# -*- coding: utf-8 -*-
"""
资料类型与资料名称配置（两层结构）
- 资料类型：用于 mp4 播放页红框 icon + 短标签
- 资料名称：用于 resources.html 的 tab 分组；每条资源归属一个资料名称，资料名称归属一个资料类型

input 文件名通过前缀识别资料名称，资料类型由资料名称的 type_id 得到。
详见 doc/资料类型功能设计.md
"""

from typing import Any

# 资料类型（上层）：mp4 页红框展示，用于 icon 设计；code 为类型简写，配置 type_id 时可直接用简写
# style_index：对应 template/styles/style{N}.css（1-4），不同资源类型使用不同样式表
MATERIAL_TYPES: list[dict[str, Any]] = [
    {"id": "follow_read", "code": "04FR", "label": "跟读", "short_label": "跟读", "icon": "follow_read", "style_index": 4},
    {"id": "vocabulary", "code": "06V", "label": "词汇", "short_label": "词汇", "icon": "vocabulary", "style_index": 1},
    {"id": "intensive_read", "code": "05IR", "label": "精读", "short_label": "精读", "icon": "intensive_read", "style_index": 2},
    {"id": "news", "code": "01N", "label": "新闻", "short_label": "新闻", "icon": "news", "style_index": 1},
    {"id": "tech", "code": "02T", "label": "科技", "short_label": "科技", "icon": "tech", "style_index": 2},
    {"id": "entertainment", "code": "03E", "label": "娱乐", "short_label": "娱乐", "icon": "entertainment", "style_index": 3},
]


def _match_white_house(stem: str) -> bool:
    return stem.startswith("WH_")


def _match_bbc(stem: str) -> bool:
    return stem.startswith("BBC_")


def _match_eim(stem: str) -> bool:
    return stem.startswith("EIM_")


def _match_s900(stem: str) -> bool:
    """S900_ 或沿用旧前缀 D_（如 D_23-TV_programs_en）"""
    return stem.startswith("S900_") or stem.startswith("D_")


# 资料名称（下层）：resources.html 按此分组；type_id 用类型简写（code）配置即可
MATERIAL_NAMES: list[dict[str, Any]] = [
    {"id": "english_in_a_minute", "label": "English in a Minute", "type_id": "04FR", "match": _match_eim},
    {"id": "ielts_speaking_900", "label": "雅思口语必备900句", "type_id": "05IR", "match": _match_s900},
    {"id": "ielts_reading_50", "label": "50 篇英语短文搞定雅思阅读核心词汇", "type_id": "06V", "match": lambda _: True},
    {"id": "white_house", "label": "美国白宫新闻发布会", "type_id": "01N", "match": _match_white_house},
    {"id": "bbc_news", "label": "BBC news", "type_id": "01N", "match": _match_bbc},
]


def get_material_name(stem: str) -> dict[str, Any]:
    """根据文件名 stem 返回匹配的资料名称配置（含 id, label, type_id）。"""
    for name in MATERIAL_NAMES:
        if name["match"](stem):
            return {k: v for k, v in name.items() if k != "match"}
    return {k: v for k, v in MATERIAL_NAMES[-1].items() if k != "match"}


def get_material_type(type_id: str) -> dict[str, Any]:
    """根据 type_id 返回资料类型配置（type_id 支持 id 或简写 code，如 01N、05IR）。"""
    for t in MATERIAL_TYPES:
        if t["id"] == type_id or t.get("code") == type_id:
            return dict(t)
    return dict(MATERIAL_TYPES[0])
