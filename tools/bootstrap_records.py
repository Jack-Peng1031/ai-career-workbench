# -*- coding: utf-8 -*-
"""一次性初始化：建好记录区目录与模板文件，然后重算计划。

用法： python tools/bootstrap_records.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

sys.path.insert(0, str(ROOT))

TEMPLATES = {
    "records/code/刷题日志.md": """# 刷题日志

> 每完成一次就加一行；`--amount` 填的数量要与这里对得上。
> 命令：`python app.py done leetcode --amount 3`

| 日期 | 题号与题目 | 难度 | 卡点 | 复杂度 | 是否独立写出 |
|---|---|---|---|---|---|
|  |  |  |  |  |  |

## 首月专题顺序（照这个走，别乱跳）

1. 数组与字符串（遍历、双指针入门）
2. 哈希表（计数、去重、两数之和系列）
3. 双指针与滑动窗口
4. 二分查找（含答案二分）
5. 栈与队列（单调栈）
6. 递归与回溯（子集、排列、组合）
7. 链表（反转、快慢指针、环）
8. 二叉树（遍历、递归三要素、层序）
9. 基础动态规划（爬楼梯、背包入门）
10. 排序与贪心

## 每周节奏

- 周一至周五：1—2 题，40—50 分钟
- 周六：3—4 题（含 1 题限时训练）
- 周日：复盘错题，把卡壳的题重写一遍
""",
    "records/english/生词本.md": """# CET-4 生词本

> 每天把"连续错"的 5 个词抄进来，第二天与第三天各回滚一次。
> 目标：2026-12-12 四级考试前核心词过完第一遍。

| 日期 | 单词 | 词性/释义 | 我为什么记不住 |
|---|---|---|---|
|  |  |  |  |

## 高频易错（自己补充）

- 
""",
    "records/english/模考记录.md": """# CET-4 模考记录

> 严格计时 125 分钟，一次做完写作 + 听力 + 阅读 + 翻译。
> 命令：`python app.py done english-mock --amount <总分>`

| 日期 | 总分 | 听力 | 阅读 | 写作 | 翻译 | 本次最弱题型 | 下周专项 |
|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |
""",
    "records/research/前沿阅读.md": """# 前沿阅读（每周 1 篇，三句话摘要）

> 只读科普/综述解读，别硬啃论文。攒到 12 篇后，回头看自己更被哪个方向吸引。

## 模板

**标题 / 链接**：
- 解决什么问题：
- 怎么做的：
- 和我学的哪门课有关：

---

（从下面开始逐条累积）
""",
    "records/research/导师与方向.md": """# 导师与方向（信息侦察成果）

## 三个感兴趣的方向

| 方向 | 为什么感兴趣 | 大三对应课程 | 现在能准备什么 |
|---|---|---|---|
| 计算机视觉 |  | 计算机视觉与数字图像处理 | 跑图像分类 demo |
| 自然语言处理 |  | 自然语言处理 | 文本分类小项目 |
| 大模型与生成式 AI |  | 大模型概论及应用 | 开源模型微调 demo |

## 关注的老师

| 姓名 | 方向 | 信息来源 | 是否联系过 |
|---|---|---|---|
|  |  |  |  |

## 待查清

- [ ] 学院科研创新训练-1 的报名时间与导师名单
- [ ] 实验室/课题组纳新时间与门槛
- [ ] 算法队或 ACM 集训队的选拔方式
""",
    "records/info/保研细则存档.md": """# 保研细则存档（30 天里程碑的硬任务）

> 目标：30 天内查清并存档。**这是投入产出比最高的一次信息侦察。**

- [ ] 综合成绩的构成公式（绩点 : 科研 : 竞赛 : 英语 : 德育 的比例）
- [ ] 绩点如何计算（是否含重修、是否按学分加权、排名口径）
- [ ] 加分项清单与上限（哪些竞赛算、哪些不算）
- [ ] 近三年本专业的推免名额与录取名次区间
- [ ] 英语门槛（六级分数要求、是否有雅思托福替代）
- [ ] 时间节点（夏令营投递、预推免、推免系统开放）

## 来源记录

| 日期 | 来源（辅导员/教务处/学院通知/学长） | 要点 | 凭证 |
|---|---|---|---|
|  |  |  |  |

## 待核对

- 本文件所有内容在**大二开学时重查一次**：政策可能修订。
""",
    "records/reviews/README.md": """# 每周复盘

每周日花 30 分钟，新建 `2026-W40.md`（年份-第几周），按下面三行写：

```markdown
# 2026 年第 40 周复盘

- 完成率：python app.py report 显示 __%
- 做对了什么：
- 失控点在哪：
- 下周只改一件事：
- 计划要改哪里：（改完跑 python app.py replan）
```

**只改一件事**：每周只允许调整一个变量，否则你无法判断是哪一步带来了变化。
""",
    "records/code/模板/README.md": """# 算法模板库

按专题存放，供蓝桥杯/竞赛与日常刷题复用。建议顺序：

- `枚举与模拟.md`
- `排序与贪心.md`
- `搜索_DFS_BFS.md`
- `递推与基础DP.md`
- `数论与组合.md`
- `二分与双指针.md`

每个模板文件里放：适用场景、代码骨架、1 道例题、常见坑。
""",
}

DIRS = [
    "records/code/ai-basics",
    "records/code/模板",
    "records/english",
    "records/research",
    "records/info",
    "records/reviews",
    "materials",
    "state/cache/days",
    "exports/daily",
]


def main() -> int:
    for d in DIRS:
        (ROOT / d).mkdir(parents=True, exist_ok=True)
        print("  dir  " + d)
    for rel, text in TEMPLATES.items():
        p = ROOT / rel
        if p.exists():
            print("  skip " + rel + "（已存在，不覆盖）")
            continue
        p.write_text(text, encoding="utf-8")
        print("  new  " + rel)

    import plan_engine as pe
    import render_dashboard as rd
    plan = pe.load_plan()
    rep = pe.replan(plan)
    rd.write_dashboard(plan)
    print("\n已登记材料 %d 个，重建快照 %d 天，dashboard.html 已刷新。"
          % (len(rep["materials"]["added"]), rep["rebuilt"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
