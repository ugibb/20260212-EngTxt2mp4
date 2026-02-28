# -*- coding: utf-8 -*-
"""
TTS 角色语音配置：角色标识、简写解析、角色 → Edge TTS voice 映射。
参见 doc/TTS角色语音技术方案.md
"""
import re
from datetime import datetime
from typing import Optional

# 角色标识（程序内部统一使用）
NARRATION = "narration"
MALE = "male"
FEMALE = "female"
BOY = "boy"
GIRL = "girl"

# 角色标识列表（用于校验与默认）
ROLE_IDS = (NARRATION, MALE, FEMALE, BOY, GIRL)

# 简写 → 角色标识（标记行 [简写] 解析用，不区分大小写）
# 支持：N/独白/独、M/男、F/女、B/童男、G/童女，以及英文全称
SHORTHAND_TO_ROLE: dict[str, str] = {
    "n": NARRATION,
    "narration": NARRATION,
    "独白": NARRATION,
    "独": NARRATION,
    "m": MALE,
    "male": MALE,
    "男": MALE,
    "f": FEMALE,
    "female": FEMALE,
    "女": FEMALE,
    "b": BOY,
    "boy": BOY,
    "童男": BOY,
    "g": GIRL,
    "girl": GIRL,
    "童女": GIRL,
}

# 角色 → Edge TTS voice ID（en-US 神经语音，可后续在 config 或此处扩展）
# 说明：GuyNeural 偏青年/少年感，ChristopherNeural 偏成熟/中老年男声，故 boy 用 Guy、male 用 Christopher
# 独白 narration 不在此写死，由 get_voice_for_role 按日期单双数切换 male/female
ROLE_VOICE_MAP: dict[str, str] = {
    MALE: "en-US-ChristopherNeural",
    FEMALE: "en-US-JennyNeural",
    BOY: "en-US-GuyNeural",
    GIRL: "en-US-AnaNeural",
}


def parse_role_tag(line: str) -> Optional[str]:
    """
    解析单独一行的角色标记。
    约定：整行仅 [xxx] 形式，方括号内为角色标识或简写，不区分大小写。
    若无法识别则返回 None。
    """
    if not line or not isinstance(line, str):
        return None
    s = line.strip()
    m = re.match(r"^\[(.+)\]$", s)
    if not m:
        return None
    key = m.group(1).strip().lower()
    if not key:
        return None
    # 中文简写不 lower（独白、男、女、童男、童女）
    role = SHORTHAND_TO_ROLE.get(key) or SHORTHAND_TO_ROLE.get(s.strip())
    return role


# 用于匹配段首「[M]:」「[男]:」等角色前缀，避免与词汇标注 [] 混淆
_ROLE_PREFIX_RE = re.compile(
    r"^\s*\[(?:n|m|f|b|g|narration|male|female|boy|girl|独白|独|男|女|童男|童女)\]\s*:?\s*",
    re.IGNORECASE,
)


def strip_leading_role_prefix(text: str) -> tuple[str, Optional[str]]:
    """
    若文本以角色标记开头（如 [M]: 或 [男]:），则剥离该前缀并返回规范角色标识。
    用于避免 [M]: 等进入 english 内容、与词汇标注的方括号混淆。
    返回 (剥离后的文本, 角色标识或 None)。
    """
    if not text or not isinstance(text, str):
        return (text or "", None)
    s = text.strip()
    m = _ROLE_PREFIX_RE.match(s)
    if not m:
        return (text, None)
    prefix = m.group(0)
    rest = s[len(prefix) :].strip()
    # 从前缀中解析出角色：取 [ 与 ] 之间的内容
    inner = re.search(r"\[([^\]]+)\]", prefix)
    role = parse_role_tag(f"[{inner.group(1)}]" if inner else "") if inner else None
    return (rest, role)


def get_voice_for_role(role: str) -> str:
    """根据角色标识返回 Edge TTS voice ID。独白(narration)按日期单双数切换男/女声；未知或空按独白处理。"""
    if not role or role not in ROLE_IDS:
        role = NARRATION
    if role == NARRATION:
        # 独白：单数日男声，双数日女声
        day = datetime.now().day
        return ROLE_VOICE_MAP[MALE] if day % 2 == 1 else ROLE_VOICE_MAP[FEMALE]
    return ROLE_VOICE_MAP[role]


def normalize_role(role: Optional[str]) -> str:
    """将 MD 或解析得到的 role 规范为角色标识，无效则返回 narration。"""
    if not role or not isinstance(role, str):
        return NARRATION
    r = role.strip().lower()
    if r in ROLE_IDS:
        return r
    return SHORTHAND_TO_ROLE.get(r) or NARRATION
