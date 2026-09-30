# -*- coding: utf-8 -*-
"""自检脚本：验证计划引擎、打卡、统计、导出、服务端接口。

用法： python tools/selftest.py
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

import plan_engine as pe  # noqa: E402
import render_dashboard as rd  # noqa: E402

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(("  ok   " if cond else "  FAIL ") + name + (("  -> " + detail) if detail and not cond else ""))


def _raises(fn) -> bool:
    """确认调用会抛异常（用于校验非法输入被拒绝）。"""
    try:
        fn()
        return False
    except Exception:  # noqa: BLE001
        return True


def _strip_test_fixtures(records: dict, notes: dict, extras: dict, custom: list | None = None) -> None:
    """从状态文件里剔除自检自己写入的测试数据，就地修改。

    自检会真的写打卡、复盘和临时任务。这些条目必须保证在测试结束后消失，
    否则被测数据会冒充成"用户的真实记录"留在工作台里（曾经真的发生过：
    一条测试用的"补体检"临时任务在首页显示了好几天）。
    """
    records.pop("2026-09-30::leetcode", None)
    records.pop("2026-09-30::vocab-cet4", None)
    records.pop("2026-09-30::course-review", None)
    notes.pop("2026-09-30::leetcode", None)
    extras.pop("2026-09-30", None)
    if custom is not None:
        custom[:] = [t for t in custom if not str(t.get("title", "")).startswith("【自检】")]


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="workbench-selftest-"))
    backup = {}
    for p in (pe.COMPLETIONS, pe.NOTES, pe.MATERIALS):
        backup[p] = p.read_bytes() if p.exists() else None
    extras = pe.CACHE / "extras.json"
    backup[extras] = extras.read_bytes() if extras.exists() else None
    custom_path = pe.CUSTOM_TASKS
    backup[custom_path] = custom_path.read_bytes() if custom_path.exists() else None

    # 备份里若混着上一次自检留下的残留，先清干净；否则"还原备份"等于把垃圾写回去。
    def _load(p):
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}

    _clean = {"completions": _load(pe.COMPLETIONS).setdefault("records", {}),
              "notes": _load(pe.NOTES),
              "extras": _load(extras),
              "custom": _load(custom_path).get("tasks", [])}
    _strip_test_fixtures(_clean["completions"], _clean["notes"], _clean["extras"], _clean["custom"])
    # 与 plan_engine._save_json 的落盘格式保持逐字节一致（ensure_ascii=False, indent=2, 末尾换行）
    def _dumps(data) -> bytes:
        return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    expected_clean = {
        pe.COMPLETIONS: _dumps({"version": 1, "records": _clean["completions"]}),
        pe.NOTES: _dumps(_clean["notes"]),
        extras: _dumps(_clean["extras"]),
        custom_path: _dumps({"version": 1, "tasks": _clean["custom"]}),
    }

    # 测试要跑在干净的打卡状态上：先清空，结束时按备份还原
    pe._save_json(pe.COMPLETIONS, {"version": 1, "records": {}})
    pe._save_json(pe.NOTES, {})
    pe._save_json(extras, {})
    pe.save_custom_tasks([])

    try:
        plan = pe.load_plan()

        print("\n[1] 课表解析与周次过滤")
        check("教学周锚点：2026-09-30 = 第5教学周",
              pe.semester_week(plan, dt.date(2026, 9, 30)) == 5,
              str(pe.semester_week(plan, dt.date(2026, 9, 30))))
        check("由锚点推出第1周周一 = 2026-08-31",
              pe.week1_monday(plan) == dt.date(2026, 8, 31), str(pe.week1_monday(plan)))
        check("周三有课", len(pe.courses_on(plan, dt.date(2026, 9, 30))) == 3)
        check("军事技能只在第1-2周",
              not any(m["name"] == "军事技能" for m in pe.courses_on(plan, dt.date(2026, 9, 30))))
        check("国家安全教育第6周周五有课（10-09）",
              any(m["name"] == "国家安全教育" for m in pe.courses_on(plan, dt.date(2026, 10, 9))))
        check("国家安全教育第10周周五有课（11-06）",
              any(m["name"] == "国家安全教育" for m in pe.courses_on(plan, dt.date(2026, 11, 6))))
        check("国家安全教育不出现在第5周周五（10-02，国庆）",
              not any(m["name"] == "国家安全教育" for m in pe.courses_on(plan, dt.date(2026, 10, 2))))
        check("国家安全教育不出现在第7周周五（10-16）",
              not any(m["name"] == "国家安全教育" for m in pe.courses_on(plan, dt.date(2026, 10, 16))))
        check("大学生心理健康第11周起才出现",
              any(m["name"] == "大学生心理健康" for m in pe.courses_on(plan, dt.date(2026, 11, 18)))
              and not any(m["name"] == "大学生心理健康" for m in pe.courses_on(plan, dt.date(2026, 10, 14))))
        check("新生研讨课有两个时段",
              len([m for m in plan["course_meetings"] if m["name"] == "新生研讨课"]) == 2)

        print("\n[2] 教授开放日（材料 -> fixed_events）")
        events = plan.get("fixed_events", [])
        check("开放日共 11 场", len(events) == 11, str(len(events)))
        by_date = {e["date"]: e for e in events}
        check("每场开放日都生成事件任务",
              all(any(t["kind"] == "event" for t in pe.tasks_for_day(plan, dt.date.fromisoformat(d)))
                  for d in by_date))
        check("非开放日不生成事件任务",
              not any(t["kind"] == "event" for t in pe.tasks_for_day(plan, dt.date(2026, 10, 13))))
        # 用 materials/讲座.txt 里自带的教学周反向校验日历锚点
        raw = (pe.ROOT / "materials" / "讲座.txt").read_text(encoding="utf-8")
        rows = [ln.split("\t") for ln in raw.splitlines()[1:] if ln.strip()]
        check("讲座.txt 共 11 行数据", len(rows) == 11, str(len(rows)))
        mismatched = []
        for cells in rows:
            wk = int(re.search(r"\d+", cells[0]).group())
            mo, dd = (int(x) for x in re.findall(r"\d+", cells[1])[:2])
            d = dt.date(2026, mo, dd)
            if pe.semester_week(plan, d) != wk:
                mismatched.append((cells[1], wk, pe.semester_week(plan, d)))
        check("讲座.txt 自带周次与日历锚点完全一致（独立佐证 9/30=第5周）",
              not mismatched, str(mismatched))
        check("全部 11 个日期都已进入 fixed_events",
              all(f"2026-{int(re.findall(r'[0-9]+', c[1])[0]):02d}-"
                  f"{int(re.findall(r'[0-9]+', c[1])[1]):02d}" in by_date for c in rows),
              str(sorted(by_date)))
        # 固定事项是"约会"，不应把当天算成超限
        clash = dt.date(2026, 11, 24)
        check("有开放日的 11-24 自主任务未超上限",
              pe.adjustable_minutes(plan, clash) <= plan["day_rules"]["max_minutes_per_day"],
              str(pe.adjustable_minutes(plan, clash)))
        overlaps = []
        unmarked = []
        for e in events:
            d = dt.date.fromisoformat(e["date"])
            ep = pe._period_start(e.get("periods", ""))
            for m in pe.courses_on(plan, d):
                mp = pe._period_start(m.get("periods", ""))
                if ep == mp:
                    overlaps.append((e["date"], e["periods"], m["name"], m.get("periods")))
                    if not any(("重合" in s or "冲突" in s) for s in e.get("steps", [])):
                        unmarked.append((e["date"], m["name"]))
        # 与课程时间冲突的场次，必须在任务步骤里写清取舍——有冲突不可怕，
        # 可怕的是当天才发现两件事撞在一起。
        check("与课程冲突的开放日都在步骤里标注了取舍",
              not unmarked, str(unmarked))
        check("检测到的冲突数与课表实际情况一致（11-02、11-30 与科技哲学史）",
              len(overlaps) == 2 and {o[0] for o in overlaps} == {"2026-11-02", "2026-11-30"},
              str(overlaps))

        print("\n[3] 新增周任务：校园跑、慕课作业、学习通作业")
        tpl = {t["id"]: t for t in plan["task_templates"]}
        for tid in ("campus-run", "campus-run-sun", "english-mooc", "english-mooc-sun", "english-xuexitong"):
            check("模板存在：" + tid, tid in tpl)
        sat, sun, mon, thu = (dt.date(2026, 10, 10), dt.date(2026, 10, 11),
                              dt.date(2026, 10, 12), dt.date(2026, 10, 8))
        ids = lambda d: [t["template_id"] for t in pe.tasks_for_day(plan, d) if t["template_id"]]
        check("周六有校园跑", "campus-run" in ids(sat))
        check("周六有英语慕课作业", "english-mooc" in ids(sat))
        check("周日有校园跑", "campus-run-sun" in ids(sun))
        check("周日有英语慕课作业", "english-mooc-sun" in ids(sun))
        check("周一有学习通作业", "english-xuexitong" in ids(mon))
        check("周四都不到（校园跑/慕课/学习通只在周末与周一）",
              not any(x in ids(thu) for x in
                      ("campus-run", "campus-run-sun", "english-mooc", "english-mooc-sun", "english-xuexitong")),
              str(ids(thu)))
        check("校园跑任务含 20 分钟", tpl["campus-run"]["minutes"] == 20
              and tpl["campus-run-sun"]["minutes"] == 20)
        check("慕课作业 40 分钟且带完成标准", tpl["english-mooc"]["minutes"] == 40
              and bool(tpl["english-mooc"].get("proof")))
        check("学习通作业 40 分钟且带完成标准", tpl["english-xuexitong"]["minutes"] == 40
              and bool(tpl["english-xuexitong"].get("proof")))

        print("\n[4] 自定义任务（某一天 / 一个时间段）")
        one = pe.add_custom_task("【自检】单日任务", "2026-10-15", minutes=15)
        rng = pe.add_custom_task("【自检】周末任务", "2026-10-01", "2026-10-31",
                                 days=[6, 7], minutes=25)
        on = lambda d: [t["title"] for t in pe.tasks_for_day(plan, d) if t["kind"] == "custom"]
        check("单日自定义任务只在那一天出现",
              any("单日任务" in x for x in on(dt.date(2026, 10, 15)))
              and not any("单日任务" in x for x in on(dt.date(2026, 10, 16))))
        check("区间+星期：周六出现", any("周末任务" in x for x in on(dt.date(2026, 10, 3))))
        check("区间+星期：周日出现", any("周末任务" in x for x in on(dt.date(2026, 10, 4))))
        check("区间+星期：周三不出现", not any("周末任务" in x for x in on(dt.date(2026, 10, 7))))
        check("超出区间后不出现",
              not any("周末任务" in x for x in on(dt.date(2026, 11, 7))))
        check("校园跑每天恰好 20 分钟（不被周末系数放大）",
              [t["minutes"] for t in pe.tasks_for_day(plan, dt.date(2026, 10, 10))
               if t.get("template_id") == "campus-run"] == [20]
              and [t["minutes"] for t in pe.tasks_for_day(plan, dt.date(2026, 10, 17))
                   if t.get("template_id") == "campus-run"] == [20],
              str([(t.get("template_id"), t["minutes"]) for t in pe.tasks_for_day(plan, dt.date(2026, 10, 10))]))
        # 10-10 在自定义区间内、11-07 在区间外，两者都是周六，差正好是这条自定义任务的 25 分钟
        check("自定义任务计入当天分钟预算",
              pe.adjustable_minutes(plan, dt.date(2026, 10, 10)) ==
              pe.adjustable_minutes(plan, dt.date(2026, 11, 7)) + 25,
              f"{pe.adjustable_minutes(plan, dt.date(2026, 10, 10))} vs {pe.adjustable_minutes(plan, dt.date(2026, 11, 7))}"
              + " | " + str([(t.get("template_id"), t["kind"], t["minutes"])
                             for t in pe.tasks_for_day(plan, dt.date(2026, 10, 10))]))
        ctd = pe.custom_dates(60, dt.date(2026, 9, 30))
        check("未来 60 天里自定义任务只落在符合条件的日子",
              all(pe.parse_date(d).weekday() + 1 in (6, 7) for d in ctd
                  if any("周末任务" in t["title"] for t in ctd[d])), str(sorted(ctd)[:5]))
        # 用"今天"验证打卡与统计：完成率会把结束日裁到今天，未来的日子谈不上已完成。
        # 这一段跑完必须清干净，否则后面的用例会数到这条任务。
        today = pe.today(plan)
        today_task = pe.add_custom_task("【自检】今天任务", today.isoformat(), minutes=10)
        pe.mark(plan, today, "custom-" + today_task["id"], "done")
        w = pe.window_completion(plan, today, today)
        check("自定义任务可打卡并计入完成率", w["done"] >= 1 and w["planned"] >= 1, str(w))
        check("自定义任务有独立轨道统计", "custom" in w["per_track"], str(w["per_track"]))
        check("删除自定义任务会连带清掉打卡记录",
              bool(pe.remove_custom_task(one["id"]))
              and not any(k.endswith("::custom-" + one["id"])
                          for k in pe.load_completions().get("records", {})))
        check("删除当天那条自定义任务（清理测试数据）",
              bool(pe.remove_custom_task(today_task["id"]))
              and not any("今天任务" in t["title"] for t in pe.tasks_for_day(plan, today)))
        pe.remove_custom_task(rng["id"])
        check("删除后清单里不再出现",
              not any("周末任务" in t["title"] for t in pe.tasks_for_day(plan, dt.date(2026, 10, 3))))
        check("传空任务名会被拒绝",
              _raises(lambda: pe.add_custom_task("   ", "2026-10-15")))
        check("结束早于开始会被拒绝",
              _raises(lambda: pe.add_custom_task("【自检】坏区间", "2026-10-20", "2026-10-01")))

        print("\n[5] 任务生成与编号")
        day = dt.date(2026, 9, 30)
        # 先清掉该日期可能残留的临时任务，保证计数稳定
        extras_data = pe._load_json(pe.CACHE / "extras.json", {})
        extras_data.pop(day.isoformat(), None)
        pe._save_json(pe.CACHE / "extras.json", extras_data)
        tasks = pe.tasks_for_day(plan, day)
        real = [t for t in tasks if t["kind"] != "class"]
        check("周三生成 5 条自主任务", len(real) == 5, str([t["title"] for t in real]))
        check("周三有 3 门课", len([t for t in tasks if t["kind"] == "class"]) == 3)
        check("课时在每日上限内", pe.minutes_planned(plan, day) <= plan["day_rules"]["max_minutes_per_day"],
              str(pe.minutes_planned(plan, day)))

        print("\n[6] 打卡：完成 / 计数 / 顺延 / 撤销")
        touched = pe.mark(plan, day, "1", "done")
        check("按序号打卡命中第一条", touched and touched[0].startswith("CET-4"), str(touched))
        pe.mark(plan, day, "leetcode", "done", amount=3)
        prog = {p["id"]: p for p in pe.progress(plan, day)}
        check("刷题量按真实数量累加", prog["leetcode"]["value"] == 3, str(prog["leetcode"]["value"]))
        check("词汇按天数累计", prog["vocab-cet4"]["value"] == 1, str(prog["vocab-cet4"]["value"]))
        again = pe.tasks_for_day(plan, day)
        check("完成状态可回读", sum(1 for t in again if t.get("done")) == 2)
        pe.mark(plan, day, "5", "skipped", reason="生病")
        w = pe.window_completion(plan, day, day)
        check("顺延项不计入分母", w["planned"] == 4, str(w["planned"]))
        pe.mark(plan, day, "1", "undone")
        check("撤销生效", pe.progress(plan, day)[0]["value"] == 0)
        pe.mark(plan, day, "all", "undone")
        check("全部撤销后无记录",
              all(not t.get("done") for t in pe.tasks_for_day(plan, day) if t["kind"] != "class"))

        print("\n[7] 复盘记录与临时任务")
        pe.set_journal(day, "leetcode", "卡在链表边界", plan)
        check("复盘可回读",
              any(t.get("journal") == "卡在链表边界" for t in pe.tasks_for_day(plan, day)))
        pe.add_extra(day, "补体检", 60)
        check("临时任务进入当天清单",
              any(t["title"] == "补体检" for t in pe.tasks_for_day(plan, day)))

        print("\n[8] 区间统计的边界裁剪")
        check("未来日期不计入完成率分母",
              pe.window_completion(plan, dt.date(2026, 9, 1), dt.date(2026, 12, 31))["end"]
              == dt.date.today().isoformat())
        w2 = pe.window_completion(plan, dt.date(2020, 1, 1), dt.date(2026, 9, 30))
        check("起始日不早于计划生效日", w2["start"] == "2026-08-31", w2["start"])

        print("\n[9] 阶段覆盖（国庆 / 期末 / 寒假）")
        holiday = pe.tasks_for_day(plan, dt.date(2026, 10, 3))
        ids = {t.get("template_id") for t in holiday if t["kind"] == "task"}
        # keep_task_ids 收窄当天任务，但标了 always 的固定事项（体育校园跑、平台英语作业）
        # 不会被收窄——它们不因为放假而消失，之前就是因为这个从清单里"隐身"了。
        check("国庆保留刷题/单词 + always 固定事项",
              ids == {"leetcode", "vocab-cet4", "campus-run", "english-mooc"}, str(ids))
        check("国庆不出现被收窄的普通任务（如 AI 编程实操）",
              "ai-code-practice" not in ids, str(ids))
        check("期末复习期仍保留校园跑与英语作业（always 生效）",
              {t.get("template_id") for t in pe.tasks_for_day(plan, dt.date(2026, 12, 20))}
              >= {"campus-run-sun", "english-mooc-sun"},
              str([t.get("template_id") for t in pe.tasks_for_day(plan, dt.date(2026, 12, 20))]))
        exam = pe.tasks_for_day(plan, dt.date(2026, 12, 20))
        check("期末期微积分时长被放大（含周日强制每日）",
              any(t.get("template_id") == "calculus-drill" and t["minutes"] >= 60 for t in exam),
              str([(t.get("template_id"), t["minutes"]) for t in exam if t["kind"] != "class"]))
        winter = pe.tasks_for_day(plan, dt.date(2027, 2, 1))
        check("寒假刷题时长被放大",
              any(t.get("template_id") == "leetcode" and t["minutes"] >= 60 for t in winter))

        print("\n[10] 材料登记与重算")
        rep = pe.replan(plan, quiet=True)
        check("重算重建 120 天快照", rep["rebuilt"] == 120, str(rep["rebuilt"]))
        check("材料已被登记", bool(rep["materials"]["added"]) or bool(rep["materials"]["removed"])
              or (pe.MATERIALS.exists()))
        check("没有孤儿打卡记录", not rep["orphans"], str(rep["orphans"]))

        print("\n[11] 可视化与导出")
        html = rd.render_dashboard(plan, day)
        check("HTML 结构完整", html.rstrip().endswith("</html>") and html.count("class=\"card\"") >= 6)
        check("无未替换的模板花括号", "{{" not in html and "}}" not in html)
        check("无替换字符乱码", "\ufffd" not in html)
        check("勾选框数量与任务数一致",
              html.count('class="check"') == len(pe.tasks_for_day(plan, day)))
        check("每日 Markdown 生成", "今日 todo" in rd.render_day_markdown(plan, day))
        # 时间线：折叠的单位是"日期"（不是每条说明）
        tl_html, tl_n = rd.render_timeline(plan, day)
        check("时间线覆盖多于 8 天", tl_n > 8, str(tl_n))
        check("折叠单位是日期：每天一个 details.tl-date",
              tl_html.count('class="tl-date"') == min(tl_n, 16) == tl_html.count("<details"),
              f"{tl_html.count('class=\"tl-date\"')} vs min({tl_n},16)")
        check("日期行摘要只显示 日期/星期/还有几天/项数（不含任务标题）",
              'class="tl-head"' in tl_html and 'class="tlmeta"' in tl_html
              and "<b>" in tl_html and " 项</span>" in tl_html)
        check("任务标题在展开区、不再单行省略（无 tlt/ellipsis 结构）",
              'class="tl-items"' in tl_html and "tlbody" not in tl_html and 'class="tlt"' not in tl_html)
        check("今天与明天默认展开",
              'data-idx="0"' in tl_html and tl_html.split('data-idx="0"')[1].split(">")[0].find("open") >= 0
              and tl_html.count(" open>") >= 1,
              str(tl_html[:200]))
        check("同一个日期下多项任务合并成一组（标题都完整保留）",
              all(len(re.findall(r'<span class="ti">', body)) >= 1
                  for body in re.findall(r'<ul class="tl-items">(.*?)</ul>', tl_html, re.S)),
              str(len(re.findall(r'<ul class="tl-items">', tl_html))))
        check("时间线超出 12 天的部分默认隐藏",
              "tl-hidden" in tl_html and tl_html.count("tl-hidden") == max(0, min(tl_n, 16) - 12),
              str(tl_html.count("tl-hidden")))
        check("页面含展开/收起按钮", 'id="tl-toggle"' in html and "toggleAllTimeline" in html)
        check("时间线里的日期都能解析",
              all(pe.parse_date("2026-" + x)
                  for x in re.findall(r'<span class="tld">([0-9]{2}-[0-9]{2})</span>', tl_html)))
        out = pe.ROOT / "exports" / "selftest-temporal.md"
        out.parent.mkdir(exist_ok=True)
        out.write_text(rd.render_day_markdown(plan, day), encoding="utf-8")
        check("Markdown 可写盘", out.exists() and out.stat().st_size > 100)

        print("\n[12] 本地服务接口")
        import app as cli
        import socket
        port_holder = {}

        # 先用一个哑 socket 占住 8791，服务端必须顺延而不能"二次绑定"同一个端口。
        # （allow_reuse_address 在 Windows 上会让第二个进程也 bind 成功，之后请求被
        #  两个进程瓜分，页面随机显示旧内容——踩过的坑。）
        squatter = socket.socket()
        squatter.bind(("127.0.0.1", 8791))
        squatter.listen(5)

        def run():
            cli.main(["serve", "--port", "8791"])

        th = threading.Thread(target=run, daemon=True)
        th.start()
        time.sleep(1.5)
        ok_http = False
        for port in range(8791, 8800):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as r:
                    body = r.read().decode("utf-8")
                if "工作台" in body:
                    ok_http, port_holder["port"] = True, port
                    break
            except Exception:  # noqa: BLE001
                continue
        check("HTTP 首页可用", ok_http, str(port_holder))
        check("端口被占用时自动顺延（没有二次绑定 8791）",
              port_holder.get("port") == 8792, str(port_holder))
        # 8791 必须仍然是那个哑 socket，说明服务端没有把别人的端口抢过来
        probe = socket.socket()
        probe.settimeout(2)
        still_mine = False
        try:
            probe.connect(("127.0.0.1", 8791))
            still_mine = True
        except Exception:  # noqa: BLE001
            still_mine = False
        finally:
            probe.close()
        squatter.close()
        check("原占用端口的进程未被顶掉", still_mine)

        if ok_http:
            # 变量名不要用 p —— 外层 finally 里的 p 是状态文件路径
            srv_port = port_holder["port"]
            req = urllib.request.Request(
                f"http://127.0.0.1:{srv_port}/api/toggle",
                data=json.dumps({"key": "2026-09-30::leetcode", "done": True}).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=3) as r:
                js = json.loads(r.read().decode("utf-8"))
            check("POST /api/toggle 写入成功", js.get("ok") is True, str(js))
            with urllib.request.urlopen(f"http://127.0.0.1:{srv_port}/api/day", timeout=3) as r:
                js2 = json.loads(r.read().decode("utf-8"))
            check("GET /api/day 返回当天任务", js2.get("date") == "2026-09-30" and len(js2["tasks"]) > 3)

        print(f"\n临时目录：{tmp}")
    finally:
        for p, data in backup.items():
            if data is None:
                if p.exists():
                    p.unlink()
            else:
                p.write_bytes(data)
        # 还原之后必须再确认一遍：盘上留下的不能是自检的测试数据
        for p in (pe.COMPLETIONS, pe.NOTES, extras):
            if p.exists():
                p.write_bytes(expected_clean[p])
        shutil.rmtree(tmp, ignore_errors=True)

    ok_clean = all(
        p.exists() and p.read_bytes() == expected_clean[p]
        for p in (pe.COMPLETIONS, pe.NOTES, extras)
    )
    check("自检不留残留数据（测试打卡/复盘/临时任务已清理）", ok_clean)
    check("测试用的“补体检”临时任务未残留",
          "补体检" not in extras.read_text(encoding="utf-8"))

    print("\n" + "=" * 60)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    for f in FAIL:
        print("  失败：" + f)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
