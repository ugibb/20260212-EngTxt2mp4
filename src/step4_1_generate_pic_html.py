#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
步骤4.1：生成 HTML 文件（v2 版本）
使用 template-txt2pic-v2.html，正文采用「上音标、下中义」静态展示（参考 template-txt2mp4），无动效。
其他内容与 step4 保持一致；与 step4 并存，输出文件名为 xxx_v2.html。

使用方法：
    python3 src/step4_1_generate_pic_html.py
    或
    ./run_step.sh step4_1_generate_pic_html.py
"""
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.utils.config import (
    INPUT_DIR,
    _04_HTML_DIR,
    TEMPLATE_FILE_V2,
    ensure_dirs,
    get_input_files_to_process,
)
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
    mark_paragraph_with_phrase_wrap,
    parse_paragraphs_from_markdown,
    parse_title_from_markdown,
    escape_html,
    remove_bracket_markers,
)
from src.utils.logger import setup_logger

logger = setup_logger("step4_1")


def prepare_paragraphs_v2(paragraphs: List[Dict[str, str]], vocabulary: List[Dict]) -> List[Dict[str, str]]:
    """
    准备段落数据供 v2 模板渲染
    英文内容按「上音标、下中义」生成 phrase-wrap 静态 HTML，移除括号标记符
    """
    result = []
    for paragraph in paragraphs:
        english_content = paragraph.get("english", "").strip()
        english_content = remove_bracket_markers(english_content)
        chinese_content = paragraph.get("chinese", "").strip()

        if not english_content:
            continue

        marked_english = mark_paragraph_with_phrase_wrap(english_content, vocabulary)
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
            "current_meaning": current_meaning,
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


def generate_pic_html_v2(vocab_file: Path) -> None:
    """
    生成 v2 版 HTML 文件
    使用 template-txt2pic-v2.html，输出为 xxx_v2.html
    """
    file_stem = get_file_stem(vocab_file)
    sanitized_stem = sanitize_filename(file_stem)
    output_file = _04_HTML_DIR / f"{sanitized_stem}_v2.html"

    try:
        if not file_exists(TEMPLATE_FILE_V2):
            logger.error("✗ 模板不存在: %s", get_relative_path(TEMPLATE_FILE_V2))
            raise FileNotFoundError(f"模板不存在: {TEMPLATE_FILE_V2}")

        vocab_markdown = read_text_file(vocab_file)
        vocab_data = parse_markdown_vocabulary(vocab_markdown)

        article_title = parse_title_from_markdown(vocab_markdown)
        if not article_title:
            article_title = file_stem
            logger.warning("⚠ 未找到标题，使用文件名: %s", article_title)

        paragraphs_raw = parse_paragraphs_from_markdown(vocab_markdown)
        vocabulary_raw = vocab_data.get("vocabulary", [])
        phrases_raw = vocab_data.get("phrases", [])

        vocabulary = prepare_vocabulary(vocabulary_raw)
        paragraphs = prepare_paragraphs_v2(paragraphs_raw, vocabulary)
        phrases = prepare_phrases(phrases_raw)

        env = Environment(
            loader=FileSystemLoader(TEMPLATE_FILE_V2.parent),
            autoescape=select_autoescape(["html", "xml"]),
        )
        template = env.get_template(TEMPLATE_FILE_V2.name)

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

    if not file_exists(TEMPLATE_FILE_V2):
        logger.error("✗ 模板不存在: %s", get_relative_path(TEMPLATE_FILE_V2))
        raise FileNotFoundError(f"模板不存在: {TEMPLATE_FILE_V2}")

    logger.info("共找到 input 目录下的 txt 文件：%d 个", len(input_files))
    processed_count = 0
    for i, input_path in enumerate(input_files, 1):
        md_path = find_md_for_input_stem(input_path.stem)
        if not md_path:
            logger.info("⊙ 跳过（无对应 MD）: %s", get_relative_path(input_path))
            continue
        logger.info("[%d/%d] 开始生成 v2 排版 HTML：%s", i, len(input_files), get_relative_path(input_path))
        try:
            generate_pic_html_v2(md_path)
            processed_count += 1
        except Exception as e:
            logger.error("✗ 失败: %s - %s", get_relative_path(md_path), e, exc_info=True)

    logger.info("【Step4.1】 完成（v2 排版 HTML：共 %d 个）", processed_count)


if __name__ == "__main__":
    main()
