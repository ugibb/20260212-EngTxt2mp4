# -*- coding: utf-8 -*-
"""
统一执行全流程：step1 -> step2 -> step3 -> step4 -> step5 -> step6 -> step7
支持按指定步骤执行，默认全部执行。

用法：
  python src/run_all.py                    # 执行全部（单日期）
  python src/run_all.py --all              # 执行 input 下所有日期目录
  python src/run_all.py -d 20260220        # 指定日期
  python src/run_all.py -f "文件名"        # 在 input 下全局查找该文件（不指定 -d 时），找到的日期下仅处理该文件
  python src/run_all.py -d 20260220 -f "文件名"  # 指定日期下仅处理该文件
  python src/run_all.py 5 6                # 仅执行 step5、step6
  python src/run_all.py --steps 1 2 3      # 仅执行 step1、step2、step3
"""

import argparse
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.file_handler import get_relative_path
from src.utils.logger import setup_logger, SEP_DOUBLE

logger = setup_logger("run_all")

# 步骤 6 为 step7_generate_resource_page，每次运行都会自动加入，保证 resources.html 包含全部资源链接
STEPS: dict[int, tuple[str, str]] = {
    1: ("文本预处理  >>>>>>>>>", "step1_format_text"),
    2: ("调用 LLM 生成词汇 >>>", "step2_extract_vocab"),
    3: ("TTS 音频+时间戳生成 >", "step3_generate_tts"),
    4: ("排版 HTML 生成 >>>>>", "step4_generate_pic_html"),
    5: ("TTS 播放页 HTML 生成 ", "step5_generate_mp4_html"),
    6: ("全局资源展示页面生成 >>", "step7_generate_resource_page"),
    7: ("视频录制导出 MP4 >>>>>", "step6_record_video"),
}
STEP_ALWAYS_RUN: int = 6  # 每次执行都运行 step7，刷新 resources.html


def _run_step(step_num: int, reload_step: bool = False) -> None:
    """动态导入并执行指定步骤。reload_step=True 时先 reload 该模块再执行，以便读到最新 config（用于 --all 逐日）"""
    import importlib
    module_name = STEPS[step_num][1]
    mod = importlib.import_module(f"src.{module_name}")
    if reload_step:
        importlib.reload(mod)
    mod.main()


def _parse_args() -> tuple[list[int], str | None, bool, str | None]:
    parser = argparse.ArgumentParser(description="执行 Txt2mp4 流程，可指定步骤")
    parser.add_argument(
        "steps",
        nargs="*",
        type=int,
        metavar="N",
        help="要执行的步骤编号 1-7，不指定则执行全部",
    )
    parser.add_argument(
        "-s", "--steps",
        dest="steps_opt",
        nargs="+",
        type=int,
        metavar="N",
        help="要执行的步骤编号（如 -s 5 6）",
    )
    parser.add_argument(
        "-d", "--date",
        dest="date",
        type=str,
        metavar="YYYYMMDD",
        help="运行日期目录，如 20260220；默认使用 .env 的 RUN_DATE 或当天",
    )
    parser.add_argument(
        "-a", "--all",
        dest="all_dates",
        action="store_true",
        help="执行 input 下所有日期目录（YYYYMMDD），逐日运行所选步骤",
    )
    parser.add_argument(
        "-f", "--file",
        dest="single_file",
        type=str,
        metavar="NAME",
        help="仅处理 input 目录下指定文件（文件名或 stem，可带或不带 .txt）",
    )
    args = parser.parse_args()
    steps = args.steps_opt if args.steps_opt is not None else args.steps
    run_date = getattr(args, "date", None) or None
    all_dates = getattr(args, "all_dates", False) or False
    single_file = (getattr(args, "single_file", None) or "").strip() or None
    if not steps:
        steps = list(STEPS.keys())
    else:
        steps = sorted(set(steps))
    invalid = [s for s in steps if s not in STEPS]
    if invalid:
        parser.error(f"无效步骤: {invalid}，有效步骤为 1-7")
    # 始终加入步骤 6（step7），保证 resources.html 包含全部资源链接
    steps = sorted(set(steps) | {STEP_ALWAYS_RUN})
    return steps, run_date, all_dates, single_file


def _get_all_date_dirs() -> list[str]:
    """获取 input 下所有 8 位数字日期目录名，正序"""
    from src.utils.config import INPUT_BASE
    if not INPUT_BASE.exists():
        return []
    date_pattern = re.compile(r"^\d{8}$")
    return sorted(d.name for d in INPUT_BASE.iterdir() if d.is_dir() and date_pattern.match(d.name))


def _find_file_in_input_globally(single_file: str) -> list[tuple[str, Path]]:
    """
    在 input 下所有日期目录（YYYYMMDD）中全局查找指定文件。
    返回 [(date_str, path), ...]，按日期正序；匹配文件名或 stem，可带或不带 .txt。
    """
    from src.utils.config import INPUT_BASE
    needle = single_file.strip()
    needle_txt = needle if needle.endswith(".txt") else f"{needle}.txt"
    found: list[tuple[str, Path]] = []
    for date_str in _get_all_date_dirs():
        input_dir = INPUT_BASE / date_str
        if not input_dir.is_dir():
            continue
        for p in input_dir.glob("*.txt"):
            if p.name == needle_txt or p.stem == needle or p.name == needle:
                found.append((date_str, p))
                break
    return found


def main() -> None:
    import importlib
    import src.utils.config as _cfg

    steps_to_run, run_date, all_dates, single_file = _parse_args()
    if single_file:
        os.environ["RUN_SINGLE_FILE"] = single_file
        importlib.reload(_cfg)

    if all_dates:
        date_list = _get_all_date_dirs()
        if not date_list:
            logger.warning("⚠ input 下无日期目录（YYYYMMDD），跳过")
            return
        logger.info("%s", SEP_DOUBLE)
        logger.info("执行全部日期: %s（共 %d 个）", ", ".join(date_list), len(date_list))
        logger.info("执行步骤: %s", " → ".join(f"Step{s}" for s in steps_to_run))
        logger.info("%s", SEP_DOUBLE)
        for one_date in date_list:
            os.environ["RUN_DATE"] = one_date
            importlib.reload(_cfg)
            from src.utils.config import ensure_dirs, RUN_DATE, INPUT_DIR, OUTPUT_DIR
            ensure_dirs()
            logger.info(">>> 当前日期: %s（input=%s, output=%s）<<<", RUN_DATE, INPUT_DIR.name, OUTPUT_DIR.name)
            for i in steps_to_run:
                name, _ = STEPS[i]
                logger.info(">>> 【Step%d】： %s>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>", i, name)
                _run_step(i, reload_step=True)
        logger.info("%s", SEP_DOUBLE)
        logger.info("→ 全部日期执行完毕（共 %d 个）←", len(date_list))
        logger.info("%s", SEP_DOUBLE)
        return

    # -f 且未指定 -d：在 input 下所有日期目录中全局查找该文件，找到则按对应日期执行
    if single_file and not run_date:
        matches = _find_file_in_input_globally(single_file)
        if not matches:
            logger.warning("⚠ 未在 input 下任何日期目录中找到文件: %s", single_file)
            return
        logger.info("%s", SEP_DOUBLE)
        logger.info("按 -f 在 input 下全局找到 %d 个文件", len(matches))
        for idx, (date_str, path) in enumerate(matches, 1):
            logger.info("  第[%d/%d]个文件：%s", idx, len(matches), get_relative_path(path))
        logger.info("执行步骤: %s", " → ".join(f"Step{s}" for s in steps_to_run))
        logger.info("%s", SEP_DOUBLE)
        for date_str, path in matches:
            os.environ["RUN_DATE"] = date_str
            os.environ["RUN_SINGLE_FILE"] = path.name
            importlib.reload(_cfg)
            from src.utils.config import ensure_dirs, RUN_DATE, INPUT_DIR, OUTPUT_DIR
            ensure_dirs()
            logger.info(">>> 当前日期: %s（input=%s, output=%s）| 文件: %s <<<", RUN_DATE, INPUT_DIR.name, OUTPUT_DIR.name, path.name)
            for i in steps_to_run:
                name, _ = STEPS[i]
                logger.info(">>> 【Step%d】： %s>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>", i, name)
                _run_step(i, reload_step=True)
        logger.info("%s", SEP_DOUBLE)
        logger.info("→ 执行完毕（共 %d 个日期）←", len(matches))
        logger.info("%s", SEP_DOUBLE)
        return

    if run_date:
        os.environ["RUN_DATE"] = run_date
        importlib.reload(_cfg)
    from src.utils.config import ensure_dirs, RUN_DATE, INPUT_DIR, OUTPUT_DIR
    ensure_dirs()
    desc = " → ".join(f"Step{s}" for s in steps_to_run)
    logger.info("%s", SEP_DOUBLE)
    logger.info("运行日期: %s（input=%s, output=%s）", RUN_DATE, INPUT_DIR.name, OUTPUT_DIR.name)
    if single_file:
        logger.info("仅处理文件: %s", single_file)
    logger.info("执行步骤: %s", desc)
    logger.info("%s", SEP_DOUBLE)

    for i in steps_to_run:
        name, _ = STEPS[i]
        logger.info(">>> 【Step%d】： %s>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>", i, name)
        _run_step(i)

    logger.info("%s", SEP_DOUBLE)
    logger.info("→ 执行完毕 ←")
    logger.info("%s", SEP_DOUBLE)


if __name__ == "__main__":
    main()
