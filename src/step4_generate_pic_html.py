#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
步骤4：生成HTML文件
根据模板和提取的词汇，生成排版后的HTML文件

HTML 生成逻辑统一在模板 template-txt2pic.html 中实现，本脚本仅负责数据准备与渲染。

使用方法：
    python3 src/step4_generate_html.py
    或
    ./run_step.sh step4_generate_html.py
"""
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.utils.config import INPUT_DIR, _04_HTML_DIR, TEMPLATE_FILE, SKIP_EXISTING_FILES, ensure_dirs, get_input_files_to_process
from src.utils.file_handler import (
    read_text_file,
    write_text_file,
    file_exists,
    get_file_stem,
    sanitize_filename,
    get_relative_path,
    find_md_for_input_stem,
)
from src.utils.text_processor import (
    parse_markdown_vocabulary,
    mark_vocabulary_in_text,
    parse_paragraphs_from_markdown,
    parse_title_from_markdown,
    escape_html,
    remove_bracket_markers,
)
from src.utils.logger import setup_logger, SEP_LINE

logger = setup_logger("step4")


def prepare_paragraphs(paragraphs: List[Dict[str, str]], vocabulary: List[Dict]) -> List[Dict[str, str]]:
    """
    准备段落数据供模板渲染
    对英文内容做词汇标记，移除括号标记符
    """
    result = []
    for paragraph in paragraphs:
        english_content = paragraph.get("english", "").strip()
        english_content = remove_bracket_markers(english_content)
        chinese_content = paragraph.get("chinese", "").strip()

        if not english_content:
            continue

        marked_english = mark_vocabulary_in_text(english_content, vocabulary)
        result.append({
            "english": marked_english,
            "chinese": escape_html(chinese_content),
        })
    return result


def prepare_vocabulary(vocabulary: List[Dict]) -> List[Dict]:
    """
    准备词汇数据供模板渲染
    为每个词汇构建 data-vocab 所需的 JSON 字符串
    """
    result = []
    for vocab in vocabulary:
        word = vocab.get("word", "")
        if not word:
            continue

        current_meaning = vocab.get("current_meaning", "")
        all_meanings = vocab.get("all_meanings", "")

        data_vocab = {
            "word": word,
            "phonetic": vocab.get("phonetic", ""),
            "pos": vocab.get("pos", ""),
            "current_meaning": current_meaning,
            "all_meanings": all_meanings,
            "root": vocab.get("root", ""),
            "synonyms": vocab.get("synonyms", ""),
            "derivatives": vocab.get("derivatives", ""),
            "collocations": vocab.get("collocations", ""),
            "examples": vocab.get("examples") or [],
        }
        result.append({
            "word": word,
            "phonetic": vocab.get("phonetic", ""),
            "pos": vocab.get("pos", ""),
            "current_meaning": current_meaning,     # 文中词义
            "all_meanings": all_meanings,
            "data_vocab": json.dumps(data_vocab, ensure_ascii=False),
        })
    return result


def prepare_phrases(phrases: List[Dict]) -> List[Dict]:
    """准备词组数据供模板渲染"""
    result = []
    for phrase_data in phrases:
        phrase = phrase_data.get("phrase", "")
        if not phrase:
            continue
        result.append({
            "phrase": phrase,
            "meaning": phrase_data.get("meaning", ""),
        })
    return result


def generate_html_file(vocab_file: Path) -> None:
    """
    生成HTML文件
    数据准备在 Python 中完成，HTML 结构由 Jinja2 模板渲染
    """
    file_stem = get_file_stem(vocab_file)
    sanitized_stem = sanitize_filename(file_stem)
    output_file = _04_HTML_DIR / f"{sanitized_stem}.html"

    # 已经更新处理逻辑了（每次按天生成，运行时间可控），现在无需判断，每次直接重新处理
    # if SKIP_EXISTING_FILES and file_exists(output_file):
    #     logger.info("⊙ 跳过执行（已存在）: %s", get_relative_path(output_file))
    #     return

    try:
        if not file_exists(TEMPLATE_FILE):
            logger.error("✗ 模板不存在: %s", get_relative_path(TEMPLATE_FILE))
            raise FileNotFoundError(f"模板不存在: {TEMPLATE_FILE}")

        # logger.info("  读取模板、词汇数据...")
        vocab_markdown = read_text_file(vocab_file)
        vocab_data = parse_markdown_vocabulary(vocab_markdown)

        article_title = parse_title_from_markdown(vocab_markdown)
        if not article_title:
            article_title = file_stem
            logger.warning("⚠ 未找到标题，使用文件名: %s", article_title)

        paragraphs_raw = parse_paragraphs_from_markdown(vocab_markdown)
        vocabulary_raw = vocab_data.get("vocabulary", [])
        phrases_raw = vocab_data.get("phrases", [])

        paragraphs = prepare_paragraphs(paragraphs_raw, vocabulary_raw)
        vocabulary = prepare_vocabulary(vocabulary_raw)
        phrases = prepare_phrases(phrases_raw)

        env = Environment(
            loader=FileSystemLoader(TEMPLATE_FILE.parent),
            autoescape=select_autoescape(["html", "xml"]),
        )
        template = env.get_template(TEMPLATE_FILE.name)

        html_content = template.render(
            title=escape_html(article_title),
            article_title=escape_html(article_title),
            date=datetime.now().strftime("%Y-%m-%d"),
            paragraphs=paragraphs,
            vocabulary=vocabulary,
            phrases=phrases,
        )

        write_text_file(output_file, html_content)
        logger.info("✓ 完成: %s", get_relative_path(output_file))

    except Exception as e:
        logger.error("✗ 失败: %s - %s", get_relative_path(vocab_file), e, exc_info=True)
        raise


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

    if not file_exists(TEMPLATE_FILE):
        logger.error("✗ 模板不存在: %s", get_relative_path(TEMPLATE_FILE))
        raise FileNotFoundError(f"模板不存在: {TEMPLATE_FILE}")

    logger.info("共找到 input 目录下的 txt 文件：%d 个", len(input_files))
    processed_count = 0
    for i, input_path in enumerate(input_files, 1):
        md_path = find_md_for_input_stem(input_path.stem)
        if not md_path:
            logger.info("⊙ 跳过（无对应 MD）: %s", get_relative_path(input_path))
            continue
        logger.info("[%d/%d] 开始准备生成排版HTML：%s", i, len(input_files), get_relative_path(input_path))
        try:
            generate_html_file(md_path)
            processed_count += 1
        except Exception as e:
            logger.error("✗ 失败: %s - %s", get_relative_path(md_path), e, exc_info=True)

    logger.info("【Step4】 完成（排版HTML：共 %d 个）", processed_count)


if __name__ == "__main__":
    main()
