# -*- coding: utf-8 -*-
"""
步骤7：生成全局资源展示页面
扫描 output/YYYYMMDD/ 下所有日期的 02-vocabulary、04-pic_html、05-mp4_html，
聚合后仅更新全局 output/resources.html，不生成当日 output/YYYYMMDD/resources.html。

使用方法：
    python src/step7_generate_resource_page.py
"""

import re
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.utils.config import (
    INPUT_BASE,
    OUTPUT_BASE,
    OUTPUT_GLOBAL_RESOURCE_INDEX,
    TEMPLATE_RESOURCE_INDEX,
    normalize_filename,
    ensure_dirs,
)
from src.utils.file_handler import get_relative_path, sanitize_filename
from src.utils.logger import setup_logger, SEP_LINE
from src.utils.material_type import MATERIAL_NAMES, get_material_name

logger = setup_logger("step7")


def _find_md_in_dir(vocab_dir: Path, input_stem: str) -> Path | None:
    """在指定 vocab 目录下按 stem 查找对应 .md（兼容 sanitize 与 normalize 命名）"""
    if not vocab_dir.exists():
        return None
    for s in (sanitize_filename(input_stem), normalize_filename(input_stem)):
        p = vocab_dir / f"{s}.md"
        if p.exists():
            return p
    return None


def _stem_variants_for_day(stem: str) -> list[str]:
    """
    生成 stem 的 Day0X / DayX 兼容变体，用于匹配 pic/mp4 文件名。
    例如 IELT50_Day02_... 与 IELT50_Day2_... 可互相匹配。
    （用 (^|_) 限定边界，因下划线属于 \\w，\\b 在 Day 前不生效）
    """
    variants = [stem]
    # Day02 -> Day2（Day0 + 一位数字，且后面不再跟数字）
    m = re.search(r"(?i)(^|_)Day0(\d)(?!\d)", stem)
    if m:
        alt = stem[: m.start()] + m.group(1) + f"Day{m.group(2)}" + stem[m.end() :]
        if alt not in variants:
            variants.append(alt)
    # Day2 -> Day02（Day + 单个数字 1-9，且后面不紧跟数字）
    m = re.search(r"(?i)(^|_)Day([1-9])(?!\d)", stem)
    if m:
        alt = stem[: m.start()] + m.group(1) + f"Day0{m.group(2)}" + stem[m.end() :]
        if alt not in variants:
            variants.append(alt)
    return variants


def _collect_resources() -> list[dict]:
    """
    扫描 output/YYYYMMDD/ 下所有日期目录，聚合各日期的词汇 MD、排版 HTML、播放页 HTML，
    返回全局资源列表（含 mtime 用于倒序）。
    """
    resources: list[dict] = []
    if not OUTPUT_BASE.exists():
        return resources
    # 仅处理 8 位数字子目录（YYYYMMDD）
    date_pattern = re.compile(r"^\d{8}$")
    for date_dir in sorted(OUTPUT_BASE.iterdir(), reverse=True):
        if not date_dir.is_dir() or not date_pattern.match(date_dir.name):
            continue
        date_str = date_dir.name
        vocab_dir = date_dir / "02-vocabulary"
        pic_dir = date_dir / "04-pic_html"
        mp4_dir = date_dir / "05-mp4_html"
        input_dir = INPUT_BASE / date_str
        if not input_dir.exists():
            continue
        pic_files = {p.stem: p for p in pic_dir.glob("*.html")} if pic_dir.exists() else {}
        mp4_files = {p.stem: p for p in mp4_dir.glob("*.html")} if mp4_dir.exists() else {}
        for input_path in sorted(input_dir.glob("*.txt")):
            md_path = _find_md_in_dir(vocab_dir, input_path.stem)
            if not md_path:
                continue
            stem = md_path.stem
            sanitized = sanitize_filename(stem)
            normalized = normalize_filename(stem)
            # 用 stem 及 Day0X/DayX 变体匹配 pic/mp4 文件名，兼容同一素材的两种命名
            pic_candidates = [sanitized, stem, normalized] + _stem_variants_for_day(stem)
            mp4_candidates = [normalized, stem, sanitized] + _stem_variants_for_day(stem)
            pic_path = next((pic_files[k] for k in pic_candidates if k in pic_files), None)
            mp4_path = next((mp4_files[k] for k in mp4_candidates if k in mp4_files), None)
            mtime = 0.0
            for p in (md_path, pic_path, mp4_path):
                if p and p.exists():
                    try:
                        mtime = max(mtime, p.stat().st_mtime)
                    except OSError:
                        pass
            resources.append({
                "name": stem,
                "vocab": md_path,
                "pic_html": pic_path,
                "mp4_html": mp4_path,
                "mtime": mtime,
            })
    return resources


def _to_resource_url(path: Path) -> str | None:
    """
    生成相对于 output/ 的路径，供全局 resources.html 使用；打开 output/resources.html 时链接可正确解析。
    """
    if not path or not path.exists():
        return None
    try:
        return path.resolve().relative_to(OUTPUT_BASE.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_uri()


def _prepare_template_data(resources: list[dict]) -> dict:
    """准备模板所需数据：按资料名称分组，每项含 name、vocab_url、pic_url、mp4_url；资源按文件生成日期倒序排列"""
    by_name: dict[str, list[dict]] = {n["id"]: [] for n in MATERIAL_NAMES}
    for r in resources:
        name_cfg = get_material_name(r["name"])
        name_id = name_cfg["id"]
        mtime = r.get("mtime", 0.0)
        mtime_str = datetime.fromtimestamp(mtime).strftime("%Y/%m/%d %H:%M:%S") if mtime else ""
        by_name.setdefault(name_id, []).append({
            "name": r["name"],
            "vocab_url": _to_resource_url(r["vocab"]) if r["vocab"] else None,
            "pic_url": _to_resource_url(r["pic_html"]) if r["pic_html"] else None,
            "mp4_url": _to_resource_url(r["mp4_html"]) if r["mp4_html"] else None,
            "mtime": mtime,
            "mtime_str": mtime_str,
        })
    # 按 MATERIAL_NAMES 顺序，每类内按 mtime 倒序、name 正序
    categories = [
        {"id": n["id"], "label": n["label"], "resources": sorted(by_name.get(n["id"], []), key=lambda x: (-x["mtime"], x["name"]))}
        for n in MATERIAL_NAMES
    ]
    return {"categories": categories}


def _generate_html(resources: list[dict]) -> str:
    """使用 Jinja2 模板生成资源展示 HTML"""
    template_data = _prepare_template_data(resources)
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_RESOURCE_INDEX.parent),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template(TEMPLATE_RESOURCE_INDEX.name)
    return template.render(**template_data)


def main() -> None:
    """主函数"""
    ensure_dirs()
    # logger.info("%s", SEP_LINE)
    # logger.info("[Step7] 资源展示页面生成")
    # logger.info("%s", SEP_LINE)

    resources = _collect_resources()
    if not resources:
        logger.warning("⚠ 未找到任何资源（请检查 input 目录及 step2 生成的 MD）")
        return

    if not TEMPLATE_RESOURCE_INDEX.exists():
        logger.error("✗ 模板不存在: %s", get_relative_path(TEMPLATE_RESOURCE_INDEX))
        return

    out_path = OUTPUT_GLOBAL_RESOURCE_INDEX
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = _generate_html(resources)
    out_path.write_text(html, encoding="utf-8")
    logger.info("✓ 已更新全局资源展示页面: %s （共 %d 条资源）", get_relative_path(out_path), len(resources))
    logger.info("[Step7] 完成（全局资源展示页面：共 %d 条资源）", len(resources))


if __name__ == "__main__":
    main()
