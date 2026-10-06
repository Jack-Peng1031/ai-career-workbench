# -*- coding: utf-8 -*-
"""验证线上页面：新功能是否真的生效（拉真实 HTML 与 API 检查）。"""
import json
import re
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
BASE = "https://jackpeng.pythonanywhere.com"


def get(path: str, timeout: int = 60):
    req = urllib.request.Request(BASE + path, headers={"Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


checks = []


def check(name, cond, detail=""):
    checks.append((name, bool(cond), detail))
    print(("  ok   " if cond else "  FAIL ") + name + (("  -> " + str(detail)) if detail and not cond else ""))


status, body = get("/")
html = body.decode("utf-8", "replace")
print(f"首页 HTTP {status}，{len(body)} 字节\n")

check("首页可访问", status == 200 and len(body) > 40000, len(body))
check("是新版（本周全景改点选式）", "点任意一天的格子" in html)
check("7 个格子可点、默认只高亮一个",
      html.count('class="wk-cell') == 7
      and len(re.findall(r'class="wk-cell[^"]*is-sel', html)) == 1,
      f"{html.count('class=\"wk-cell')} / "
      f"{len(re.findall(r'class=.wk-cell[^\"]*is-sel', html))}")
check("清单区与切换数据都在线上",
      'id="wk-day"' in html and 'id="wk-data"' in html and "wkSelectDay" in html)
wk_days = {}
try:
    wk_days = json.loads(re.search(r'<script id="wk-data" type="application/json">(.*?)</script>',
                                   html, re.S).group(1))
    check("线上日清单数据覆盖 7 天", len(wk_days) == 7, len(wk_days))
except Exception as exc:  # noqa: BLE001
    check("线上日清单数据覆盖 7 天", False, str(exc)[:120])
check("格子下面确实有任务（当前那一天的清单）",
      html.count('class="wk-tt"') >= 3, html.count('class="wk-tt"'))
check("切换数据里 7 天都有任务内容",
      sum(1 for v in wk_days.values() if 'class="wk-tt"' in v) >= 6,
      sum(1 for v in wk_days.values() if 'class="wk-tt"' in v))
check("时间线前 5 项默认展开",
      len(re.findall(r'class="tl-date" data-idx="\d+" open', html)) == 5,
      len(re.findall(r'class="tl-date" data-idx="\d+" open', html)))
check("右栏已加宽", "1fr 400px" in html)
check("课表与自定义任务都在左栏",
      html.index('id="timetable"') < html.index('id="custom"') < html.index('id="rightcol"'))
check("材料库分行排版（已入库不竖排）", 'class="mat-name"' in html)
check("新主题主色已生效", "--primary:#2f5fd0" in html)
check("五层表面变量在", all(v in html for v in ("--sunken:", "--panel-2:", "--raised:")))
check("深色模式两套在", html.count("prefers-color-scheme:dark") >= 2,
      html.count("prefers-color-scheme:dark"))
check("轨道配色标签已渲染", html.count("tg tg-") >= 20, html.count("tg tg-"))
check("折叠单位仍是日期（时间线）", 'class="tl-date"' in html)
check("自定义任务表单在", 'id="ct-form"' in html)
check("没有乱码", "\ufffd" not in html)
check("没有未替换的模板花括号", "{{" not in html and "}}" not in html)

# 页面里的日期与远端渲染日期一致
m = re.search(r'data-today="([0-9-]+)"', html)
print("页面 data-today =", m.group(1) if m else "(未找到)")

print()
status, body = get("/api/day")
try:
    js = json.loads(body.decode("utf-8"))
    check("GET /api/day 可用", status == 200 and len(js.get("tasks", [])) > 0,
          f"HTTP {status} {str(js)[:120]}")
    print(f"       /api/day -> {js.get('date')} 第{js.get('week')}周 {len(js['tasks'])} 项")
except Exception as exc:  # noqa: BLE001
    check("GET /api/day 可用", False, str(exc))

status, body = get("/api/day?date=2026-10-09")
try:
    js = json.loads(body.decode("utf-8"))
    check("GET /api/day?date=2026-10-09（国家安全教育那天）",
          status == 200 and js.get("date") == "2026-10-09",
          f"HTTP {status} {str(js)[:120]}")
    print(f"       -> {js.get('date')} 第{js.get('week')}周 {len(js['tasks'])} 项")
except Exception as exc:  # noqa: BLE001
    check("GET /api/day?date=2026-10-09", False, str(exc))

bad = [c for c in checks if not c[1]]
print("\n" + ("线上验证全部通过 ✅" if not bad else f"失败 {len(bad)} 项：" + "、".join(c[0] for c in bad)))
sys.exit(1 if bad else 0)
