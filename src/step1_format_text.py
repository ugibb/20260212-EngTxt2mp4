#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
步骤1：文本预处理
将 input 中的 txt 文件进行换行、去中文注释等处理，生成两份文件：
- output/01-txt/{文件名}.txt：完整格式化文本（含 ^ 等标记，供 step2 词汇提取）
- output/01-txt/{文件名}_voc.txt：核心词汇表（从 ^ 标记提取，每行一词）

_en.txt 由 step2 在生成 MD 后，从 output/02-vocabulary/*.md 段落结构统一生成

使用方法：
    python3 src/step1_format_text.py
"""
import sys
import re
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.config import INPUT_DIR, _01_TXT_DIR, SKIP_EXISTING_FILES, ensure_dirs, get_input_files_to_process
from src.utils.file_handler import read_text_file, write_text_file, file_exists, get_file_stem, sanitize_filename, get_relative_path
from src.utils.logger import setup_logger, SEP_LINE
from src.utils.text_processor import extract_bracketed_vocabulary

logger = setup_logger("step1")


def ensure_space_before_caret(text: str) -> str:
    """
    在 ^ 前增加一个空格（当 ^ 前为非空白字符时），避免人为将两个单词合并成一个。
    例如：our^exploration -> our ^exploration
    """
    if not text:
        return text
    return re.sub(r"(\S)\^", r"\1 ^", text)


def remove_all_chinese(text: str) -> str:
    """
    去除文本中的所有中文字符
    如果一行从汉字开始，删除整行
    如果一行中包含汉字，删除从第一个汉字开始到行尾的所有内容
    
    Args:
        text: 原始文本
        
    Returns:
        去除所有汉字后的文本
    """
    # 匹配中文字符模式
    # \u4e00-\u9fff 是中文字符范围
    # \u3000-\u303f 是中文标点符号范围
    # \uff00-\uffef 是全角字符范围
    chinese_pattern = r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]'
    
    # 按行处理，保留换行符
    lines = text.split('\n')
    processed_lines = []
    
    for line in lines:
        # 查找第一个中文字符的位置
        match = re.search(chinese_pattern, line)
        
        if match:
            # 如果找到中文字符
            chinese_start_pos = match.start()
            
            # 如果行首就是汉字（去除前导空格后），删除整行
            if chinese_start_pos == 0 or line[:chinese_start_pos].strip() == '':
                # 整行删除，跳过
                continue
            else:
                # 删除从第一个汉字开始到行尾的所有内容
                cleaned_line = line[:chinese_start_pos].rstrip()
        else:
            # 没有中文字符，保留原行
            cleaned_line = line
        
        # 清理行内多个连续空格
        cleaned_line = re.sub(r'[ \t]+', ' ', cleaned_line)
        cleaned_line = cleaned_line.strip()
        
        if cleaned_line:  # 只保留非空行
            processed_lines.append(cleaned_line)
    
    # 重新组合，保留换行符
    result = '\n'.join(processed_lines)
    
    return result


def remove_chinese_annotations(text: str) -> str:
    """
    去除文本中的中文注释（包括括号）
    
    Args:
        text: 原始文本
        
    Returns:
        去除中文注释后的文本
    """
    # 匹配括号内的中文内容，包括中文字符、标点符号等
    # 使用 [\u4e00-\u9fff] 匹配中文字符
    # 匹配格式：(中文内容)，包括括号前后的空格
    pattern = r'\s*\([^)]*[\u4e00-\u9fff][^)]*\)\s*'
    
    # 使用回调函数处理替换，确保保留必要的空格（避免单词被错误拼接）
    def replace_annotation(match):
        start, end = match.start(), match.end()
        before_char = text[start - 1 : start] if start > 0 else ""
        after_char = text[end : end + 1] if end < len(text) else ""
        after_rest = text[end:].lstrip()
        next_char = after_rest[0] if after_rest else ""

        if before_char and before_char.isalpha():
            # 括号前是字母：若括号后紧跟字母或 ^，保留空格避免拼接（如 mound (土堆) ^survey）
            if after_char.isalpha() or (next_char and (next_char == "^" or next_char.isalnum())):
                return " "
            if after_char in ".,;:!?)]":
                return ""
        if after_char and after_char.isalpha():
            return " "
        return ""
    
    # 从后往前替换，避免位置偏移
    matches = list(re.finditer(pattern, text))
    result = text
    for match in reversed(matches):
        replacement = replace_annotation(match)
        result = result[:match.start()] + replacement + result[match.end():]
    
    # 清理多个连续空格
    result = re.sub(r'\s+', ' ', result)
    # 清理标点前的多余空格
    result = re.sub(r'\s+([.,!?;:])', r'\1', result)
    # 清理标点后的多余空格（保留一个）
    result = re.sub(r'([.,!?;:])\s+', r'\1 ', result)
    
    return result.strip()


def format_text_with_line_breaks(text: str) -> str:
    """
    根据句号、感叹号、问号进行换行。
    已不再使用：分段严格遵循 input 原始 TXT 的换行，不再按标点拆句。
    """
    # 先去除所有汉字
    # text = remove_all_chinese(text)
    
    # 再去除中文注释（括号内的中文）
    text = remove_chinese_annotations(text)
    
    # 清理文本，将多个空格和换行符统一处理
    text = re.sub(r'\s+', ' ', text.strip())
    
    # 按照句号、感叹号、问号（中英文）进行分割
    # 使用正向先行断言，保留标点符号
    sentences = re.split(r'([.!?。！？]\s*)', text)
    
    # 过滤空字符串并重新组合句子
    formatted_sentences = []
    current_sentence = ""
    
    for item in sentences:
        if item.strip():
            current_sentence += item
            # 如果当前项以句号、感叹号、问号结尾，则作为一个完整的句子
            if re.search(r'[.!?。！？]\s*$', item):
                if current_sentence.strip():
                    formatted_sentences.append(current_sentence.strip())
                current_sentence = ""
    
    # 处理最后剩余的文本
    if current_sentence.strip():
        formatted_sentences.append(current_sentence.strip())
    
    # 将每个句子转换为一行
    return '\n'.join(formatted_sentences)


def format_text_file(input_file: Path) -> None:
    """
    处理单个文件
    
    Args:
        input_file: 输入文件路径
    """
    file_stem = get_file_stem(input_file)
    # 清理文件名，将空格和特殊字符替换为下划线
    sanitized_stem = sanitize_filename(file_stem)
    output_file = _01_TXT_DIR / f"{sanitized_stem}.txt"
    
    output_voc_file = _01_TXT_DIR / f"{sanitized_stem}_voc.txt"

    # 已经更新处理逻辑了（每次按天生成，运行时间可控），现在无需判断，每次直接重新处理
    # if SKIP_EXISTING_FILES and file_exists(output_file) and file_exists(output_voc_file):
    #     logger.info("⊙ 跳过执行（已存在）: %s", get_relative_path(output_file))
    #     return

    try:
        # logger.info("  读取: %s", get_relative_path(input_file))
        text_content = read_text_file(input_file)
        # Step1 开始处理时先对 ^ 前补空格，避免两词被人为疏忽，被合并成一个
        text_content = ensure_space_before_caret(text_content)

        if not text_content.strip():
            logger.warning("⊙ 跳过（文件为空）: %s", get_relative_path(input_file))
            return

        # 先去除所有汉字（按行处理，保留换行结构）
        # text_content = remove_all_chinese(text_content)
        
        # 提取标题（第一行），正文严格保留 input 原始分段（不再按句号拆句换行）
        lines = text_content.strip().split('\n')
        title = lines[0].strip() if lines else ""
        body_lines = lines[1:] if len(lines) > 1 else []
        # 仅做行内清理（去中文注释、多余空格），不新增换行
        body_cleaned = []
        for line in body_lines:
            line = line.strip()
            if line:
                line = remove_chinese_annotations(line)
                line = re.sub(r'\s+', ' ', line).strip()
                if line:
                    body_cleaned.append(line)
        formatted_body = '\n'.join(body_cleaned)
        
        # 组合标题和格式化后的正文（如果标题为空，则不添加标题行）
        if title:
            formatted_content = f"{title}\n\n{formatted_body}\n" if formatted_body else f"{title}\n"
        else:
            formatted_content = f"{formatted_body}\n" if formatted_body else ""
        
        # 保存完整版（供 step2 词汇提取）
        write_text_file(output_file, formatted_content)
        logger.info("✓ 完成文件输出: %s", get_relative_path(output_file))

        # _en.txt 由 step2 在生成 MD 后，从 output/02-vocabulary/*.md 段落结构统一生成

        # 生成核心词汇表：从 ^ 等标记提取，每行一词
        vocab_list = extract_bracketed_vocabulary(formatted_content)
        if vocab_list:
            voc_content = "\n".join(vocab_list) + "\n"
            write_text_file(output_voc_file, voc_content)
            logger.info("✓ 完成文件输出: %s", get_relative_path(output_voc_file))

    except Exception as e:
        logger.error("✗ 失败: %s - %s", get_relative_path(input_file), e, exc_info=True)


def main():
    """主函数"""
    ensure_dirs()
    # logger.info("%s", SEP_LINE)
    # logger.info("[Step1] 文本预处理")
    # logger.info("%s", SEP_LINE)

    txt_files = get_input_files_to_process()
    if not txt_files:
        logger.warning("⚠ 未找到 txt 文件: %s", get_relative_path(INPUT_DIR))
        return

    logger.info("待处理input目录下的txt文件：共 %d 个", len(txt_files))
    for i, txt_file in enumerate(txt_files, 1):
        logger.info("[%d/%d] 开始文本预处理（格式化正文、换行...）：%s", i, len(txt_files), get_relative_path(txt_file))
        try:
            format_text_file(txt_file)
        except Exception as e:
            logger.error("✗ 失败: %s - %s", get_relative_path(txt_file), e, exc_info=True)

    logger.info("【Step1】 完成（文本预处理（格式化正文、换行...）：共 %d 个文件）", len(txt_files))


if __name__ == "__main__":
    main()
