#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
步骤2： 提取核心词汇和词组
从output/01-txt文件夹中的txt文件提取核心词汇和词组，保存到output/02-vocabulary/

使用模型： kimi-k2.5（Kimi最强文本处理模型）

使用方法： 
    python3 src/step2_extract_vocab.py
    或
    ./run_step.sh step2_extract_vocab.py
"""
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.config import INPUT_DIR, _01_TXT_DIR, _02_VOCABULARY_DIR, ensure_dirs, get_input_files_to_process, normalize_filename
from src.utils.file_handler import read_text_file, write_text_file, get_file_stem, sanitize_filename, get_relative_path
from src.utils.llm_client import LLMClient
import re
from src.utils.text_processor import (
    parse_paragraphs_from_txt,
    parse_paragraphs_from_markdown,
    extract_bracketed_vocabulary,
)
from src.utils.voice_role import strip_leading_role_prefix
from src.utils.logger import setup_logger, SEP_LINE

logger = setup_logger("step2")


def _build_paragraph_section(expected_paragraphs: list[dict], llm_paragraphs: list[dict] | None = None) -> str:
    """
    根据 expected_paragraphs 构建「## 段落结构」整段内容。
    llm_paragraphs 若提供且段数匹配，则每段 chinese 优先用 LLM 的，否则用 expected 的。
    """
    expected_count = len(expected_paragraphs)
    llm_count = len(llm_paragraphs) if llm_paragraphs else 0
    new_section_lines = [f"## 段落结构（共 {expected_count} 段）", ""]
    for idx, para in enumerate(expected_paragraphs, 1):
        eng = (para.get("english") or "").strip()
        stripped, _ = strip_leading_role_prefix(eng)
        eng = stripped if stripped else eng
        ch = (para.get("chinese") or "").strip()
        if llm_paragraphs and idx <= llm_count and llm_paragraphs[idx - 1].get("chinese"):
            ch = (llm_paragraphs[idx - 1].get("chinese") or "").strip()
        role = para.get("role") or "narration"
        new_section_lines.append(f"### 段落{idx}")
        new_section_lines.append(f"- **english**: {eng}")
        new_section_lines.append(f"- **chinese**: {ch}")
        new_section_lines.append(f"- **role**: {role}")
        new_section_lines.append("")
    return "\n".join(new_section_lines).rstrip()


def _ensure_paragraph_structure(markdown_content: str, expected_paragraphs: list[dict]) -> str:
    """
    若 LLM 返回的「段落结构」段数与 01-txt 解析结果不一致（如合并成 2 段），
    用 expected_paragraphs 重写该段，保证段数与每段 english 与 01-txt 一致。
    chinese：若 LLM 段数正确则沿用 LLM 的中文，否则用 expected 中的中文（常为空）。
    若 LLM 因 token 截断未输出「## 段落结构」，则用 expected_paragraphs 直接追加该段（方案 A）。
    """
    if not expected_paragraphs:
        return markdown_content

    # 截断导致整段缺失：用 01-txt 的段落信息直接追加，保证 Step3 不因「MD 无段落结构」跳过
    if "## 段落结构" not in markdown_content:
        new_section = _build_paragraph_section(expected_paragraphs, llm_paragraphs=None)
        return markdown_content.rstrip() + "\n\n" + new_section + "\n"

    llm_paragraphs = parse_paragraphs_from_markdown(markdown_content)
    new_section = _build_paragraph_section(expected_paragraphs, llm_paragraphs)

    # 替换：从 "## 段落结构" 到下一个 "## " 或文件末尾
    parts = re.split(r"\n## 段落结构\b", markdown_content, maxsplit=1)
    if len(parts) < 2:
        return markdown_content
    before = parts[0]
    rest = parts[1]
    rest_after_section = re.sub(r"^[^\n]*\n?", "", rest, count=1)
    next_h2 = re.search(r"\n##\s+", rest_after_section)
    if next_h2:
        after = "\n" + rest_after_section[next_h2.start() :]
    else:
        after = ""

    return before + "\n" + new_section + after


def _fix_existing_md_paragraph_structure(txt_path: Path, md_path: Path) -> None:
    """对已存在的 MD 根据 01-txt 修正「段落结构」段数，使与 01-txt 一致（不调用 LLM）。"""
    try:
        text_content = read_text_file(txt_path)
        if not text_content.strip():
            return
        paragraphs = parse_paragraphs_from_txt(text_content)
        if not paragraphs:
            return
        md_content = read_text_file(md_path)
        fixed = _ensure_paragraph_structure(md_content, paragraphs)
        if fixed != md_content:
            write_text_file(md_path, fixed)
            logger.info("✓ 已修正段落结构（与 01-txt 一致）: %s", get_relative_path(md_path))
    except Exception as e:
        logger.debug("修正段落结构时忽略: %s - %s", get_relative_path(md_path), e)


def _find_existing_vocab(stem: str) -> Path | None:
    """检查 output/02-vocabulary 中是否存在对应 md（兼容 sanitize 与 normalize 两种命名），存在则返回路径"""
    for s in (sanitize_filename(stem), normalize_filename(stem)):
        p = _02_VOCABULARY_DIR / f"{s}.md"
        if p.exists():
            return p
    return None


def extract_vocabulary_from_file(input_file: Path) -> None:
    """
    从单个文件提取词汇
    
    Args:
        input_file: 输入文件路径
    """
    file_stem = get_file_stem(input_file)
    sanitized_stem = sanitize_filename(file_stem)
    output_file = _02_VOCABULARY_DIR / f"{sanitized_stem}.md"
    
    # 调用 LLM 前判断 output/02-vocabulary/{文件名}.md 是否存在，存在则跳过，避免不必要的 LLM 费用
    existing = _find_existing_vocab(file_stem)
    if existing:
        logger.info("⊙ 跳过（已存在）: %s", get_relative_path(existing))
        return

    try:
        # logger.info("  读取: %s", get_relative_path(input_file))
        text_content = read_text_file(input_file)
        
        if not text_content.strip():
            logger.warning("⊙ 跳过（文件为空）: %s", get_relative_path(input_file))
            return

        paragraphs = parse_paragraphs_from_txt(text_content)
        if not paragraphs:
            logger.warning("⊙ 跳过（无段落结构）: %s", get_relative_path(input_file))
            return
        
        # 将段落结构格式化，添加到文本内容中供LLM参考
        # LLM会直接使用这个段落结构，不需要重新分段
        paragraph_info = "\n\n---\n## 已识别的段落结构（共{}段，请直接使用，不要重新分段）： \n".format(len(paragraphs))
        for idx, para in enumerate(paragraphs, 1):
            paragraph_info += f"\n### 段落{idx}\n"
            paragraph_info += f"- **英文**: {para['english']}\n"
            if para['chinese']:
                paragraph_info += f"- **中文**: {para['chinese']}\n"
            else:
                paragraph_info += f"- **中文**: （该段落没有中文翻译，请生成）\n"
        
        # 从短文中提取核心词汇标记（「」、[]、【】、{}、^ 前缀）
        bracketed_terms = extract_bracketed_vocabulary(text_content)
        if bracketed_terms:
            bracket_note = (
                "\n\n---\n【以下词/短语在短文中以「」、[]、【】、{} 或 ^ 前缀标注，请全部列入核心词汇并输出完整词条（音标、词义、词根词缀等）】：\n"
                + ", ".join(bracketed_terms)
            )
            text_with_paragraphs = text_content + bracket_note + paragraph_info
        else:
            text_with_paragraphs = text_content + paragraph_info

        # logger.info("  调用 LLM 提取词汇，解析段落、提取词汇标记...")
        llm_client = LLMClient()
        vocabulary_markdown = llm_client.extract_vocabulary(text_with_paragraphs, file_name=file_stem)

        # 强制段落结构与 01-txt 一致：若 LLM 合并了段落，用我们解析的 paragraphs 重写「段落结构」段
        vocabulary_markdown = _ensure_paragraph_structure(vocabulary_markdown, paragraphs)

        write_text_file(output_file, vocabulary_markdown)
        logger.info("✓ 完成: %s", get_relative_path(output_file))

    except Exception as e:
        logger.error("✗ 失败: %s - %s", get_relative_path(input_file), e, exc_info=True)


def main():
    """主函数"""
    ensure_dirs()
    # logger.info("%s", SEP_LINE)
    # logger.info("[Step2] 词汇提取（调用LLM提取词汇）")
    # logger.info("%s", SEP_LINE)

    # 根据 input 中的 txt 文件，找到对应的 output/01-txt/{文件名}.txt（避免按后缀排除产生误判）
    # 仅处理 output/02-vocabulary/{文件名}.md 不存在的文件，避免不必要的 LLM 调用费用
    txt_files = []
    for input_file in get_input_files_to_process():
        stem = sanitize_filename(input_file.stem)
        txt_path = _01_TXT_DIR / f"{stem}.txt"
        existing_vocab = _find_existing_vocab(input_file.stem)
        if not txt_path.exists():
            logger.warning("⊙ 跳过（01-txt 中无对应文件）: %s -> %s", get_relative_path(input_file), get_relative_path(txt_path))
        elif existing_vocab:
            logger.info("⊙ 词汇文件已存在，跳过执行LLM调用: %s", get_relative_path(existing_vocab))
            # 仍对已有 MD 执行段落结构修正，使段数与 01-txt 一致
            _fix_existing_md_paragraph_structure(txt_path, existing_vocab)
        else:
            txt_files.append(txt_path)
    if not txt_files:
        logger.info("⚠ 暂无需要调用LLM处理的 txt 文件: input=%s, output=%s", get_relative_path(INPUT_DIR), get_relative_path(_01_TXT_DIR))
    else:
        logger.info("待处理input目录下的txt文件：共 %d 个", len(txt_files))
        for i, txt_file in enumerate(txt_files, 1):
            logger.info("[%d/%d]开始调用LLM处理： %s", i, len(txt_files), get_relative_path(txt_file))
            try:
                extract_vocabulary_from_file(txt_file)
            except Exception as e:
                logger.error("✗ 失败: %s - %s", get_relative_path(txt_file), e, exc_info=True)

    logger.info("【Step2】 完成（input目录下的txt文件：共 %d 个）", len(txt_files))


if __name__ == "__main__":
    main()
