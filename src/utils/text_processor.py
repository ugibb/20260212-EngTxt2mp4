"""
文本处理工具模块
"""
import re
import html
import logging
from typing import List, Dict, Tuple

from src.utils.voice_role import parse_role_tag, normalize_role, strip_leading_role_prefix, NARRATION

logger = logging.getLogger("text_uti")


def clean_text(text: str) -> str:
    """
    清理文本内容
    
    Args:
        text: 原始文本
        
    Returns:
        清理后的文本
    """
    # 移除多余的空白字符
    text = re.sub(r'\s+', ' ', text)
    # 移除首尾空白
    text = text.strip()
    return text


def remove_bracket_markers(text: str) -> str:
    """
    从文本中移除词汇标记符（「」、[]、【】、{}、^ 前缀），保留内容。
    用于统一清理 english 字段中的词汇标记，便于排版与展示。
    """
    if not text:
        return text
    for char in ['「', '」', '【', '】', '[', ']', '{', '}']:
        text = text.replace(char, '')
    # 移除 ^ 前缀（^word 中的 ^）
    text = re.sub(r'\^(?=[a-zA-Z])', '', text)
    return text


def ensure_space_after_punctuation(text: str) -> str:
    """
    在「字母/数字 + 标点 + 字母/数字」的标点后补空格，使 MD 与 TTS 分词一致，便于 LRC 对齐。
    例如：myths,pointed -> myths, pointed；word.Next -> word. Next
    """
    if not text:
        return text
    # 标点后若紧跟字母/数字则插入空格（避免 MD 出现 word,word 而 LRC 为 word + word）
    return re.sub(r"([,.;:!?])(?=[a-zA-Z0-9])", r"\1 ", text)


def parse_paragraphs_from_txt(text_content: str) -> List[Dict[str, str]]:
    """
    从txt文件中解析段落结构（英文行和中文行交替出现）。
    支持 TTS 角色标记：单独一行 [男]/[M]/[female] 等，表示紧跟其后的该段使用该角色语音。
    
    格式说明：
    - 英文行和中文行交替出现
    - 连续的英文行组成一个段落的english部分
    - 紧跟在英文行后面的中文行是该段落的chinese部分
    - 空行会被忽略
    - 单独一行的角色标记 [角色] 仅影响下一段，不进入段落内容
    
    Returns:
        段落列表，每项含 english、chinese，以及可选的 role（默认 narration）
    """
    paragraphs = []
    lines = text_content.strip().split('\n')

    # 中文字符范围；仅当一行中中文「足够多」才视为中文行（避免 firework爆 等夹杂单字触发交替逻辑）
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]')

    def _is_chinese_line(line: str) -> bool:
        line = line.strip()
        if not line:
            return False
        ch_chars = chinese_pattern.findall(line)
        # 至少 3 个中文字符才视为中文行，否则按英文行处理（严格按 input 分段）
        return len(ch_chars) >= 3

    # 角色标记：当前「下一段」要使用的角色，解析到段落后清空
    pending_role: str = NARRATION

    # 先检查整个文件是否有「中文行」（按上述规则）
    has_any_chinese = any(_is_chinese_line(line) for line in lines if line.strip())

    # 如果没有中文行，按行分割：每行英文作为一个段落（角色行单独识别）
    if not has_any_chinese:
        for line in lines:
            line = line.strip()
            if not line:
                continue
            role = parse_role_tag(line)
            if role is not None:
                pending_role = role
                continue
            # 段首 [M]:、[男]: 等前缀剥离
            stripped, prefix_role = strip_leading_role_prefix(line)
            if prefix_role is not None:
                pending_role = prefix_role
            para = {'english': stripped if stripped else line, 'chinese': '', 'role': pending_role}
            paragraphs.append(para)
            pending_role = NARRATION
        logger.debug("段落解析完成: %d 段（按行分割）", len(paragraphs))
        return paragraphs

    # 如果有中文行，使用交替解析逻辑，并识别角色行
    current_english_lines = []
    current_chinese = ''

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # 跳过空行
        if not line:
            i += 1
            continue

        # 单独一行的角色标记：作用于下一段，不进入内容
        role = parse_role_tag(line)
        if role is not None:
            pending_role = role
            i += 1
            continue

        # 判断是否为中文行（至少 3 个中文字符）
        has_chinese = _is_chinese_line(line)

        if has_chinese:
            # 中文行：保存为当前段落的中文部分
            current_chinese = line
            i += 1

            # 如果已有英文内容，保存段落（带当前 pending_role）
            if current_english_lines:
                paragraph = {
                    'english': '\n'.join(current_english_lines),
                    'chinese': current_chinese,
                    'role': pending_role,
                }
                paragraphs.append(paragraph)
                current_english_lines = []
                current_chinese = ''
                pending_role = NARRATION
        else:
            # 英文行
            if current_english_lines and current_chinese:
                # 先保存当前段落（带当前 pending_role；下一段会再取新的标记）
                paragraph = {
                    'english': '\n'.join(current_english_lines),
                    'chinese': current_chinese,
                    'role': pending_role,
                }
                paragraphs.append(paragraph)
                current_english_lines = []
                current_chinese = ''
                pending_role = NARRATION

            # 段首 [M]:、[男]: 等前缀剥离，避免进入 english 与词汇 [] 混淆
            stripped, prefix_role = strip_leading_role_prefix(line)
            if prefix_role is not None:
                pending_role = prefix_role
            if stripped:
                current_english_lines.append(stripped)
            i += 1

    # 处理最后一个段落（可能没有中文）
    if current_english_lines:
        paragraph = {
            'english': '\n'.join(current_english_lines),
            'chinese': current_chinese,
            'role': pending_role,
        }
        paragraphs.append(paragraph)

    logger.debug("段落解析完成: %d 段", len(paragraphs))
    return paragraphs


def extract_bracketed_vocabulary(text: str) -> List[str]:
    """
    从短文中提取核心词汇标记，支持：
    - 「」、[]、【】、{} 括起来的词或短语
    - ^ 前缀标记的词或短语（如 ^inhabitant、^make sense of）

    Args:
        text: 短文正文内容

    Returns:
        去重后的词/短语列表，保持首次出现顺序
    """
    if not text or not text.strip():
        return []
    seen = set()
    result: List[str] = []
    # 「」、[]、【】、{} 四种括号内容
    patterns = [
        re.compile(r'「([^」]+)」'),
        re.compile(r'\[([^\]]+)\]'),
        re.compile(r'【([^】]+)】'),
        re.compile(r'\{([^}]+)\}'),
        # ^ 前缀：^word 或 ^phrase (中文)，遇 " (" 则匹配整短语，否则匹配单词
        re.compile(r'\^([a-zA-Z]+(?:\'[a-zA-Z]+)?(?:\s+[a-zA-Z]+(?:\'[a-zA-Z]+)?)*?)(?=\s*\()'),
        re.compile(r'\^([a-zA-Z]+(?:\'[a-zA-Z]+)?)(?=[\s.,;:!?\n]|$)'),
    ]
    for pattern in patterns:
        for m in pattern.finditer(text):
            term = m.group(1).strip()
            if not term or term in seen:
                continue
            # 若 term 是已加入短语的子串，则跳过（避免 ^make sense of 同时加入 make）
            if any(" " in r and term in r for r in result):
                continue
            seen.add(term)
            result.append(term)
    return result


def escape_html(text: str) -> str:
    """
    HTML转义
    
    Args:
        text: 原始文本
        
    Returns:
        转义后的文本
    """
    return html.escape(text)


def parse_title_from_markdown(markdown_content: str) -> str:
    """
    从Markdown文件中解析标题（文档标题）
    
    Args:
        markdown_content: Markdown格式的内容
        
    Returns:
        标题字符串，如果未找到则返回空字符串
    """
    try:
        # 查找第一个一级标题（# 开头的行）
        lines = markdown_content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('# ') and len(line) > 2:
                # 提取标题文本（去掉 # 和空格）
                title = line[2:].strip()
                return title
        return ""
    except Exception as e:
        logger.error("✗ 解析标题失败: %s", e)
        return ""


def parse_markdown_vocabulary(markdown_content: str) -> Dict[str, List[Dict]]:
    """
    解析Markdown格式的词汇提取结果
    
    Args:
        markdown_content: Markdown格式的内容
        
    Returns:
        包含核心词汇和核心词组的字典
        {
            'vocabulary': [
                {
                    'word': '单词',
                    'phonetic': '音标',
                    'pos': '词性',
                    'current_meaning': '单词在当前文中的词义',
                    'all_meanings': '单词所有可能的中文词义',
                    'root': '词根词缀',
                    'synonyms': '近义词',
                    'derivatives': '派生词',
                    'collocations': '常见搭配',
                    'examples': ['例句1', '例句2', ...]
                },
                ...
            ],
            'phrases': [
                {
                    'phrase': '词组',
                    'meaning': '中文释义'
                },
                ...
            ]
        }
    """
    result = {
        'vocabulary': [],
        'phrases': []
    }
    
    try:
        # 分割核心词汇和核心词组部分
        vocab_section = ""
        phrase_section = ""
        
        if "## 核心词汇" in markdown_content:
            parts = markdown_content.split("## 核心词汇", 1)
            if len(parts) > 1:
                remaining = parts[1]
                # 移除标题行的剩余部分（如"（共 4 个）"）和换行符
                first_newline = remaining.find('\n')
                if first_newline >= 0:
                    remaining = remaining[first_newline + 1:]
                else:
                    remaining = remaining.lstrip()
                
                # 查找下一个二级标题的位置（可能是"## 核心词组"或"## 段落结构"）
                next_section_match = re.search(r'\n##\s+', remaining)
                
                if "## 核心词组" in markdown_content:
                    # 检查下一个二级标题是否是"## 核心词组"
                    phrase_match = re.search(r'\n##\s+核心词组', remaining)
                    if phrase_match:
                        # 分割词汇和词组
                        vocab_section = remaining[:phrase_match.start()]
                        phrase_remaining = remaining[phrase_match.end():]
                        # 移除词组标题行的剩余部分（如"（共 7 组）"）
                        phrase_first_newline = phrase_remaining.find('\n')
                        if phrase_first_newline >= 0:
                            phrase_remaining = phrase_remaining[phrase_first_newline + 1:]
                        else:
                            phrase_remaining = phrase_remaining.lstrip()
                        # 如果后面有段落结构，只取到段落结构之前
                        paragraph_match = re.search(r'\n##\s+段落结构', phrase_remaining)
                        if paragraph_match:
                            phrase_section = phrase_remaining[:paragraph_match.start()]
                        else:
                            phrase_section = phrase_remaining
                    else:
                        # 如果没有找到核心词组，但有其他二级标题，只取到那里
                        if next_section_match:
                            vocab_section = remaining[:next_section_match.start()]
                        else:
                            vocab_section = remaining
                else:
                    # 如果没有核心词组部分，只取到下一个二级标题之前
                    if next_section_match:
                        vocab_section = remaining[:next_section_match.start()]
                    else:
                        vocab_section = remaining
        
        # 解析核心词汇
        if vocab_section:
            vocab_items = re.split(r'###\s+', vocab_section)
            for item in vocab_items:
                if not item.strip():
                    continue
                
                vocab_dict = {}
                lines = item.strip().split('\n')
                current_word = None
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # 提取单词（第一行通常是单词）
                    # 跳过包含"共"、"个"等字符的标题行
                    if not current_word and line and not line.startswith('-') and not line.startswith('*'):
                        # 过滤掉标题行（如"（共 4 个）"）
                        if '共' in line and '个' in line:
                            continue
                        current_word = line.strip('#').strip()
                        vocab_dict['word'] = current_word
                        continue
                    
                    # 提取各个字段（移除行首的"-"和markdown格式）
                    # 'current_meaning': '单词在当前文中的词义',
                    # 'all_meanings': '单词所有可能的中文词义',

                    if '**音标**' in line or '音标' in line:
                        vocab_dict['phonetic'] = re.sub(r'^[-*]\s*', '', re.sub(r'\*\*音标\*\*[:：]?\s*', '', line)).strip()
                    elif '**词性**' in line or '词性' in line:
                        vocab_dict['pos'] = re.sub(r'^[-*]\s*', '', re.sub(r'\*\*词性\*\*[:：]?\s*', '', line)).strip()
                    elif '**文中词义**' in line or '文中词义' in line:
                        vocab_dict['current_meaning'] = re.sub(r'^[-*]\s*', '', re.sub(r'\*\*文中词义\*\*[:：]?\s*', '', line)).strip()

                    elif '**中文词义**' in line or '中文词义' in line:
                        vocab_dict['all_meanings'] = re.sub(r'^[-*]\s*', '', re.sub(r'\*\*中文词义\*\*[:：]?\s*', '', line)).strip()





                    elif '**词根词缀**' in line or '词根词缀' in line:
                        vocab_dict['root'] = re.sub(r'^[-*]\s*', '', re.sub(r'\*\*词根词缀\*\*[:：]?\s*', '', line)).strip()
                    elif '**近义词**' in line or '近义词' in line:
                        vocab_dict['synonyms'] = re.sub(r'^[-*]\s*', '', re.sub(r'\*\*近义词\*\*[:：]?\s*', '', line)).strip()
                    elif '**派生词**' in line or '派生词' in line:
                        vocab_dict['derivatives'] = re.sub(r'^[-*]\s*', '', re.sub(r'\*\*派生词\*\*[:：]?\s*', '', line)).strip()
                    elif '**常见搭配**' in line or '常见搭配' in line:
                        vocab_dict['collocations'] = re.sub(r'^[-*]\s*', '', re.sub(r'\*\*常见搭配\*\*[:：]?\s*', '', line)).strip()
                    elif '**例句**' in line or '例句' in line:
                        vocab_dict['examples'] = []
                    elif vocab_dict.get('examples') is not None and (line.startswith(('1.', '2.', '3.', '4.', '5.', '-', '*'))):
                        example = re.sub(r'^\d+\.\s*[-*]?\s*', '', line).strip()
                        if example:
                            vocab_dict['examples'].append(example)
                
                if vocab_dict.get('word'):
                    result['vocabulary'].append(vocab_dict)
        
        # 解析核心词组
        if phrase_section:
            phrase_lines = phrase_section.split('\n')
            for line in phrase_lines:
                line = line.strip()
                if not line:
                    continue
                
                # 跳过段落结构中的内容（包含"**english**"或"**chinese**"的行）
                if '**english**' in line.lower() or '**chinese**' in line.lower():
                    continue
                
                # 只匹配数字开头的词组格式（如"1. **around the corner**：..."）
                if line[0].isdigit():
                    # 提取词组和释义
                    match = re.match(r'^\d+\.\s*\*\*(.+?)\*\*[:：]\s*(.+)$', line)
                    if match:
                        phrase = match.group(1).strip()
                        meaning = match.group(2).strip()
                        result['phrases'].append({
                            'phrase': phrase,
                            'meaning': meaning
                        })
        
        logger.debug("词汇解析: %d 词, %d 词组", len(result["vocabulary"]), len(result["phrases"]))
        
    except Exception as e:
        logger.error("✗ 解析 Markdown 失败: %s", e)
    
    return result


def parse_paragraphs_from_markdown(markdown_content: str) -> List[Dict[str, str]]:
    """
    从Markdown文件中解析段落结构
    
    Args:
        markdown_content: Markdown格式的内容
        
    Returns:
        段落列表，每个段落包含 english 和 chinese 字段
        [
            {
                'english': '英文内容（可能多行）',
                'chinese': '中文翻译'
            },
            ...
        ]
    """
    paragraphs = []
    
    try:
        # 查找"段落结构"部分
        if "## 段落结构" not in markdown_content:
            logger.warning("⚠ 未找到段落结构")
            return paragraphs
        
        # 提取段落结构部分（到下一个##或文件结尾）
        # 使用split方法，更可靠
        if "## 段落结构" not in markdown_content:
            logger.warning("⚠ 未找到段落结构")
            return paragraphs
        
        # 使用split分割，获取"## 段落结构"之后的所有内容
        parts = markdown_content.split("## 段落结构", 1)
        if len(parts) < 2:
            logger.warning("⚠ 无法分割段落结构")
            return paragraphs
        
        paragraph_section = parts[1]
        
        # 移除标题行的剩余部分（如"（共 15 段）"）和换行符
        # 找到第一个换行符之后的内容
        first_newline = paragraph_section.find('\n')
        if first_newline >= 0:
            paragraph_section = paragraph_section[first_newline + 1:]
        else:
            paragraph_section = paragraph_section.lstrip()
        
        # 如果后面还有其他章节，只取到下一个二级标题（##）之前
        # 使用正则匹配独立的二级标题（换行符+##+空格），避免匹配到三级标题（###）
        next_section_match = re.search(r'\n##\s+', paragraph_section)
        if next_section_match:
            paragraph_section = paragraph_section[:next_section_match.start()]
        
        logger.debug("段落部分长度: %d 字符", len(paragraph_section))
        # logger.info(f"段落结构部分前500字符:\n{repr(paragraph_section[:500])}")
        
        # 先检查是否有"### 段落"标题（支持 "段落1" 或 "段落 1" 格式）
        simple_matches = re.findall(r'###\s+段落\s*\d+', paragraph_section)
        # logger.info(f"找到 {len(simple_matches)} 个'### 段落'标题: {simple_matches[:5]}...")
        
        # 使用正则表达式查找所有段落块
        # 匹配格式：### 段落N 后面跟着的内容，直到下一个 ### 段落 或文件结尾（支持 "段落 1" 有空格）
        # 使用更灵活的正则：允许空行，使用非贪婪匹配
        paragraph_pattern = r'###\s+段落\s*\d+\s*\n(.*?)(?=\n###\s+段落\s*\d+|$)'
        paragraph_matches = list(re.finditer(paragraph_pattern, paragraph_section, re.DOTALL))
        
        # logger.info(f"使用正则表达式 '{paragraph_pattern}' 找到 {len(paragraph_matches)} 个段落匹配")
        
        if not paragraph_matches and simple_matches:
            logger.debug("主正则未匹配，尝试备用方式")
            # 尝试另一种匹配方式：匹配整个段落块（包括标题），不要求换行
            alt_pattern = r'###\s+段落\s*\d+\s*\n(.*?)(?=\n###\s+段落\s*\d+|$)'
            # 尝试更宽松的匹配：不要求换行
            alt_pattern2 = r'###\s+段落\s*\d+[^\n]*\n(.*?)(?=###\s+段落\s*\d+|$)'
            alt_matches = list(re.finditer(alt_pattern2, paragraph_section, re.DOTALL))
            logger.debug("备用模式找到 %d 个匹配", len(alt_matches))
            
            if alt_matches:
                logger.debug("使用备用模式解析")
                paragraph_matches = alt_matches
            else:
                # 最后尝试：手动分割
                logger.debug("尝试手动分割")
                # 使用findall找到所有段落标题的位置
                paragraph_titles = list(re.finditer(r'###\s+段落\s*\d+', paragraph_section))
                logger.debug("找到 %d 个段落标题", len(paragraph_titles))
                
                if paragraph_titles:
                    # 直接提取每个段落的内容并解析
                    for i, title_match in enumerate(paragraph_titles):
                        start_pos = title_match.end()
                        # 找到下一个段落标题的位置，或者文件结尾
                        if i + 1 < len(paragraph_titles):
                            end_pos = paragraph_titles[i + 1].start()
                        else:
                            end_pos = len(paragraph_section)
                        
                        # 提取内容（不包括标题）
                        block = paragraph_section[start_pos:end_pos].strip()
                        if not block:
                            continue
                        
                        paragraph_dict = {}
                        
                        # 提取 english 字段
                        english_match = re.search(
                            r'[-*]\s*\*\*english\*\*[:：]\s*(.+?)(?=\n[-*]\s*\*\*chinese\*\*|\n\n|$)', 
                            block, 
                            re.DOTALL | re.IGNORECASE
                        )
                        if english_match:
                            english_content = english_match.group(1).strip()
                            english_content = re.sub(r'\n\s+', '\n', english_content)
                            stripped, _ = strip_leading_role_prefix(english_content)
                            paragraph_dict['english'] = stripped if stripped else english_content
                        
                        # 提取 chinese 字段
                        # 止于下一字段（- **xxx**）、双换行或结尾，避免把 - **role**: 等纳入 chinese
                        chinese_match = re.search(
                            r'[-*]\s*\*\*chinese\*\*[:：]\s*(.+?)(?=\n[-*]\s*\*\*|\n\n|$)',
                            block,
                            re.DOTALL | re.IGNORECASE
                        )
                        if chinese_match:
                            chinese_content = chinese_match.group(1).strip()
                            chinese_content = re.sub(r'\n\s+', ' ', chinese_content)
                            chinese_content = re.sub(r'\([^)]*\)', '', chinese_content)
                            chinese_content = chinese_content.strip()
                            paragraph_dict['chinese'] = chinese_content
                        # 提取 role 字段（TTS 角色，可选）；同一段多个 - **role**: 时取最后一个
                        role_matches = list(re.finditer(
                            r'[-*]\s*\*\*role\*\*[:：]\s*(\S+)',
                            block,
                            re.IGNORECASE
                        ))
                        if role_matches:
                            paragraph_dict['role'] = normalize_role(role_matches[-1].group(1).strip())
                        else:
                            paragraph_dict['role'] = NARRATION

                        # 如果成功提取了english字段，添加到列表
                        if paragraph_dict.get('english'):
                            if 'chinese' not in paragraph_dict:
                                paragraph_dict['chinese'] = ''
                            paragraphs.append(paragraph_dict)
                            logger.debug(f"手动提取段落 {i+1}，内容长度: {len(block)}")
                    
                    logger.debug("手动分割: %d 段", len(paragraphs))
                    # 如果手动分割成功，直接返回
                    if paragraphs:
                        logger.debug("段落解析完成: %d 段", len(paragraphs))
                        return paragraphs
        
        for idx, match in enumerate(paragraph_matches, 1):
            # 获取捕获组1的内容（段落正文，不包括标题）
            try:
                block = match.group(1).strip()
                logger.debug(f"段落 {idx} 使用group(1)，内容长度: {len(block)}")
            except (IndexError, AttributeError):
                block = match.group(0).strip()
                # 移除段落标题行
                block = re.sub(r'^###\s+段落\s*\d+\s*\n', '', block, flags=re.MULTILINE).strip()
                logger.debug(f"段落 {idx} 使用group(0)并移除标题，内容长度: {len(block)}")
            
            if not block:
                logger.debug("段落 %d 内容为空，跳过", idx)
                continue
            
            logger.debug(f"段落 {idx} 原始block前200字符:\n{block[:200]}")
            
            paragraph_dict = {}
            
            # 提取 english 字段
            # 匹配格式：- **english**: 内容
            english_match = re.search(
                r'[-*]\s*\*\*english\*\*[:：]\s*(.+?)(?=\n[-*]\s*\*\*chinese\*\*|\n\n|$)', 
                block, 
                re.DOTALL | re.IGNORECASE
            )
            if english_match:
                english_content = english_match.group(1).strip()
                # 清理可能的markdown格式，保留换行
                english_content = re.sub(r'\n\s+', '\n', english_content)
                stripped, _ = strip_leading_role_prefix(english_content)
                paragraph_dict['english'] = stripped if stripped else english_content
                logger.debug(f"段落 {idx} 提取到英文: {english_content[:50]}...")
            else:
                logger.debug("段落 %d 未找到英文", idx)
                logger.debug(f"段落 {idx} 尝试匹配的正则: r'[-*]\\s*\\*\\*english\\*\\*[:：]\\s*(.+?)(?=\\n[-*]\\s*\\*\\*chinese\\*\\*|\\n\\n|$)'")
            
            # 提取 chinese 字段
            # 匹配格式：- **chinese**: 内容；止于下一字段（- **role** 等）、双换行或结尾
            chinese_match = re.search(
                r'[-*]\s*\*\*chinese\*\*[:：]\s*(.+?)(?=\n[-*]\s*\*\*|\n\n|$)',
                block,
                re.DOTALL | re.IGNORECASE
            )
            if chinese_match:
                chinese_content = chinese_match.group(1).strip()
                # 清理可能的markdown格式和注释
                chinese_content = re.sub(r'\n\s+', ' ', chinese_content)
                # 移除括号注释（如 "(使用原文中已有的中文翻译)"）
                chinese_content = re.sub(r'\([^)]*\)', '', chinese_content)
                chinese_content = chinese_content.strip()
                paragraph_dict['chinese'] = chinese_content
                logger.debug(f"段落 {idx} 提取到中文: {chinese_content[:50]}...")
            else:
                logger.debug(f"段落 {idx} 未找到中文内容")

            # 提取 role 字段（TTS 角色，可选）；同一段多个 - **role**: 时取最后一个
            role_matches = list(re.finditer(
                r'[-*]\s*\*\*role\*\*[:：]\s*(\S+)',
                block,
                re.IGNORECASE
            ))
            if role_matches:
                paragraph_dict['role'] = normalize_role(role_matches[-1].group(1).strip())
            else:
                paragraph_dict['role'] = NARRATION

            # 如果成功提取了english字段，添加到列表
            if paragraph_dict.get('english'):
                # 确保chinese字段存在（如果没有则设为空字符串）
                if 'chinese' not in paragraph_dict:
                    paragraph_dict['chinese'] = ''
                paragraphs.append(paragraph_dict)
                logger.debug(f"段落 {idx} 成功添加到列表")
            else:
                logger.debug("段落 %d 未能提取英文", idx)
        
        logger.debug("段落解析完成: %d 段", len(paragraphs))
        
    except Exception as e:
        logger.error("✗ 段落解析失败: %s", e, exc_info=True)
    
    return paragraphs


def mark_vocabulary_in_text(text: str, vocabulary: List[Dict]) -> str:
    """
    在文本中标记核心词汇
    
    Args:
        text: 原始文本
        vocabulary: 词汇列表
        
    Returns:
        标记后的文本
    """
    # 按单词长度降序排序，优先匹配长单词
    sorted_vocab = sorted(vocabulary, key=lambda x: len(x.get('word', '')), reverse=True)
    
    marked_text = text
    for vocab in sorted_vocab:
        word = vocab.get('word', '').strip()
        if not word:
            continue
        
        # current_meaning = vocab.get("current_meaning", "")  # 文中词义
        all_meanings = vocab.get("all_meanings", "")  # 所有可能的中文词义
        
        # 使用单词边界匹配，避免部分匹配
        pattern = r'\b' + re.escape(word) + r'\b'
        
        # 替换为带标记的HTML
        replacement = f'<span class="vocab-word" data-translation="{escape_html(all_meanings)}">{word}</span>'
        marked_text = re.sub(pattern, replacement, marked_text, flags=re.IGNORECASE)
    
    return marked_text
