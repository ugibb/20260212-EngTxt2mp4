# -*- coding: utf-8 -*-
"""
步骤 6：Playwright 全屏录屏 HTML 播放页，导出 MP4
录制尺寸：移动端 APP 竖屏 9:16（默认 1080x1920），可在 config.py 或 .env 中配置 VIDEO_WIDTH/VIDEO_HEIGHT
"""

import sys
import time
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
    OUTPUT_05_MP4_DIR,
    VIDEO_WIDTH,
    VIDEO_HEIGHT,
    VIDEO_TRIM_SYNC_OFFSET,
    VIDEO_TRIM_SYNC_OFFSET_EIM,
    normalize_filename,
    ensure_dirs,
)
from src.utils.file_handler import get_relative_path, find_md_for_input_stem
from src.utils.logger import setup_logger, SEP_LINE

logger = setup_logger("step6")


def _get_ffmpeg_cmd() -> str | None:
    """获取 ffmpeg 可执行路径（兼容 Homebrew 等环境），不可用时返回 None"""
    import shutil
    cmd = shutil.which("ffmpeg")
    if cmd:
        return cmd
    for path in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
        if Path(path).exists():
            return path
    return None


def _check_ffmpeg() -> bool:
    """检查 ffmpeg 是否可用（MP4 输出必需）"""
    return _get_ffmpeg_cmd() is not None


def _merge_video_audio(webm_path: Path, mp3_path: Path, out_path: Path, use_mp4: bool, reencode_video: bool = False, trim_start: float = 0) -> bool:
    """使用 ffmpeg 合并视频与音频。trim_start：裁剪视频开头秒数（对齐 mp3 起点，解决音画不同步）"""
    import subprocess
    ffmpeg = _get_ffmpeg_cmd()
    if not ffmpeg:
        return False
    # 音画同步：-ss 放 -i 前可快速裁剪，-avoid_negative_ts make_zero 归一化时间戳
    video_input = ["-ss", str(trim_start), "-i", str(webm_path)] if trim_start > 0 else ["-i", str(webm_path)]
    sync_flags = ["-avoid_negative_ts", "make_zero", "-fflags", "+genpts"]
    try:
        if use_mp4:
            if reencode_video:
                subprocess.run(
                    [
                        ffmpeg, "-y",
                        *video_input,
                        "-i", str(mp3_path),
                        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                        "-c:a", "aac",
                        "-shortest",
                        *sync_flags,
                        "-movflags", "+faststart",
                        str(out_path),
                    ],
                    check=True,
                    capture_output=True,
                )
            else:
                subprocess.run(
                    [
                        ffmpeg, "-y",
                        *video_input,
                        "-i", str(mp3_path),
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-shortest",
                        *sync_flags,
                        "-movflags", "+faststart",
                        str(out_path),
                    ],
                    check=True,
                    capture_output=True,
                )
        else:
            subprocess.run(
                [
                    ffmpeg, "-y",
                    "-i", str(webm_path),
                    "-i", str(mp3_path),
                    "-c:v", "copy",
                    "-c:a", "libopus",
                    "-shortest",
                    str(out_path),
                ],
                check=True,
                capture_output=True,
            )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _remove_empty_mp4(mp4_path: Path) -> None:
    """删除 ffmpeg 失败时产生的 0 字节 mp4 文件"""
    if mp4_path.exists() and mp4_path.stat().st_size == 0:
        mp4_path.unlink(missing_ok=True)


def _convert_webm_to_mp4(webm_path: Path, mp4_path: Path, mp3_path: Path | None = None, trim_start: float = 0) -> bool:
    """使用 ffmpeg 将 webm 转为 mp4（H.264 编码，兼容性最佳），若有 mp3 则合并音轨。返回是否成功"""
    import subprocess
    ffmpeg = _get_ffmpeg_cmd()
    if not ffmpeg:
        return False
    try:
        if mp3_path and mp3_path.exists():
            # 优先转为 mp4（含音频）：trim_start 裁剪视频开头，对齐 mp3 起点
            if _merge_video_audio(webm_path, mp3_path, mp4_path, use_mp4=True, reencode_video=False, trim_start=trim_start):
                logger.info("✓ 已转为 mp4（含音频）: %s", get_relative_path(mp4_path))
                webm_path.unlink(missing_ok=True)
                return True
            _remove_empty_mp4(mp4_path)
            if _merge_video_audio(webm_path, mp3_path, mp4_path, use_mp4=True, reencode_video=True, trim_start=trim_start):
                logger.info("✓ 已保存 MP4 文件: %s", get_relative_path(mp4_path))
                webm_path.unlink(missing_ok=True)
                return True
            _remove_empty_mp4(mp4_path)
        # 无 mp3 或合并失败时：先尝试 -c copy，失败则用 libx264 重编码（无音轨）
        video_in = ["-ss", str(trim_start), "-i", str(webm_path)] if trim_start > 0 else ["-i", str(webm_path)]
        try:
            subprocess.run(
                [ffmpeg, "-y", *video_in, "-c", "copy", "-avoid_negative_ts", "make_zero", str(mp4_path)],
                check=True,
                capture_output=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            _remove_empty_mp4(mp4_path)
            subprocess.run(
                [
                    ffmpeg, "-y", *video_in,
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-an", "-avoid_negative_ts", "make_zero", "-movflags", "+faststart",
                    str(mp4_path),
                ],
                check=True,
                capture_output=True,
            )
        logger.info("✓ 已转为 mp4: %s", get_relative_path(mp4_path))
        webm_path.unlink(missing_ok=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        _remove_empty_mp4(mp4_path)
        return False


def _get_mp3_path_from_html(html_path: Path, fallback_stem: str) -> Path | None:
    """从 HTML 的 audio src 解析 mp3 路径，若无则用 fallback_stem 拼接"""
    import re
    mp3_path = OUTPUT_03_MP3_DIR / f"{fallback_stem}.mp3"
    if mp3_path.exists():
        return mp3_path
    try:
        content = html_path.read_text(encoding="utf-8")
        # 匹配 src="file:///.../xxx.mp3" 或 src=".../xxx.mp3"
        m = re.search(r'src=["\']([^"\']+\.mp3)["\']', content)
        if m:
            src = m.group(1)
            if src.startswith("file://"):
                from urllib.parse import unquote
                p = Path(unquote(src.replace("file://", "")))
                if p.exists():
                    return p
    except Exception:
        pass
    return mp3_path if mp3_path.exists() else None


def record_html(html_path: Path, mp4_path: Path) -> None:
    """录制单个 HTML 并保存为 MP4"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required"],
        )
        context = browser.new_context(
            record_video_dir=str(mp4_path.parent),
            record_video_size={"width": VIDEO_WIDTH, "height": VIDEO_HEIGHT},
            viewport={"width": VIDEO_WIDTH, "height": VIDEO_HEIGHT},
            device_scale_factor=1,
        )
        page = context.new_page()
        t_start = time.time()
        page.goto(html_path.as_uri(), wait_until="networkidle", timeout=30000)

        # 点击播放（记录从页面创建到点击的时长，用于裁剪视频开头以对齐 mp3）
        play_btn = page.locator("#playBtn")
        play_btn.wait_for(state="visible", timeout=5000)
        play_btn.click()
        # 基础裁剪量（点击前预录）；再叠加 config 中的音画同步微调（VIDEO_TRIM_SYNC_OFFSET / VIDEO_TRIM_SYNC_OFFSET_EIM）
        base_trim = time.time() - t_start - 0.4
        is_eim = mp4_path.stem.startswith("EIM_")
        sync_offset = VIDEO_TRIM_SYNC_OFFSET + (VIDEO_TRIM_SYNC_OFFSET_EIM if is_eim else 0.0)
        trim_start = max(0, round(base_trim + sync_offset, 1))
        # if trim_start > 0:
        #     logger.info("  裁剪视频开头 %.1fs 以对齐音轨", trim_start)

        # 等待音频播放结束
        try:
            page.evaluate("""() => {
                return new Promise(resolve => {
                    const audio = document.getElementById('audio');
                    if (audio.duration && !isNaN(audio.duration)) {
                        const ms = (audio.duration + 3) * 1000;
                        setTimeout(resolve, ms);
                    } else {
                        setTimeout(resolve, 90000);
                    }
                });
            }""")
        except Exception:
            page.wait_for_timeout(90000)

        # 保存视频：需先关闭 page，再调用 save_as
        video = page.video
        page.close()
        if video:
            webm_path = mp4_path.with_suffix(".webm")
            # 获取 Playwright 原始路径（save_as 会复制，原文件仍存在）
            try:
                original_path = Path(video.path()) if video.path() else None
            except Exception:
                original_path = None
            video.save_as(str(webm_path))
            # 删除 Playwright 原始视频，仅保留最终结果
            if original_path and original_path.exists() and original_path.resolve() != webm_path.resolve():
                original_path.unlink(missing_ok=True)
            # 统一转为 MP4（兼容性最佳），合并 mp3 音轨
            mp3_path = _get_mp3_path_from_html(html_path, mp4_path.stem)
            if not mp3_path or not mp3_path.exists():
                logger.warning("⊙ 未找到 mp3: %s，输出将无音频", get_relative_path(OUTPUT_03_MP3_DIR / f"{mp4_path.stem}.mp3"))
            if _convert_webm_to_mp4(webm_path, mp4_path, mp3_path, trim_start=trim_start):
                pass
            else:
                webm_path.unlink(missing_ok=True)
                raise RuntimeError("ffmpeg 不可用或转换失败，无法输出 MP4。请安装 ffmpeg: brew install ffmpeg")

        total_elapsed = time.time() - t_start
        logger.info("  裁剪视频开头 %.1fs 以对齐音轨（录屏执行总用时 %.1fs）", trim_start, total_elapsed)
        context.close()
        browser.close()


def main() -> None:
    ensure_dirs()
    # logger.info("%s", SEP_LINE)
    # logger.info("【Step6】 视频录制（输出 MP4）")
    # logger.info("%s", SEP_LINE)

    if not _check_ffmpeg():
        logger.error("✗ ffmpeg 未安装，无法输出 MP4。请安装: brew install ffmpeg")
        return

    OUTPUT_05_MP4_DIR.mkdir(parents=True, exist_ok=True)

    if not INPUT_DIR.exists():
        logger.warning("⚠ 目录不存在: %s", get_relative_path(INPUT_DIR))
        return

    input_files = get_input_files_to_process()
    if not input_files:
        logger.warning("⚠ 未找到 input 目录下的 txt 文件")
        return

    logger.info("共找到 input 目录下的 txt 文件：%d 个（竖屏 %dx%d）", len(input_files), VIDEO_WIDTH, VIDEO_HEIGHT)
    processed = 0
    for i, input_path in enumerate(input_files, 1):
        md_path = find_md_for_input_stem(input_path.stem)
        if not md_path:
            logger.info("⊙ 跳过（无对应 MD）: %s", get_relative_path(input_path))
            continue
        out_name = normalize_filename(md_path.stem)
        html_path = OUTPUT_05_MP4_HTML_DIR / f"{out_name}.html"
        if not html_path.exists():
            logger.info("⊙ 跳过（无对应 HTML，请先运行 step5）: %s", get_relative_path(input_path))
            continue
        mp4_path = OUTPUT_05_MP4_DIR / f"{out_name}.mp4"
        webm_path = mp4_path.with_suffix(".webm")

        # 已经更新处理逻辑了（每次按天生成，运行时间可控），现在无需判断，每次直接重新处理
        # if SKIP_IF_EXISTS and mp4_path.exists():
        #     logger.info("⊙ 跳过执行（录屏文件已存在）: %s", get_relative_path(mp4_path))
        #     continue

        logger.info("[%d/%d] 开始录制TTS播放页HTML：%s", i, len(input_files), get_relative_path(html_path))
        try:
            record_html(html_path, mp4_path)
            processed += 1
        except Exception as e:
            logger.error("✗ 失败: %s - %s", get_relative_path(html_path), e)

    logger.info("【Step7】 完成（录屏MP4：共 %d 个）", processed)


if __name__ == "__main__":
    main()
