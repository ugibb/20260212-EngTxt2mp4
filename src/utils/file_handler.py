"""
文件处理工具模块
"""
import logging
from pathlib import Path
from typing import List, Optional

from src.utils.config import PROJECT_ROOT, normalize_filename

logger = logging.getLogger("file_uti")


def get_relative_path(file_path: Path) -> str:
    """
    将绝对路径转换为相对于项目根目录的相对路径
    
    Args:
        file_path: 文件路径（可以是绝对路径或相对路径）
        
    Returns:
        相对路径字符串
    """
    try:
        # 如果是相对路径，直接返回
        if not file_path.is_absolute():
            return str(file_path)
        
        # 转换为相对于项目根目录的路径
        try:
            relative_path = file_path.relative_to(PROJECT_ROOT)
            return str(relative_path)
        except ValueError:
            # 如果不在项目根目录下，返回原路径
            return str(file_path)
    except Exception:
        # 如果转换失败，返回原路径
        return str(file_path)


def read_text_file(file_path: Path, encoding: str = "utf-8") -> str:
    """
    读取文本文件内容
    
    Args:
        file_path: 文件路径
        encoding: 文件编码，默认utf-8
        
    Returns:
        文件内容字符串
        
    Raises:
        FileNotFoundError: 文件不存在
        UnicodeDecodeError: 编码错误
    """
    try:
        with open(file_path, "r", encoding=encoding) as f:
            content = f.read()
        # logger.info(f"成功读取文件: {get_relative_path(file_path)}")
        return content
    except FileNotFoundError:
        logger.error("✗ 文件不存在: %s", get_relative_path(file_path))
        raise
    except UnicodeDecodeError as e:
        logger.error("✗ 编码错误: %s - %s", get_relative_path(file_path), e)
        raise


def write_text_file(file_path: Path, content: str, encoding: str = "utf-8") -> None:
    """
    写入文本文件
    
    Args:
        file_path: 文件路径
        content: 文件内容
        encoding: 文件编码，默认utf-8
    """
    try:
        # 确保目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, "w", encoding=encoding) as f:
            f.write(content)
        # logger.info(f"成功写入文件: {get_relative_path(file_path)}")
    except Exception as e:
        logger.error("✗ 写入失败: %s - %s", get_relative_path(file_path), e)
        raise


def get_txt_files(directory: Path) -> List[Path]:
    """
    获取目录下所有txt文件
    
    Args:
        directory: 目录路径
        
    Returns:
        txt文件路径列表
    """
    if not directory.exists():
        logger.warning("⚠ 目录不存在: %s", get_relative_path(directory))
        return []
    
    txt_files = list(directory.glob("*.txt"))
    # logger.info(f"在「input」目录中找到待处理的txt文件：共 {len(txt_files)} 个")
    return sorted(txt_files)


def file_exists(file_path: Path) -> bool:
    """
    检查文件是否存在
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件是否存在
    """
    exists = file_path.exists() and file_path.is_file()
    if exists:
        logger.debug(f"文件已存在: {get_relative_path(file_path)}")
    return exists


def get_file_stem(file_path: Path) -> str:
    """
    获取文件名（不含扩展名）
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件名（不含扩展名）
    """
    return file_path.stem


def sanitize_filename(filename: str) -> str:
    """
    清理文件名，将空格和特殊字符替换为下划线
    
    Args:
        filename: 原始文件名
        
    Returns:
        清理后的文件名
    """
    import re
    # 将空格和特殊字符替换为下划线
    # 保留字母、数字、下划线、连字符、点号
    sanitized = re.sub(r'[^\w\-.]', '_', filename)
    # 将多个连续的下划线合并为一个
    sanitized = re.sub(r'_+', '_', sanitized)
    # 去除开头和结尾的下划线
    sanitized = sanitized.strip('_')
    return sanitized


def find_md_for_input_stem(input_stem: str) -> Optional[Path]:
    """根据 input 文件名 stem 查找对应的 output/02-vocabulary/*.md（兼容 sanitize 与 normalize 命名）。调用时从 config 读取目录，避免 run_all 切换 RUN_DATE 后仍用旧目录。"""
    from src.utils.config import _02_VOCABULARY_DIR
    vocab_dir = _02_VOCABULARY_DIR
    if not vocab_dir.exists():
        return None
    for s in (sanitize_filename(input_stem), normalize_filename(input_stem)):
        p = vocab_dir / f"{s}.md"
        if p.exists():
            return p
    return None
