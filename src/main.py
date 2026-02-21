#!/usr/bin/env python3
"""南科大课表无冲突组合求解器 - 主入口"""

from __future__ import annotations

import sys
import os
from pathlib import Path

import yaml
from rich.console import Console
from rich.panel import Panel

# 将项目根目录加入 sys.path，以支持直接运行
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.auth import interactive_login, cas_login
from src.scraper import get_semester_info, get_courses_for_selection
from src.solver import solve, print_solve_summary
from src.display import display_all_schedules

console = Console()

BANNER = r"""
  ____  _   _ ____  _____         _
 / ___|| | | / ___||_   _|__  ___| |__
 \___ \| | | \___ \  | |/ _ \/ __| '_ \
  ___) | |_| |___) | | |  __/ (__| | | |
 |____/ \___/|____/  |_|\___|\___|_| |_|

     课表无冲突组合求解器 v1.0
"""


def load_config(config_path: str = "config.yaml") -> dict:
    """从配置文件读取完整配置（课程列表 + 可选的登录凭据）。

    Parameters
    ----------
    config_path : str
        配置文件路径，默认为项目根目录下的 config.yaml

    Returns
    -------
    dict
        包含 courses, student_id(可选), password(可选) 的配置字典
    """
    # 先尝试相对于项目根目录
    full_path = PROJECT_ROOT / config_path
    if not full_path.exists():
        # 再尝试相对于当前工作目录
        full_path = Path(config_path)

    if not full_path.exists():
        console.print(f"[red]配置文件 {config_path} 不存在！[/red]")
        console.print(f"请在项目根目录创建 config.yaml，格式如下：\n")
        console.print(
            'courses:\n'
            '  - "高等数学A"\n'
            '  - "线性代数"\n'
            '  - "大学物理A"\n'
        )
        sys.exit(1)

    with open(full_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not config or "courses" not in config:
        console.print("[red]配置文件格式错误：缺少 courses 字段[/red]")
        sys.exit(1)

    courses = config["courses"]
    if not isinstance(courses, list) or len(courses) == 0:
        console.print("[red]配置文件中 courses 列表为空[/red]")
        sys.exit(1)

    config["courses"] = [str(c).strip() for c in courses if c]
    return config


def main() -> None:
    """主流程：读取配置 -> 登录 -> 爬取 -> 求解 -> 展示"""
    console.print(Panel(BANNER, border_style="bright_blue", expand=False))

    # 1. 读取配置
    console.print("[bold]步骤 1/4: 读取课程配置[/bold]")
    config = load_config()
    wanted_courses = config["courses"]
    console.print(f"[green]已读取 {len(wanted_courses)} 门想选的课程:[/green]")
    for i, name in enumerate(wanted_courses, 1):
        console.print(f"  {i}. {name}")
    console.print()

    # 2. 登录 TIS
    console.print("[bold]步骤 2/4: 登录 TIS 系统[/bold]")
    try:
        sid = config.get("student_id", "")
        pwd = config.get("password", "")
        if sid and pwd:
            console.print(f"[*] 使用配置文件中的凭据登录（学号: {sid}）...")
            headers = cas_login(str(sid), str(pwd))
            console.print("[+] 登录成功！")
        else:
            headers = interactive_login()
    except (RuntimeError, ConnectionError, ValueError) as e:
        console.print(f"[red]{e}[/red]")
        console.print("[*] 尝试手动登录...")
        try:
            headers = interactive_login()
        except RuntimeError as e2:
            console.print(f"[red]{e2}[/red]")
            sys.exit(1)

    # 3. 获取学期信息和课程数据
    console.print("\n[bold]步骤 3/4: 获取课程数据[/bold]")
    try:
        semester_info = get_semester_info(headers)
        semester_name = {
            "1": "秋季",
            "2": "春季",
            "3": "小学期",
        }.get(str(semester_info.get("p_xq", "")), "未知")
        console.print(
            f"[green]当前学期: {semester_info.get('p_xn', '?')} 学年 "
            f"第 {semester_info.get('p_xq', '?')} 学期 ({semester_name})[/green]\n"
        )
    except Exception as e:
        console.print(f"[red]获取学期信息失败: {e}[/red]")
        sys.exit(1)

    try:
        courses = get_courses_for_selection(headers, semester_info, wanted_courses)
    except Exception as e:
        console.print(f"[red]获取课程数据失败: {e}[/red]")
        sys.exit(1)

    if not courses:
        console.print("[red]未能获取到任何课程信息，请检查课程名是否正确[/red]")
        sys.exit(1)

    # 展示获取到的课程信息
    console.print("\n[bold]已获取的课程信息:[/bold]")
    for course in courses:
        console.print(f"\n  [bright_cyan]{course.name}[/bright_cyan] ({len(course.sections)} 个教学班)")
        for sec in course.sections:
            slots_str = ", ".join(str(ts) for ts in sec.time_slots) or "时间未知"
            console.print(f"    - {sec.section_name}  [dim]{slots_str}[/dim]")

    # 4. 求解
    console.print(f"\n[bold]步骤 4/4: 求解无冲突课表[/bold]")
    results = solve(courses, max_results=2000)
    print_solve_summary(courses, results)

    # 展示结果
    display_all_schedules(results)


if __name__ == "__main__":
    main()
