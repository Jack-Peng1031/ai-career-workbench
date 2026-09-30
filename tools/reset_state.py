# -*- coding: utf-8 -*-
"""重置打卡状态（保留计划与材料）。

用法：
    python tools/reset_state.py                 # 清空打卡与复盘，保留临时任务
    python tools/reset_state.py --purge-extras  # 连临时任务一起清空
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

import plan_engine as pe  # noqa: E402
import render_dashboard as rd  # noqa: E402

purge = "--purge-extras" in sys.argv

pe.save_completions({"version": 1, "records": {}})
print("  已清空 state/completions.json")
pe._save_json(pe.NOTES, {})
print("  已清空 state/notes.json")
if purge:
    pe._save_json(pe.CACHE / "extras.json", {})
    print("  已清空 state/cache/extras.json")
else:
    extras = pe._load_json(pe.CACHE / "extras.json", {})
    print("  保留 %d 天的临时任务" % len(extras))

plan = pe.load_plan()
rd.write_dashboard(plan)
print("  计划与 dashboard.html 已刷新（材料指纹未动）")
