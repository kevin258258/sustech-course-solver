# SUSTech Course Schedule Solver

南方科技大学（SUSTech）课表无冲突组合求解器。

由于本人的神秘选课，导致怎么选都存在课程冲突，于是就push ai写了个求解的工具

## 功能特性

- **自动爬取**：通过 CAS 认证登录 TIS，自动获取当前学期全部课程数据
- **智能匹配**：输入课程名（如"高等数学（下）"）即可自动匹配所有教学班
- **冲突求解**：回溯算法 + 剪枝优化，高效枚举所有无冲突的课表组合
- **可视化展示**：终端彩色课表矩阵，交互式翻页浏览所有方案
- **硬编码补充**：对于 TIS API 无法查到的课程，支持手动硬编码

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/<your-username>/sustech-course-solver.git
cd sustech-course-solver
```

### 2. 安装依赖

需要 Python 3.10+。

```bash
pip install -r requirements.txt
```

### 3. 配置课程

```bash
cp config.yaml.example config.yaml
```

编辑 `config.yaml`，填入你的学号、密码和想选的课程：

```yaml
student_id: "你的学号"
password: "你的CAS密码"

courses:
  - "高等数学（下）"
  - "大学物理（下）"
  - "概率论与数理统计"
  - "大学化学"
```

> 课程名称需要与 TIS 系统中显示的一致（不需要带班号）。程序会自动匹配该课程下的所有教学班。

凭据也可以不写在文件中，程序运行时会交互式询问。或者设置环境变量：

```bash
export SUSTECH_SID="你的学号"
export SUSTECH_PWD="你的CAS密码"
```

### 4. 运行

```bash
python src/main.py
```

程序会：

1. 读取 `config.yaml` 中的课程列表
2. 登录 TIS 系统
3. 爬取所有课程的教学班和时间信息
4. 求解所有无冲突的排课组合
5. 以彩色课表形式在终端展示，支持交互翻页

## 处理无法查到的课程

TIS 的 API 有时无法返回某些课程（如部分专业选修课）。如果运行后提示某门课未找到，但你确认该课程存在，可以手动硬编码。

编辑 `src/scraper.py`，找到 `_HARDCODED` 字典，按照以下格式添加：

```python
_HARDCODED: dict[str, list[Section]] = {
    "你的课程名": [
        Section(
            course_name="你的课程名",
            section_name="课程名-01班-英文 - 教师姓名",
            section_id="课程代码-01",
            course_type="zynknjxk",
            time_slots=[
                TimeSlot(weekday=2, start_period=3, end_period=4),
                # weekday: 0=周一, 1=周二, 2=周三, 3=周四, 4=周五
                # start_period / end_period: 第几节课 (1-11)
            ],
            teacher="教师姓名",
        ),
    ],
}
```

节次与时间的对应关系：

| 节次 | 时间 |
|------|------|
| 第1节 | 08:00-08:50 |
| 第2节 | 09:00-09:50 |
| 第3节 | 10:20-11:10 |
| 第4节 | 11:20-12:10 |
| 第5节 | 14:00-14:50 |
| 第6节 | 15:00-15:50 |
| 第7节 | 16:20-17:10 |
| 第8节 | 17:20-18:10 |
| 第9节 | 19:00-19:50 |
| 第10节 | 20:00-20:50 |
| 第11节 | 21:10-22:00 |

## 项目结构

```
sustech-course-solver/
├── config.yaml.example  # 配置模板（复制为 config.yaml 使用）
├── requirements.txt     # Python 依赖
├── README.md
└── src/
    ├── main.py          # 主入口
    ├── auth.py          # CAS 登录认证
    ├── scraper.py       # TIS 课程数据爬取与解析
    ├── models.py        # 数据模型 (TimeSlot, Section, Course)
    ├── solver.py        # 回溯求解器
    └── display.py       # 终端课表可视化
```

## 算法说明

求解器将问题建模为约束满足问题（CSP）：

- **变量**：每门课程
- **值域**：该课程的所有教学班
- **约束**：任意两个选中的教学班之间不能有时间重叠

使用回溯搜索（Backtracking）配合以下优化：

- **MRV 启发式**：优先处理教学班数量最少的课程（最受约束的变量优先）
- **O(1) 冲突检测**：用 `set` 记录已占用的 `(星期, 节次)` 对

## 隐私与安全

- `config.yaml` 已加入 `.gitignore`，**不会被提交到 Git 仓库**
- 仅提供 `config.yaml.example` 作为模板，不含任何真实凭据
- 密码支持三种输入方式：配置文件、环境变量、交互式输入（不回显）
- 所有网络请求仅与南科大官方服务器通信（cas.sustech.edu.cn / tis.sustech.edu.cn）
- 本工具仅查询课程信息，**不会执行任何选课/抢课操作**

## 致谢

本项目参考了以下开源项目的 TIS API 交互方式：

- [SUSTech_Tools](https://github.com/GhostFrankWu/SUSTech_Tools) - 南科大 TIS 选课助手
- [SUSTechTISHelper](https://github.com/Fros1er/SUSTechTISHelper) - TIS 暂存课表脚本

## 免责声明

本项目仅供学习研究使用，不用于任何商业目的。使用本工具产生的任何后果由用户自行承担。本工具不会对 TIS 系统进行任何写入操作（不会帮你选课/抢课），仅读取公开的课程信息。

## License

MIT
