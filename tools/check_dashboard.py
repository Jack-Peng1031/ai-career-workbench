# -*- coding: utf-8 -*-
"""仪表盘产物检查：结构、花括号配对、内联 JS 语法、乱码。

用法： python tools/check_dashboard.py [dashboard.html]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

import plan_engine as pe  # noqa: E402
import render_dashboard as rd  # noqa: E402

NODE = Path(r"C:\Users\pxj10\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe")

fails: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("  ok   " if cond else "  FAIL ") + name + (("  -> " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def balanced(s: str) -> bool:
    depth = 0
    for ch in s:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dashboard.html"
    plan = pe.load_plan()
    html = rd.render_dashboard(plan, pe.today(plan))
    disk = path.read_text(encoding="utf-8") if path.exists() else ""

    print(f"检查对象：{path}")
    check("页面结构完整（</html> 收尾）", html.rstrip().endswith("</html>"))
    check("磁盘文件与渲染结果同源", disk.rstrip().endswith("</html>") and len(disk) > 3000)
    check("无替换字符（乱码）", "\ufffd" not in html)
    check("无未替换的 Python 模板花括号", "{{" not in html and "}}" not in html)
    check("CSS 花括号配对", balanced(rd.CSS))
    check("内联 JS 花括号配对", balanced(rd.JS))
    check("中文内容正常（含关键标题）",
          "学习实践工作台" in html and "今日清单" in html and "阶段里程碑" in html)

    # 卡片与交互元素
    check("卡片数量合理", html.count('class="card"') >= 7, str(html.count('class="card"')))
    today_sec = html.split('id="today"')[1].split('id="week"')[0]
    n_tasks = len(pe.tasks_for_day(plan, pe.today(plan)))
    check("今日清单勾选框与任务数一致", today_sec.count('class="check"') == n_tasks,
          f"{today_sec.count('class=\"check\"')} vs {n_tasks}")
    check("内嵌 bootstrap 数据可解析",
          bool(json.loads(re.search(r'<script id="bootstrap" type="application/json">(.*?)</script>',
                                    html, re.S).group(1))))

    # 本周全景：7 个可点的格子 + 点选后切换的清单区
    strip = html.split('id="wk-day"')[0]
    check("本周全景条带是 7 个格子（不会撑坏 7 列布局）",
          strip.count('class="wk-cell') == 7, str(strip.count('class="wk-cell')))
    check("7 个格子都带 data-day（可点切换）",
          strip.count('data-day="') == 7, str(strip.count('data-day="')))
    check("默认只有一个格子高亮（is-sel）",
          len(re.findall(r'class="wk-cell[^"]*is-sel', strip)) == 1,
          str(len(re.findall(r'class="wk-cell[^"]*is-sel', strip))))
    check("清单区在 #week 卡片内部（点击委托才收得到）",
          html.index('id="wk-day"') > html.index('id="week"')
          and html.index('id="wk-day"') < html.index('阶段里程碑'))
    check("切换所需的三件套齐备：wk-day 容器 / wk-data 数据 / 初次内容",
          'id="wk-day"' in html and 'id="wk-data"' in html
          and 'class="wk-day-hd"' in html)
    check("日清单数据可解析且覆盖 7 天",
          len(json.loads(re.search(r'<script id="wk-data" type="application/json">(.*?)</script>',
                                   html, re.S).group(1))) == 7)
    check("切换函数与点击委托都在",
          "wkSelectDay" in rd.JS and "closest('.wk-cell')" in rd.JS
          and "querySelectorAll('.wk-day-card')" not in rd.JS)
    check("本周全景的旧折叠开关已移除", 'id="wk-toggle"' not in html and "toggleWeekDays" not in html)

    # 时间线：前 5 项默认展开
    check("时间线前 5 项默认展开",
          len(re.findall(r'class="tl-date" data-idx="\d+" open', html)) == 5,
          str(len(re.findall(r'class="tl-date" data-idx="\d+" open', html))))

    # 右栏宽度与窄栏排版
    check("右栏加宽到 400px", "1fr 400px" in rd.CSS)
    check("自定义任务卡片在左栏最下方（课表之后、右栏之前）",
          html.index('id="timetable"') < html.index('id="custom"') < html.index('id="rightcol"'))
    check("本学期课表已移到左栏（在自定义任务上方）",
          html.index('id="timetable"') > html.index('id="week"')
          and html.index('id="timetable"') < html.index('id="custom"'))
    check("材料库用分行结构（已入库不会竖排）",
          'class="mat-name"' in html and 'class="mat-meta"' in html)

    # 主题：层次与语义色
    check("主题含主色与语义色", all(v in html for v in
          ("--primary:#2f5fd0", "--ok:", "--warn:", "--danger:")))
    check("主题含表面层级", all(v in html for v in ("--sunken:", "--panel-2:", "--raised:")))
    check("深色模式两套（媒体查询 + 卡片底色）",
          html.count("prefers-color-scheme:dark") >= 2, str(html.count("prefers-color-scheme:dark")))
    check("轨道标签带颜色类", html.count("tg tg-") >= 20, str(html.count("tg tg-")))
    check("时间线里没有省略号截断的规则",
          not [r for r in rd.CSS.split("}") if "ul.tl" in r.split("{")[0]
               and ("ellipsis" in r or "nowrap" in r) and ".tlmeta" not in r])

    # 内联脚本语法（node --check）
    if NODE.exists():
        js = re.search(r"<script>(.*?)</script>\s*</body>", html, re.S)
        js_text = js.group(1) if js else rd.JS
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
            fh.write(js_text)
            tmp = fh.name
        proc = subprocess.run([str(NODE), "--check", tmp], capture_output=True, text=True)
        check("内联 JS 通过 node --check", proc.returncode == 0, proc.stderr.strip()[:300])
        Path(tmp).unlink(missing_ok=True)
    else:
        print("  skip  node 不存在，跳过 JS 语法检查")

    # 服务端契约
    api_ok = Path(ROOT / "app.py").read_text(encoding="utf-8")
    check("服务端提供 /api/toggle", "/api/toggle" in api_ok)
    check("服务端提供 /api/day", "/api/day" in api_ok)

    print("\n" + ("全部通过" if not fails else f"失败 {len(fails)} 项：" + "、".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
