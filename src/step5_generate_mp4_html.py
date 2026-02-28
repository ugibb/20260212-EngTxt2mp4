# -*- coding: utf-8 -*-
"""
步骤5（mp4 流程）：生成 TTS 播放页 HTML
基于模板 template-txt2mp4.html，从 output/02-vocabulary 和 output/03-mp3 读取数据，
生成 HTML 播放页，保存至 output/05-mp4_html/{文件名}.html

数据来源：
- 顶部音标、底部中文：output/02-vocabulary/{文件名}.md 核心词汇
- 中间英文、段落中文：output/02-vocabulary/{文件名}.md 段落结构（严格按 md 分段）
- 时间戳、音频：output/03-mp3/{文件名}.json、.mp3

使用方法：
    python src/step5_generate_mp4_html.py
"""

import sys
import re
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.config import (
    SKIP_IF_EXISTS,
    get_input_files_to_process,
    INPUT_DIR,
    OUTPUT_03_MP3_DIR,
    OUTPUT_05_MP4_HTML_DIR,
    TEMPLATE_TXT2MP4_FILE,
    STYLE_INDEX,
    RUN_DATE,
    normalize_filename,
    ensure_dirs,
)
from src.utils.file_handler import read_text_file, get_relative_path, find_md_for_input_stem
from src.utils.material_type import get_material_name, get_material_type
from src.utils.text_processor import (
    ensure_space_after_punctuation,
    parse_markdown_vocabulary,
    parse_paragraphs_from_markdown,
    remove_bracket_markers,
)
from src.utils.logger import setup_logger, SEP_LINE

logger = setup_logger("step5")


def _normalize_segment_for_alignment(english: str) -> str:
    """
    规范化段落英文，使 MD 分词与 TTS/LRC 一致，便于后续对齐。
    例如：句号后紧跟大写字母时补空格（viral.I -> viral. I），避免 MD 出现 viral.I 单 token 而 LRC 为 viral / I 两 token 导致整段错位。
    """
    if not english:
        return english
    # 句号/问号/感叹号后紧跟大写字母时插入空格
    return re.sub(r"([.!?])([A-Z])", r"\1 \2", english)


def get_segments_from_paragraphs(paragraphs: list[dict]) -> list[str]:
    """
    从 output/02-vocabulary/{文件名}.md 的段落结构解析分段。
    严格按 md 的「段落结构」：每段一个 english 块（多行合并为一段）。
    标点后补空格，使与 TTS/LRC 分词一致，便于对齐。
    """
    return [
        _normalize_segment_for_alignment(
            ensure_space_after_punctuation(p.get("english", "").replace("\n", " ").strip())
        )
        for p in paragraphs
        if p.get("english")
    ]


def _normalize_word(w: str) -> str:
    """归一化用于匹配：小写、去除标点。"""
    return re.sub(r"[^\w\s]", "", w.lower()).strip()


def _get_md_words_flat(segments: list[str]) -> list[tuple[int, str]]:
    """
    从 MD 段落得到扁平化的 (段落索引, 归一化词) 序列。
    与 remove_bracket_markers 后的分词一致。
    """
    result: list[tuple[int, str]] = []
    for si, seg in enumerate(segments):
        clean = remove_bracket_markers(seg)
        for tok in re.findall(r"\S+", clean):
            norm = _normalize_word(tok)
            if norm:
                result.append((si, norm))
    return result


def _align_lrc_to_segments(lrc_entries: list[dict], segments: list[str]) -> list[dict]:
    """
    基于文本将 LRC 条目对齐到 MD 段落。
    处理：LRC 多词合并（如 "The park"）、标点差异（MD "month," vs LRC "month"）；
    当单词不匹配时尝试将多个 LRC 词拼成一个与 MD token 匹配（如 myths+pointed -> mythspointed），避免对齐卡住。
    """
    md_flat = _get_md_words_flat(segments)
    # 将 LRC 打平为 (entry_idx, normalized_word)，便于多词拼接匹配
    lrc_flat: list[tuple[int, str]] = []
    for i, entry in enumerate(lrc_entries):
        for p in (entry.get("text", "") or "").split():
            norm = _normalize_word(p)
            if norm:
                lrc_flat.append((i, norm))

    md_idx = 0
    last_sent_index = 0
    sent_index_by_entry: dict[int, int] = {}
    max_accumulate = 5  # 最多用几个 LRC 词拼成一个 MD token

    lrc_i = 0
    while lrc_i < len(lrc_flat):
        entry_idx, norm = lrc_flat[lrc_i]
        if md_idx >= len(md_flat):
            sent_index_by_entry[entry_idx] = last_sent_index
            lrc_i += 1
            continue
        seg_idx, md_norm = md_flat[md_idx]
        if norm == md_norm:
            sent_index_by_entry[entry_idx] = seg_idx
            last_sent_index = seg_idx
            md_idx += 1
            lrc_i += 1
        else:
            # 单词不匹配时，尝试用当前词 + 后续若干词拼接与 MD token 匹配
            found = False
            for k in range(1, min(max_accumulate + 1, len(lrc_flat) - lrc_i)):
                acc = norm
                for j in range(1, k + 1):
                    acc += lrc_flat[lrc_i + j][1]
                if acc == md_norm:
                    for j in range(0, k + 1):
                        sent_index_by_entry[lrc_flat[lrc_i + j][0]] = seg_idx
                    last_sent_index = seg_idx
                    md_idx += 1
                    lrc_i += k + 1
                    found = True
                    break
            if not found:
                sent_index_by_entry[entry_idx] = last_sent_index
                lrc_i += 1

    if md_idx < len(md_flat) and lrc_flat:
        logger.debug(
            "LRC-MD 对齐: MD 剩余 %d 词未匹配（可能 LRC 有合并 token）",
            len(md_flat) - md_idx,
        )
    return [
        {**entry, "index": i, "sentIndex": sent_index_by_entry.get(i, last_sent_index)}
        for i, entry in enumerate(lrc_entries)
    ]


def build_lrc_with_sent_index(lrc_entries: list[dict], sentences: list[str]) -> list[dict]:
    """为 LRC 条目添加 sentIndex（基于文本对齐，严格按 MD 分段）"""
    return _align_lrc_to_segments(lrc_entries, sentences)


def build_sentences_json(lrc_entries: list[dict], sentences: list[str]) -> list[dict]:
    """构建 SENTENCES_JSON（基于文本对齐后的 sentIndex 分组）"""
    lrc_with_sent = _align_lrc_to_segments(lrc_entries, sentences)
    num_segments = len(sentences)
    out: list[dict] = [{"words": []} for _ in range(num_segments)]

    for e in lrc_with_sent:
        si = e.get("sentIndex", 0)
        if 0 <= si < num_segments:
            out[si]["words"].append({"index": e["index"], "text": e["text"]})

    return out


def build_translations_from_paragraphs(paragraphs: list[dict]) -> list[str]:
    """
    从段落结构构建每段对应的中文翻译（严格按段，一段一译）。
    取值：output/02-vocabulary/{文件名}.md 段落结构 -> - **chinese**:
    与 _en.txt 的分段一一对应。
    """
    return [p.get("chinese", "").strip() for p in paragraphs if p.get("english")]


def vocab_list_to_json(vocabulary: list[dict]) -> dict:
    """将 parse_markdown_vocabulary 的词汇列表转为 {word: {w, phonetic, meaning}}"""
    result = {}
    for v in vocabulary:
        word = v.get("word", "").strip()
        if not word:
            continue
        result[word] = {
            "w": word,
            "phonetic": v.get("phonetic", ""),
            "meaning": v.get("current_meaning", ""),
        }
    return result


def process_file(base_name: str, vocab_path: Path) -> None:
    """处理单个文件"""
    out_name = normalize_filename(base_name)
    lrc_path = OUTPUT_03_MP3_DIR / f"{out_name}.json"
    mp3_path = OUTPUT_03_MP3_DIR / f"{out_name}.mp3"
    html_path = OUTPUT_05_MP4_HTML_DIR / f"{out_name}.html"

    if not vocab_path.exists():
        logger.warning("⊙ 跳过（词汇文件不存在）: %s", get_relative_path(vocab_path))
        return
    if not lrc_path.exists() or not mp3_path.exists():
        miss = get_relative_path(lrc_path) if not lrc_path.exists() else get_relative_path(mp3_path)
        logger.warning("⊙ 跳过（需先运行 step3）: %s", miss)
        return

    # 已经更新处理逻辑了（每次按天生成，运行时间可控），现在无需判断，每次直接重新处理
    # if SKIP_IF_EXISTS and html_path.exists():
    #     logger.info("⊙ 跳过执行（已存在）: %s", get_relative_path(html_path))
    #     return

    try:
        # logger.info("  读取词汇表: %s", get_relative_path(vocab_path))
        vocab_markdown = read_text_file(vocab_path)
        vocab_data = parse_markdown_vocabulary(vocab_markdown)
        paragraphs = parse_paragraphs_from_markdown(vocab_markdown)

        # 严格按 output/02-vocabulary/{文件名}.md 的「段落结构」分段
        segments = get_segments_from_paragraphs(paragraphs)
        if not segments:
            logger.warning("⊙ 未解析到段落结构，跳过: %s", get_relative_path(vocab_path))
            return

        lrc_raw = json.loads(lrc_path.read_text(encoding="utf-8"))
        # 移除 JSON 中的 phonetic、meaning，统一由 output/02-vocabulary 的 VOCABULARY 提供
        lrc_entries = [
            {k: v for k, v in e.items() if k not in ("phonetic", "meaning")}
            for e in lrc_raw
        ]
        # 若原 JSON 含 phonetic/meaning，写回清理后的版本
        if any("phonetic" in e or "meaning" in e for e in lrc_raw):
            lrc_path.write_text(json.dumps(lrc_entries, ensure_ascii=False, indent=2), encoding="utf-8")
            # logger.info("  已移除 JSON 中的 phonetic/meaning: %s", get_relative_path(lrc_path))
        lrc_with_sent = build_lrc_with_sent_index(lrc_entries, segments)
        # 过滤空文本 LRC 条目，避免 TTS 产生的空 WordBoundary 被误标 sentIndex 导致错误插入翻译块（如「Just a second.» 与 «I'm almost done.» 之间出现段落13的翻译）
        lrc_for_html = [e for e in lrc_with_sent if (e.get("text") or "").strip()]
        sentences_json = build_sentences_json(lrc_entries, segments)

        vocabulary = vocab_list_to_json(vocab_data.get("vocabulary", []))
        vocab_count = len(vocab_data.get("vocabulary", []))
        phrase_count = len(vocab_data.get("phrases", []))
        translations = build_translations_from_paragraphs(paragraphs)
        # 确保 translations 与 segments 数量一致（均来自 md 段落结构）
        if len(translations) > len(segments):
            translations = translations[: len(segments)]
        elif len(translations) < len(segments):
            translations = translations + [""] * (len(segments) - len(translations))

        title = (
            segments[0][:50] + "..."
            if segments and len(segments[0]) > 50
            else (segments[0] if segments else base_name)
        )
        audio_url = mp3_path.resolve().as_uri()

        # 根据 stem 解析资料名称 → 资料类型，用于 mp4 页红框与样式表（style_index → template/styles/style{N}.css）
        material_name = get_material_name(base_name)
        material_type = get_material_type(material_name["type_id"])
        material_type_short_label = material_type.get("short_label", "精读")
        material_type_icon = material_type.get("icon", "intensive_read")
        style_index = material_type.get("style_index", STYLE_INDEX)

        template = TEMPLATE_TXT2MP4_FILE.read_text(encoding="utf-8")
        html = template.replace("{{ARTICLE_TITLE}}", title)
        html = html.replace("{{MATERIAL_TYPE_SHORT_LABEL}}", material_type_short_label)
        html = html.replace("{{MATERIAL_TYPE_ICON}}", material_type_icon)
        html = html.replace("{{AUDIO_URL}}", audio_url)
        html = html.replace("{{VOCAB_COUNT}}", str(vocab_count))
        html = html.replace("{{PHRASE_COUNT}}", str(phrase_count))
        # 日期使用所在 input 文件夹的日期（RUN_DATE），非系统当前日期
        date_display = f"{RUN_DATE[:4]}-{RUN_DATE[4:6]}-{RUN_DATE[6:8]}" if len(RUN_DATE) == 8 else datetime.now().strftime("%Y-%m-%d")
        html = html.replace("{{DATE}}", date_display)
        html = html.replace("{{STYLE_INDEX}}", str(style_index))
        html = html.replace("{{LRC_DATA}}", json.dumps(lrc_for_html, ensure_ascii=False))
        html = html.replace("{{VOCABULARY_JSON}}", json.dumps(vocabulary, ensure_ascii=False))
        html = html.replace("{{SENTENCES_JSON}}", json.dumps(sentences_json, ensure_ascii=False))
        html = html.replace("{{TRANSLATIONS_JSON}}", json.dumps(translations, ensure_ascii=False))

        # logger.info("  写入 HTML: %s", get_relative_path(html_path))
        OUTPUT_05_MP4_HTML_DIR.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html, encoding="utf-8")
        logger.info("✓ 完成生成TTS播放页HTML: %s", get_relative_path(html_path))

    except Exception as e:
            logger.error("✗ 失败: %s - %s", get_relative_path(vocab_path), e, exc_info=True)


def main() -> None:
    """主函数"""
    ensure_dirs()

    if not INPUT_DIR.exists():
        logger.warning("⚠ 目录不存在: %s", get_relative_path(INPUT_DIR))
        return

    input_files = get_input_files_to_process()
    if not input_files:
        logger.warning("⚠ 未找到 input 目录下的 txt 文件")
        return

    logger.info("共找到 input 目录下的 txt 文件：%d 个", len(input_files))
    processed = 0
    for i, input_path in enumerate(input_files, 1):
        md_path = find_md_for_input_stem(input_path.stem)
        if not md_path:
            logger.info("⊙ 跳过（无对应 MD）: %s", get_relative_path(input_path))
            continue
        
        logger.info("[%d/%d] 开始准备生成TTS播放页HTML：%s", i, len(input_files), get_relative_path(input_path))
        try:
            process_file(md_path.stem, md_path)
            processed += 1
        except Exception as e:
            logger.error("✗ 失败: %s - %s", get_relative_path(md_path), e, exc_info=True)

    logger.info("【Step5】 完成（生成TTS播放页HTML：共 %d 个）", processed)


if __name__ == "__main__":
    main()
