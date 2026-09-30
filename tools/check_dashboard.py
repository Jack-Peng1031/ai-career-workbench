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
    n_tasks = len(pe.tasks_for_day(plan, pe.today(plan)))
    check("勾选框与任务数一致", html.count('class="check"') == n_tasks,
          f"{html.count('class=\"check\"')} vs {n_tasks}")
    check("内嵌 bootstrap 数据可解析",
          bool(json.loads(re.search(r'<script id="bootstrap" type="application/json">(.*?)</script>',
                                    html, re.S).group(1))))

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
