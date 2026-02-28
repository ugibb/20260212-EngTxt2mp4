# -*- coding: utf-8 -*-
"""
步骤 3：TTS 音频 + 单词级时间戳

支持多角色语音：MD 段落结构中的 role 或 input 中的 [男]/[女] 等标记，按段选用不同 Edge TTS 声音后合并为单一 mp3 + json。

输入：
  - 遍历 input/*.txt
  - 找到同名 MD（output/02-vocabulary/{文件名}.md）后，从 MD 段落结构生成 _en.txt 并用于 TTS
输出：
  - output/01-txt/{文件名}_en.txt：纯英文短文（由 step3 从 MD 生成）
  - output/03-mp3/{文件名}.mp3：TTS 音频（多角色时按段合成）
  - output/03-mp3/{文件名}.json：单词级时间戳 [{start, end, text, index}]

使用方法：
    python src/step3_generate_tts.py
"""

import sys
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import edge_tts
from src.utils.config import (
    get_input_files_to_process,
    INPUT_DIR,
    OUTPUT_01_TXT_DIR,
    OUTPUT_03_MP3_DIR,
    normalize_filename,
    ensure_dirs,
)
from src.utils.file_handler import read_text_file, write_text_file, get_relative_path, find_md_for_input_stem
from src.utils.text_processor import parse_paragraphs_from_markdown, remove_bracket_markers
from src.utils.voice_role import get_voice_for_role, NARRATION
from src.utils.logger import setup_logger, SEP_LINE

logger = setup_logger("step3")


# 英文标点（词尾附加，用于 HTML 同步显示）
_TRAILING_PUNCT = ".,!?;:\"'"


def _attach_punctuation_from_source(lrc_entries: list[dict], source_text: str) -> list[dict]:
    """
    根据源文本为 LRC 条目附加词尾标点，保证 output/05-mp4_html 可同步显示标点。
    标点前加空格，便于词汇表匹配音标和词义（"month" 可匹配，"," 单独显示）。
    Edge TTS WordBoundary 不包含标点，需从 TTS 输入文本中按序匹配并附加。
    """
    if not lrc_entries or not source_text:
        return lrc_entries
    src = source_text.replace("\n", " ")
    src_lower = src.lower()
    pos = 0
    result = []
    for entry in lrc_entries:
        raw = entry.get("text", "")
        if not raw:
            result.append(entry)
            continue
        # 剥离已有标点，用纯词匹配源文本
        word = raw.rstrip(_TRAILING_PUNCT)
        idx = src_lower.find(word.lower(), pos)
        if idx >= 0:
            end = idx + len(word)
            punct = ""
            while end < len(src) and src[end] in _TRAILING_PUNCT:
                punct += src[end]
                end += 1
            # 标点前加空格，便于词汇表匹配音标和词义
            result.append({**entry, "text": word + (" " + punct if punct else "")})
            pos = end
        else:
            result.append(entry)
    return result


def srt_to_lrc(srt_content: str) -> list[dict]:
    """将 SRT 转成 LRC 格式 [{start, end, text, index}]"""
    entries = []
    # SRT 格式: 序号\n开始-->结束\n文本\n\n
    blocks = re.split(r'\n\s*\n', srt_content.strip())
    for i, block in enumerate(blocks):
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            times = lines[1]
            text = ' '.join(lines[2:]).strip()
            m = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})', times)
            if m:
                start = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 1000
                end = int(m.group(5)) * 3600 + int(m.group(6)) * 60 + int(m.group(7)) + int(m.group(8)) / 1000
                entries.append({"start": start, "end": end, "text": text, "index": i})
    return entries


def _generate_en_txt_and_get_paragraphs(md_path: Path) -> tuple[str | None, list[dict]]:
    """
    从 MD 段落结构生成 output/01-txt/{stem}_en.txt，并返回全文与段落列表（含 role）。
    返回 (full_text, paragraphs)；无段落时 (None, [])。
    """
    content = read_text_file(md_path)
    paragraphs = parse_paragraphs_from_markdown(content)
    segments = [
        remove_bracket_markers(p.get("english", "").replace("\n", " ").strip())
        for p in paragraphs
        if p.get("english")
    ]
    if not segments:
        logger.warning("⊙ 跳过（MD 无段落结构）: %s", get_relative_path(md_path))
        return None, []
    text = "\n".join(segments)
    stem = md_path.stem
    en_path = OUTPUT_01_TXT_DIR / f"{stem}_en.txt"
    OUTPUT_01_TXT_DIR.mkdir(parents=True, exist_ok=True)
    write_text_file(en_path, text + "\n")
    logger.info("✓ 完成生成 「_en.txt」的中间文件: %s（%d 段）", get_relative_path(en_path), len(segments))
    return text, paragraphs


def _get_audio_duration_sec(path: Path) -> float | None:
    """用 ffprobe 获取音频时长（秒），失败返回 None。用于多段合并时按真实时长做时间戳偏移。"""
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0 and out.stdout and out.stdout.strip():
            return float(out.stdout.strip())
    except (FileNotFoundError, ValueError, subprocess.TimeoutExpired):
        pass
    return None


def _concat_mp3_files(file_paths: list[Path], out_path: Path) -> bool:
    """使用 ffmpeg 将多个 mp3 按顺序拼接为 out_path。成功返回 True。"""
    if not file_paths:
        return False
    if len(file_paths) == 1:
        import shutil
        shutil.copy(file_paths[0], out_path)
        return True
    list_file = out_path.parent / (out_path.stem + "_concat_list.txt")
    try:
        # ffmpeg concat 要求 list 里路径可相对可绝对，一行 file 'path'
        lines = [f"file '{p.resolve()}'\n" for p in file_paths]
        list_file.write_text("".join(lines), encoding="utf-8")
        ret = subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(list_file),
                "-c", "copy",
                str(out_path),
            ],
            capture_output=True,
            timeout=120,
        )
        if ret.returncode != 0:
            logger.warning("⊙ ffmpeg concat 失败: %s", (ret.stderr or b"").decode("utf-8", errors="replace")[:200])
            return False
        return True
    except FileNotFoundError:
        logger.warning("⊙ 未找到 ffmpeg，无法合并多段音频；请安装 ffmpeg 或使用单角色内容")
        return False
    except Exception as e:
        logger.warning("⊙ 合并 mp3 时出错: %s", e)
        return False
    finally:
        if list_file.exists():
            try:
                list_file.unlink()
            except Exception:
                pass


def generate_tts_for_file(input_path: Path, md_path: Path, out_name: str) -> None:
    """为单个文件生成 _en.txt、MP3 和 JSON；支持按段落多角色 TTS 后合并。"""
    mp3_path = OUTPUT_03_MP3_DIR / f"{out_name}.mp3"
    json_path = OUTPUT_03_MP3_DIR / f"{out_name}.json"

    full_text, paragraphs = _generate_en_txt_and_get_paragraphs(md_path)
    if not full_text or not paragraphs:
        return

    # 按段生成 TTS：每段对应 role → voice，写临时 mp3，收集 LRC 并做时间偏移
    segment_texts = [
        remove_bracket_markers(p.get("english", "").replace("\n", " ").strip())
        for p in paragraphs
        if p.get("english")
    ]
    if not segment_texts:
        return

    segment_roles = [
        (p.get("role") or NARRATION) for p in paragraphs if p.get("english")
    ]
    assert len(segment_texts) == len(segment_roles)

    OUTPUT_03_MP3_DIR.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.gettempdir()) / "txt2mp4_tts"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_mp3s: list[Path] = []
    all_lrc: list[dict] = []
    offset_sec = 0.0
    global_index = 0

    try:
        t0 = time.perf_counter()
        for i, (seg_text, role) in enumerate(zip(segment_texts, segment_roles)):
            if not seg_text.strip():
                continue
            voice = get_voice_for_role(role)
            communicate = edge_tts.Communicate(seg_text, voice, boundary="WordBoundary")
            submaker = edge_tts.SubMaker()
            seg_mp3 = temp_dir / f"{out_name}_seg_{i}.mp3"
            with open(seg_mp3, "wb") as f:
                for chunk in communicate.stream_sync():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        submaker.feed(chunk)
            temp_mp3s.append(seg_mp3)
            srt_content = submaker.get_srt()
            lrc_entries = srt_to_lrc(srt_content)
            for e in lrc_entries:
                e["start"] += offset_sec
                e["end"] += offset_sec
                e["index"] = global_index
                global_index += 1
            # 下一段偏移用本段音频真实时长，避免 LRC 末词 end 小于实际 MP3 导致字幕快于音频
            seg_duration = _get_audio_duration_sec(seg_mp3)
            if seg_duration is not None:
                offset_sec += seg_duration
            elif lrc_entries:
                offset_sec = lrc_entries[-1]["end"]
            all_lrc.extend(lrc_entries)

        elapsed = time.perf_counter() - t0
        elapsed_str = f"{elapsed:.1f}s" if elapsed < 60 else f"{int(elapsed // 60)}分{elapsed % 60:.1f}秒"

        # 合并音频
        if _concat_mp3_files(temp_mp3s, mp3_path):
            logger.info("✓ 完成生成TTS音频: %s（耗时 %s）", get_relative_path(mp3_path), elapsed_str)
        else:
            # 回退：若只有一段则已写入 temp_mp3s[0]，拷贝到目标
            if len(temp_mp3s) == 1:
                import shutil
                shutil.copy(temp_mp3s[0], mp3_path)
                logger.info("✓ 完成生成TTS音频: %s（耗时 %s）", get_relative_path(mp3_path), elapsed_str)
            else:
                logger.error("✗ 多段音频合并失败，未生成 mp3")

        # 标点附加与 JSON
        all_lrc = _attach_punctuation_from_source(all_lrc, full_text)
        json_path.write_text(json.dumps(all_lrc, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("✓ 完成生成时间戳: %s（耗时 %s）", get_relative_path(json_path), elapsed_str)
    finally:
        for p in temp_mp3s:
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass


def main() -> None:
    ensure_dirs()

    if not INPUT_DIR.exists():
        logger.warning("⚠ input目录不存在：%s", get_relative_path(INPUT_DIR))
        return

    input_files = get_input_files_to_process()
    if not input_files:
        logger.warning("⚠ 未找到 input 目录下的 txt 文件")
        return

    processed = 0
    logger.info("共找到 input 目录下的 txt 文件：%d 个", len(input_files))
    for i, input_path in enumerate(input_files, 1):
        input_stem = input_path.stem
        md_path = find_md_for_input_stem(input_stem)
        if not md_path:
            logger.info("⊙ 无对应 MD文件，请先运行 step2：%s", get_relative_path(input_path))
            continue
        out_name = normalize_filename(md_path.stem)
        logger.info("[%d/%d] 开始准备生成TTS音频+时间戳：%s", i, len(input_files), get_relative_path(input_path))
        try:
            generate_tts_for_file(input_path, md_path, out_name)
            processed += 1
        except Exception as e:
            logger.error("✗ 失败: %s - %s", get_relative_path(input_path), e, exc_info=True)

    logger.info("【Step3】 完成（生成TTS音频+时间戳：共处理 %d 个）", processed)


if __name__ == "__main__":
    main()
