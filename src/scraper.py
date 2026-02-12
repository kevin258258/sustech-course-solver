"""课程数据爬取模块：从 TIS 系统获取课程信息并解析时间"""

from __future__ import annotations

import re
import json
import warnings
from collections import defaultdict

import requests
from urllib3.exceptions import InsecureRequestWarning

from .models import Course, Section, TimeSlot, WEEKDAY_MAP

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

TIS_BASE = "https://tis.sustech.edu.cn"
QUERY_SEMESTER_URL = f"{TIS_BASE}/Xsxk/queryXkdqXnxq"
QUERY_COURSES_URL = f"{TIS_BASE}/Xsxk/queryKxrw"

# 六种选课类型
COURSE_TYPES: dict[str, str] = {
    "bxxk": "通识必修选课",
    "xxxk": "通识选修选课",
    "kzyxk": "培养方案内课程",
    "zynknjxk": "非培养方案内课程",
    "cxxk": "重修选课",
    "jhnxk": "计划内选课新生",
}

# 时间正则：匹配 "星期一第1-2节" 这种格式
TIME_PATTERN = re.compile(r"星期([一二三四五六日])第(\d+)-(\d+)节")


def get_semester_info(headers: dict[str, str]) -> dict:
    """获取当前学期信息。

    Returns
    -------
    dict
        包含 p_xn, p_xq, p_xnxq 等字段的字典
    """
    resp = requests.post(
        QUERY_SEMESTER_URL,
        data={"mxpylx": 1},
        headers=headers,
        verify=False,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if "p_xn" not in data:
        raise RuntimeError(f"获取学期信息失败，返回数据异常: {resp.text[:200]}")
    return data


def parse_time_slots(time_str: str) -> list[TimeSlot]:
    """从时间描述字符串中解析出 TimeSlot 列表。

    支持的格式示例：
        "星期一第1-2节"
        "星期三第3-4节 星期五第1-2节"（多个时间段）

    Parameters
    ----------
    time_str : str
        包含上课时间信息的字符串

    Returns
    -------
    list[TimeSlot]
    """
    slots: list[TimeSlot] = []
    for match in TIME_PATTERN.finditer(time_str):
        weekday_char = match.group(1)
        start = int(match.group(2))
        end = int(match.group(3))
        weekday = WEEKDAY_MAP.get(weekday_char)
        if weekday is not None:
            slots.append(TimeSlot(weekday=weekday, start_period=start, end_period=end))
    return slots


def fetch_all_courses(
    headers: dict[str, str],
    semester_info: dict,
) -> dict[str, list[Section]]:
    """从 TIS 抓取当前学期所有课程信息。

    Returns
    -------
    dict[str, list[Section]]
        课程名 -> 该课程所有教学班列表
    """
    course_map: dict[str, list[Section]] = defaultdict(list)

    for c_type, c_name in COURSE_TYPES.items():
        print(f"  [*] 获取 {c_name} 列表...")

        page_num = 1
        page_size = 500  # TIS 服务端分页上限为 500
        total_fetched = 0

        while True:
            data = {
                "p_xn": semester_info["p_xn"],
                "p_xq": semester_info["p_xq"],
                "p_xnxq": semester_info["p_xnxq"],
                "p_pylx": 1,
                "mxpylx": 1,
                "p_xkfsdm": c_type,
                "pageNum": page_num,
                "pageSize": page_size,
            }

            try:
                resp = requests.post(
                    QUERY_COURSES_URL,
                    data=data,
                    headers=headers,
                    verify=False,
                    timeout=30,
                )
                resp.raise_for_status()
                raw = resp.json()
            except (requests.RequestException, json.JSONDecodeError) as e:
                print(f"  [!] 获取 {c_name} 第{page_num}页失败: {e}")
                break

            course_list = raw.get("kxrwList", {})
            if isinstance(course_list, dict):
                course_list = course_list.get("list", [])
            elif not isinstance(course_list, list):
                course_list = []

            if not course_list:
                break

            for item in course_list:
                course_name = item.get("rwmc", "未知课程")
                section_name = item.get("rwmc", course_name)
                section_id = item.get("id", "")
                teacher = item.get("dgjsmc", "") or ""

                # 尝试从多个可能的字段中提取时间信息
                time_str = ""
                # 常见的时间字段名
                for time_field in ["sksj", "sksjms", "sksjStr", "sksjdd"]:
                    if item.get(time_field):
                        time_str = str(item[time_field])
                        break

                # 如果上面的字段都没有，尝试从整个 item 的字符串表示中提取
                if not time_str:
                    item_str = json.dumps(item, ensure_ascii=False)
                    if TIME_PATTERN.search(item_str):
                        time_str = item_str

                time_slots = parse_time_slots(time_str)

                # 构建教学班显示名：课程名 + 教师
                display_name = section_name
                if teacher:
                    display_name = f"{section_name} - {teacher}"

                section = Section(
                    course_name=course_name,
                    section_name=display_name,
                    section_id=section_id,
                    course_type=c_type,
                    time_slots=time_slots,
                    teacher=teacher,
                )
                course_map[course_name].append(section)

            total_fetched += len(course_list)

            # 如果本页数量不足 page_size，说明已经是最后一页
            if len(course_list) < page_size:
                break

            # 还有更多页，继续获取
            page_num += 1
            print(f"  [*] {c_name}: 已获取 {total_fetched} 个，继续获取第 {page_num} 页...")

        if total_fetched > 0:
            print(f"  [+] {c_name}: 共获取到 {total_fetched} 个教学班")

    total = sum(len(secs) for secs in course_map.values())
    print(f"[+] 课程信息获取完毕，共 {len(course_map)} 门课程，{total} 个教学班")
    return dict(course_map)


def get_courses_for_selection(
    headers: dict[str, str],
    semester_info: dict,
    wanted_course_names: list[str],
) -> list[Course]:
    """获取用户想选的课程及其所有教学班。

    Parameters
    ----------
    headers : dict[str, str]
        已登录的请求头
    semester_info : dict
        学期信息
    wanted_course_names : list[str]
        用户想选的课程名列表

    Returns
    -------
    list[Course]
        每门课包含所有可选教学班信息
    """
    print("[*] 从 TIS 获取课程数据...")
    all_courses = fetch_all_courses(headers, semester_info)

    # 硬编码：TIS API 无法查到但确实存在的课程
    _HARDCODED: dict[str, list[Section]] = {
        "数理逻辑导论": [
            Section(
                course_name="数理逻辑导论",
                section_name="数理逻辑导论-01班-英文 - 陶伊达",
                section_id="CS104-01",
                course_type="zynknjxk",
                time_slots=[TimeSlot(weekday=2, start_period=3, end_period=4)],  # 星期三第3-4节
                teacher="陶伊达",
            ),
        ],
    }
    for hc_name, hc_sections in _HARDCODED.items():
        if hc_name not in all_courses:
            all_courses[hc_name] = hc_sections
            print(f"  [*] 补充硬编码课程: {hc_name}")

    result: list[Course] = []
    not_found: list[str] = []

    for name in wanted_course_names:
        name = name.strip()
        if not name:
            continue

        # 精确匹配
        if name in all_courses:
            sections = all_courses[name]
            result.append(Course(name=name, sections=sections))
            continue

        # 模糊匹配：课程名包含用户输入的关键词
        fuzzy_matches: list[tuple[str, list[Section]]] = []
        for course_name, sections in all_courses.items():
            if name in course_name or course_name in name:
                fuzzy_matches.append((course_name, sections))

        if len(fuzzy_matches) == 1:
            matched_name, sections = fuzzy_matches[0]
            print(f"  [*] 模糊匹配: \"{name}\" -> \"{matched_name}\"")
            result.append(Course(name=matched_name, sections=sections))
        elif len(fuzzy_matches) > 1:
            # 将多个匹配项合并为同一门课的不同教学班
            all_sections: list[Section] = []
            for mn, secs in fuzzy_matches:
                all_sections.extend(secs)
            print(f"  [*] \"{name}\" 匹配到 {len(all_sections)} 个教学班:")
            for sec in all_sections:
                slots_str = ", ".join(str(ts) for ts in sec.time_slots) or "时间未知"
                print(f"      - {sec.section_name} [{slots_str}]")
            result.append(Course(name=name, sections=all_sections))
        else:
            not_found.append(name)

    if not_found:
        print(f"\n[!] 以下课程未在 TIS 中找到:")
        for name in not_found:
            print(f"    - {name}")
        print("    请检查课程名是否与 TIS 系统中的完全一致\n")

    return result
