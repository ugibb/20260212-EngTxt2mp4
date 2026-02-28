# -*- coding: utf-8 -*-
"""
统一配置：所有配置项优先从项目根目录的 .env 文件中读取
单一数据源，避免重复定义
"""

import os
import re
from datetime import date
from pathlib import Path

# 项目根目录（config 位于 src/utils/config.py，上两级为项目根）
_CONFIG_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _CONFIG_DIR.parent.parent

# 加载 .env（支持多种路径；无 python-dotenv 时手动解析）
def _parse_env_file(path: Path) -> None:
    """简单解析 .env 文件，将 KEY=VALUE 写入 os.environ（无 python-dotenv 时的回退）"""
    try:
        content = path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("'\"")
                if key:
                    os.environ[key] = value
    except Exception:
        pass


def _load_env() -> None:
    env_paths = [
        PROJECT_ROOT / ".env",
        Path.cwd() / ".env",
        Path.cwd().parent / ".env",
    ]
    loaded = False
    try:
        from dotenv import load_dotenv
        for p in env_paths:
            resolved = p.resolve()
            if resolved.exists():
                load_dotenv(dotenv_path=resolved, override=True)
                loaded = True
                break
    except ImportError:
        pass
    if not loaded:
        for p in env_paths:
            resolved = p.resolve()
            if resolved.exists():
                _parse_env_file(resolved)
                break


_load_env()

# 是否跳过已存在文件（统一配置，step1/2/4/5/6 等已存在输出时跳过；直接在此修改，无需 .env）
# SKIP_IF_EXISTS: bool = False
SKIP_IF_EXISTS: bool = True
SKIP_EXISTING_FILES: bool = SKIP_IF_EXISTS  # 别名

# 视频录制尺寸（移动端 APP 竖屏 9:16）
VIDEO_WIDTH: int = 1080
VIDEO_HEIGHT: int = 1920


# 录屏 MP4 音画同步微调（秒）：裁剪视频开头时加上该偏移。统一在 config.py 中配置，无需 .env。
# 若出现「音频晚于字幕」（字幕先出、声音后到），设为负值如 -0.2 少裁视频以对齐；若「字幕晚于音频」则设正值。
VIDEO_TRIM_SYNC_OFFSET: float = 0.0
# 仅对 EIM_ 前缀素材的录屏做额外 trim 微调（秒）；该类页面易出现「音频晚于字幕」，默认 -0.2 少裁视频。
VIDEO_TRIM_SYNC_OFFSET_EIM: float = -0.2

# 运行日期（用于 input/YYYYMMDD、output/YYYYMMDD 子目录；可从 .env 的 RUN_DATE 或 run_all.py --date 传入）
RUN_DATE: str = (os.getenv("RUN_DATE") or date.today().strftime("%Y%m%d")).strip()

# 仅处理指定文件（run_all -f 传入；为 input 目录下文件名或 stem，如 "IELT50_Day02：A Forest Exploration.txt" 或 "IELT50_Day02：A Forest Exploration"）
RUN_SINGLE_FILE: str = (os.getenv("RUN_SINGLE_FILE") or "").strip()

# 目录配置（统一使用 Path；input/output 按日期分子目录）
INPUT_BASE: Path = PROJECT_ROOT / "input"
OUTPUT_BASE: Path = PROJECT_ROOT / "output"
INPUT_DIR: Path = INPUT_BASE / RUN_DATE
OUTPUT_DIR: Path = OUTPUT_BASE / RUN_DATE
LOG_DIR: Path = PROJECT_ROOT / "log"
DOC_DIR: Path = PROJECT_ROOT / "doc"
TEMPLATE_DIR: Path = PROJECT_ROOT / "template"

# 输出子目录
OUTPUT_01_TXT_DIR: Path = OUTPUT_DIR / "01-txt"
OUTPUT_02_VOCABULARY_DIR: Path = OUTPUT_DIR / "02-vocabulary"
OUTPUT_03_MP3_DIR: Path = OUTPUT_DIR / "03-mp3"
OUTPUT_04_PIC_HTML_DIR: Path = OUTPUT_DIR / "04-pic_html"
OUTPUT_05_MP4_HTML_DIR: Path = OUTPUT_DIR / "05-mp4_html"
OUTPUT_05_MP4_DIR: Path = OUTPUT_DIR / "06-mp4"

# 资源索引页（step7 生成）：仅更新全局 output/resources.html，不生成当日 output/YYYYMMDD/resources.html
OUTPUT_RESOURCE_INDEX: Path = OUTPUT_DIR / "resources.html"
OUTPUT_GLOBAL_RESOURCE_INDEX: Path = OUTPUT_BASE / "resources.html"

# 模板文件
TEMPLATE_FILE: Path = TEMPLATE_DIR / "template-txt2pic.html"
TEMPLATE_TXT2MP4_FILE: Path = TEMPLATE_DIR / "template-txt2mp4.html"
TEMPLATE_RESOURCE_INDEX: Path = TEMPLATE_DIR / "resource-index.html"
TEMPLATE_STYLES_DIR: Path = TEMPLATE_DIR / "styles"
OUTPUT_MP4_STYLES_DIR: Path = OUTPUT_05_MP4_HTML_DIR / "styles"
VOCABULARY_PROMPT_TEMPLATE: Path = TEMPLATE_DIR / "prompt_vocabulary_extraction.txt"

# 播放页样式索引（1-4），可通过 .env 的 STYLE_INDEX 覆盖
STYLE_INDEX: int = 4

# 兼容别名（指向同一路径，避免多处修改）
_01_TXT_DIR: Path = OUTPUT_01_TXT_DIR
_02_VOCABULARY_DIR: Path = OUTPUT_02_VOCABULARY_DIR
_04_HTML_DIR: Path = OUTPUT_04_PIC_HTML_DIR

# LLM API 配置（从 .env 读取，兼容 OPENAI_* 与 LLM_* 两种命名）
KIMI_API_KEY: str = os.getenv("KIMI_API_KEY", "").strip()
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "").strip()
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.moonshot.cn/v1").strip()
LLM_MODEL: str = (
    os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or "kimi-k2.5"
).strip()

# API 调用配置
MAX_RETRIES: int = 3
RETRY_DELAY: int = 2
REQUEST_TIMEOUT: int = 60
# LLM 请求超时（秒），词汇提取输出较长，默认 5 分钟
LLM_REQUEST_TIMEOUT: int = int(os.getenv("LLM_REQUEST_TIMEOUT", "300"))

# 日志配置（与 utils/logger 保持一致）
LOG_FORMAT: str = "%(asctime)s │ %(levelname)-5s │ %(message)s"
LOG_DATE_FORMAT: str = "%H:%M:%S"


def normalize_filename(name: str) -> str:
    """将文件名中的空格及特殊字符替换为 _"""
    normalized = re.sub(r"[\s\-\.]+", "_", name)
    normalized = re.sub(r"[^\w\u4e00-\u9fff]", "_", normalized)
    return normalized.strip("_")


def get_input_files_to_process() -> list[Path]:
    """
    返回当前应处理的 input 下的 txt 文件列表。
    若 RUN_SINGLE_FILE 已设置，则只返回与之匹配的一个文件（按文件名或 stem 匹配，可带或不带 .txt）。
    """
    if not INPUT_DIR.exists():
        return []
    files = sorted(INPUT_DIR.glob("*.txt"))
    if not RUN_SINGLE_FILE:
        return files
    needle = RUN_SINGLE_FILE.strip()
    needle_txt = needle if needle.endswith(".txt") else f"{needle}.txt"
    for p in files:
        if p.name == needle_txt or p.stem == needle or p.name == needle:
            return [p]
    return []


def ensure_dirs() -> None:
    """确保所需目录存在"""
    dirs = [
        INPUT_DIR, OUTPUT_DIR, LOG_DIR, DOC_DIR, TEMPLATE_DIR,
        OUTPUT_01_TXT_DIR, OUTPUT_02_VOCABULARY_DIR, OUTPUT_03_MP3_DIR,
        OUTPUT_04_PIC_HTML_DIR, OUTPUT_05_MP4_HTML_DIR, OUTPUT_05_MP4_DIR,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
