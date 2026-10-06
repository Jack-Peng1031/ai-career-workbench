# -*- coding: utf-8 -*-
"""命令行工作台：每天生成 todo、确认完成、出报告、加材料后重算。

用法示例
--------
python app.py today                      # 生成今天的 todo 清单
python app.py today --date 2026-10-08    # 指定某天
python app.py week                       # 未来 7 天一览
python app.py done 1 2 3                 # 确认完成（按清单序号）
python app.py done leetcode --amount 3   # 确认完成并填写真实数量（如刷了3题）
python app.py undone 2                   # 撤销
python app.py skip 2 --reason "生病"      # 顺延，不计入未完成
python app.py note 4 "今天卡在链表中点"    # 记一句复盘
python app.py add "导师组会旁听" --minutes 60
python app.py report                     # 今日+本周+区间报告
python app.py report --month / --quarter / --year
python app.py replan                     # 加了新材料后重算全部未来清单
python app.py export --days 30           # 导出可打印的 Markdown 打卡表
python app.py serve --port 8765          # 打开可视化工作台
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

try:  # 保证中文在管道/重定向时也按 UTF-8 输出
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

import plan_engine as pe
import render_dashboard as rd

ROOT = Path(__file__).resolve().parent
DASH = ROOT / "dashboard.html"
EXPORT_DIR = ROOT / "exports"

OK = "[OK]"
NO = "[--]"


def _slot(tasks: list[dict], position: int) -> int:
    """把"第几条自主任务"换算成它在 tasks 里的序号（课程行不参与编号）。"""
    n = 0
    for i, t in enumerate(tasks, 1):
        if t["kind"] == "class":
            continue
        n += 1
        if n == position:
            return i
    return position





# --------------------------------------------------------------------------
def cmd_today(args) -> int:
    plan = pe.load_plan()
    day = pe.parse_date(args.date) if args.date else pe.today(plan)
    tasks = pe.tasks_for_day(plan, day)
    week = pe.semester_week(plan, day)
    phase = pe.current_phase(plan, day)

    print("=" * 74)
    print(f"  {day.isoformat()}  {pe.WEEKDAY_CN[day.weekday()]}   {'第 %d 教学周' % week if week else '非教学周'}")
    print(f"  {plan['student']['university']} {plan['student']['major']} {plan['student']['cohort']}"
          f"   |   目标：{plan['student']['goal']}")
    print("=" * 74)
    if phase:
        print(f"  当前阶段：{phase.get('title','')}（{phase['from']} ~ {phase['to']}）")
        note = phase.get("note") or phase.get("intro")
        if note:
            print(f"  {note}")
        print("-" * 74)

    courses = [t for t in tasks if t["kind"] == "class"]
    if courses:
        print("\n【今天的课】")
        for t in courses:
            print(f"   · {t['title']}　{t['steps'][0] if t['steps'] else ''}")

    real = [t for t in tasks if t["kind"] != "class"]
    done = sum(1 for t in real if t.get("done"))
    total = sum(t["minutes"] for t in real)
    print(f"\n【今日 todo】完成 {done}/{len(real)}　计划投入 {total} 分钟\n")

    slot = 0
    for t in tasks:
        if t["kind"] == "class":
            continue
        slot += 1
        mark = OK if t.get("done") and not t.get("skipped") else (NO if not t.get("skipped") else "[>>]")
        star = "★" if t.get("track") in ("gpa", "code") else " "
        print(f"  {mark}{star} {slot:>2}. {t['title']}　({t['minutes']} 分钟)")
        for s in t.get("steps", []):
            print(f"        - {s}")
        if t.get("proof"):
            print(f"        完成标准：{t['proof']}")
        if t.get("note"):
            print(f"        提示：{t['note']}")
        if t.get("journal"):
            print(f"        记录：{t['journal']}")
        print()

    for msg in pe.clamp_day(plan, day):
        print(f"  ! {msg}")
    prog = [p for p in pe.progress(plan, day) if p.get("target")]
    if prog:
        print("\n【累计进度】")
        for p in prog:
            ratio = f"{p['ratio']*100:5.1f}%" if p.get("ratio") is not None else "  n/a"
            print(f"  {ratio}  {p['title']}：{p['value']:g}/{p['target']:g} {p['unit']}"
                  + (f"（{p['target_by']} 前）" if p.get("target_by") else ""))
    st = pe.streak(plan, "leetcode", day)
    sv = pe.streak(plan, "vocab-cet4", day)
    print(f"\n  连续打卡：刷题 {st} 天　单词 {sv} 天")
    print(f"  确认已完成：python app.py done 1 2 3　（撤销：app.py undone 1）")
    print("  ★ = 保研权重最高的两件事：绩点与编程\n")
    return 0


def cmd_week(args) -> int:
    plan = pe.load_plan()
    base = pe.parse_date(args.date) if args.date else pe.today(plan)
    lines = []
    for i in range(int(args.days)):
        d = base + dt.timedelta(days=i)
        tasks = pe.tasks_for_day(plan, d)
        real = [t for t in tasks if t["kind"] != "class"]
        courses = [t for t in tasks if t["kind"] == "class"]
        done = sum(1 for t in real if t.get("done"))
        mins = sum(t["minutes"] for t in real)
        lines.append((d, courses, real, done, mins))
    print("=" * 92)
    print(f"  {base.isoformat()} 起 {args.days} 天一览　（✓=已完成　○=待完成）")
    print("=" * 92)
    for d, courses, real, done, mins in lines:
        week = pe.semester_week(plan, d)
        head = f"{d.isoformat()} {pe.WEEKDAY_CN[d.weekday()]}" + (f" 第{week}周" if week else "")
        print(f"\n{head}　课 {len(courses)} 门　任务 {done}/{len(real)}　{mins} 分钟")
        if courses:
            print("   课：" + "、".join(c["title"].split("（")[0] for c in courses))
        for i, t in enumerate(real, 1):
            print(f"   {'✓' if t.get('done') else '○'} {t['title']}（{t['minutes']}m）")
    print()
    return 0


def cmd_mark(args, status: str) -> int:
    plan = pe.load_plan()
    day = pe.parse_date(args.date) if args.date else pe.today(plan)
    if not args.selectors:
        print("请给出要标记的任务序号或任务 id，例如：python app.py done 1 2 3")
        return 2
    all_touched = []
    for sel in args.selectors:
        touched = pe.mark(plan, day, sel, status=status,
                          amount=getattr(args, "amount", None),
                          reason=getattr(args, "reason", "") or "")
        if not touched:
            print(f"  ? 没找到匹配「{sel}」的任务，先运行 python app.py today 看看序号")
        all_touched += touched
    for t in all_touched:
        label = {"done": "已完成", "undone": "已撤销", "skipped": "已顺延"}[status]
        print(f"  {label}：{t}")
    tasks = [t for t in pe.tasks_for_day(plan, day) if t["kind"] != "class"]
    done = sum(1 for t in tasks if t.get("done"))
    print(f"\n  {day.isoformat()} 进度：{done}/{len(tasks)}")
    rd.write_dashboard(plan, day)
    return 0


def cmd_note(args) -> int:
    plan = pe.load_plan()
    day = pe.parse_date(args.date) if args.date else pe.today(plan)
    touched = pe.set_journal(day, args.selector, args.text, plan)
    if not touched:
        print("没找到对应任务。")
        return 2
    for t in touched:
        print(f"  已记录到：{t}")
    rd.write_dashboard(plan, day)
    return 0


def cmd_add(args) -> int:
    plan = pe.load_plan()
    day = pe.parse_date(args.date) if args.date else pe.today(plan)
    pe.add_extra(day, args.title, args.minutes)
    print(f"  已为 {day.isoformat()} 增加临时任务：{args.title}（{args.minutes} 分钟）")
    rd.write_dashboard(plan, day)
    return 0


def cmd_addtask(args) -> int:
    plan = pe.load_plan()
    days = []
    for part in str(getattr(args, "days", "") or "").replace("，", ",").split(","):
        part = part.strip()
        if part:
            try:
                days.append(int(part))
            except ValueError:
                print(f"  --days 需要 1-7 的数字（周一到周日），收到：{part}")
                return 2
    steps = [s.strip() for s in str(args.steps or "").split("|") if s.strip()]
    try:
        task = pe.add_custom_task(
            title=args.title, from_date=args.from_date, to_date=args.to_date,
            days=days, minutes=args.minutes, steps=steps, proof=args.proof)
    except ValueError as exc:
        print(f"  添加失败：{exc}")
        return 2
    rng = task["from"] if task["to"] == task["from"] else task["from"] + " ~ " + task["to"]
    wd = ("　限 " + "、".join(pe.WEEKDAY_CN[d - 1] for d in days)) if days else ""
    print(f"已添加自定义任务：{task['title']}（{rng}{wd}　{task['minutes']} 分钟）")
    print(f"  id = {task['id']}　（删除：python app.py deltask {task['id']}）")
    rd.write_dashboard(plan, pe.today(plan))
    print("  dashboard.html 已刷新；网页端可在「自定义任务」卡片里看到并删除。")
    return 0


def cmd_tasks(args) -> int:
    items = pe.load_custom_tasks()
    if not items:
        print("还没有自定义任务。添加：python app.py addtask \"任务名\" --from 2026-10-03 --to 2026-10-31 --days 6,7")
        return 0
    print(f"共 {len(items)} 个自定义任务：")
    for t in sorted(items, key=lambda z: (z.get("from", ""), z.get("title", ""))):
        rng = t["from"] if t.get("to", t["from"]) == t["from"] else t["from"] + " ~ " + t["to"]
        days = t.get("days") or []
        wd = ("　限 " + "、".join(pe.WEEKDAY_CN[int(d) - 1] for d in days)) if days else ""
        print(f"  · [{t['id']}] {t['title']}　{rng}{wd}　{t.get('minutes', 0)} 分钟")
    return 0


def cmd_deltask(args) -> int:
    hit = pe.remove_custom_task(args.task_id)
    if not hit:
        print(f"  找不到自定义任务：{args.task_id}（用 python app.py tasks 查看）")
        return 2
    print(f"已删除：{hit['title']}（相关打卡记录一并清除）")
    rd.write_dashboard(pe.load_plan(), pe.today(pe.load_plan()))
    return 0


def _report_block(plan: dict, days: int, label: str, base: dt.date) -> None:
    start = base - dt.timedelta(days=days - 1)
    w = pe.window_completion(plan, start, base)
    ratio = f"{w['ratio']*100:.1f}%" if w["ratio"] is not None else "n/a"
    print(f"\n【{label}】{w['start']} ~ {w['end']}　完成 {w['done']}/{w['planned']}　{ratio}")
    names = {t["id"]: t["name"] for t in plan.get("tracks", [])}
    for tid, v in sorted(w["per_track"].items(), key=lambda kv: -kv[1]["planned"]):
        r = f"{v['ratio']*100:5.1f}%" if v["ratio"] is not None else "  n/a"
        print(f"   {r}  {names.get(tid, tid):<18} {v['done']}/{v['planned']}")


def cmd_report(args) -> int:
    plan = pe.load_plan()
    base = pe.parse_date(args.date) if args.date else pe.today(plan)
    print("=" * 74)
    print(f"  学习实践报告　基准日 {base.isoformat()}")
    print("=" * 74)

    if getattr(args, "range", None):
        try:
            lo_s, _, hi_s = args.range.partition("..")
            lo = pe.parse_date(lo_s.strip())
            hi = pe.parse_date(hi_s.strip()) if hi_s.strip() else base
        except ValueError:
            print("  --range 需要形如 2026-09-30..2026-12-31")
            return 2
        w = pe.window_completion(plan, lo, hi)
        ratio = f"{w['ratio']*100:.1f}%" if w["ratio"] is not None else "n/a"
        clamped = pe.parse_date(w["end"]) != hi or pe.parse_date(w["start"]) != lo
        if clamped:
            # 区间被裁剪时，直接显示裁剪后的实际统计范围，避免出现 "10-01 ~ 09-30" 这种倒序区间
            span = (f"{w['start']} ~ {w['end']}" if pe.parse_date(w["start"]) <= pe.parse_date(w["end"])
                    else "无（整段都在今天之后）")
            print(f"\n【指定区间】{lo} ~ {hi} → 实际统计 {span}"
                  f"　完成 {w['done']}/{w['planned']}　{ratio}")
        else:
            print(f"\n【指定区间】{w['start']} ~ {w['end']}　完成 {w['done']}/{w['planned']}　{ratio}")
        # 裁剪规则：结束日不晚于今天、开始日不早于计划生效日。裁剪了就说清楚，
        # 否则"查未来 90 天"只会看到一排 0/0 而不知道为什么。
        if pe.parse_date(w["end"]) != hi:
            print(f"   （提示：{hi} 还没到，统计只算到今天 {w['end']}）")
        if pe.parse_date(w["start"]) != lo:
            print(f"   （提示：计划自 {w['start']} 起生效，{lo} 之前没有安排）")
        if w["planned"] == 0:
            print("   （这段区间内没有可统计的自主任务）")
        names = {t["id"]: t["name"] for t in plan.get("tracks", [])}
        for tid, v in sorted(w["per_track"].items(), key=lambda kv: -kv[1]["planned"]):
            r = f"{v['ratio']*100:5.1f}%" if v["ratio"] is not None else "  n/a"
            print(f"   {r}  {names.get(tid, tid):<18} {v['done']}/{v['planned']}")
    else:
        if args.month or args.quarter or args.year or not any([args.month, args.quarter, args.year]):
            _report_block(plan, 30, "近一个月（已过完的日子）", base)
        if args.quarter or args.year:
            _report_block(plan, 90, "近 90 天", base)
        if args.year:
            _report_block(plan, 365, "近一年", base)

    print("\n【累计目标进度】")
    for p in pe.progress(plan, base):
        if not p.get("target"):
            continue
        bar = "█" * int((p["ratio"] or 0) * 20) + "░" * (20 - int((p["ratio"] or 0) * 20))
        print(f"   {bar} {p['value']:>6g}/{p['target']:<6g} {p['unit']:<3} {p['title']}")

    print("\n【里程碑】")
    for m in plan.get("milestones", []):
        due = pe.parse_date(m["due"])
        left = (due - base).days
        state = "已到期" if left < 0 else f"还剩 {left} 天"
        print(f"\n   {m['title']}（{m['due']}，{state}）")
        for c in m.get("checks", []):
            print(f"     □ {c}")

    kd = [k for k in plan.get("key_dates", []) if pe.parse_date(k["date"]) >= base]
    if kd:
        print("\n【即将到来的关键日期】")
        for k in sorted(kd, key=lambda z: z["date"])[:8]:
            d = (pe.parse_date(k["date"]) - base).days
            print(f"   {k['date']}（{d:>3} 天后）{k['title']}　→ {k.get('action','')}")
    print()
    return 0


def cmd_replan(args) -> int:
    plan = pe.load_plan()
    report = pe.replan(plan)
    rd.write_dashboard(plan)
    print("\n计划已重算，dashboard.html 已刷新。")
    if report["materials"]["added"] or report["materials"]["changed"]:
        print("提示：新材料已登记。要真正改计划，请编辑 plan.json 的以下区块，再执行一次本命令：")
        print("  · course_meetings  课表变动")
        print("  · task_templates   新增/调整每日与每周任务")
        print("  · key_dates        新的考试、报名、竞赛截止日")
        print("  · phase_overrides  期中、期末、假期等阶段节奏")
        print("  · milestones       30天/90天/一年的验收标准")
    return 0


def cmd_export(args) -> int:
    plan = pe.load_plan()
    base = pe.parse_date(args.date) if args.date else pe.today(plan)
    EXPORT_DIR.mkdir(exist_ok=True)
    days = int(args.days)
    out = EXPORT_DIR / f"checklist-{base.isoformat()}-{days}d.md"
    lines = [f"# 打卡清单（{base.isoformat()} 起 {days} 天）", "",
             f"> 由 `python app.py export --days {days}` 生成；勾选后可用 `python app.py done <序号>` 记录。", ""]
    for i in range(days):
        d = base + dt.timedelta(days=i)
        tasks = pe.tasks_for_day(plan, d)
        week = pe.semester_week(plan, d)
        real = [t for t in tasks if t["kind"] != "class"]
        courses = [t for t in tasks if t["kind"] == "class"]
        lines.append(f"## {d.isoformat()}（{pe.WEEKDAY_CN[d.weekday()]}）"
                     + (f" 第 {week} 教学周" if week else ""))
        if courses:
            lines.append("")
            lines.append("**课程**：" + "、".join(c["title"].split("（")[0] for c in courses))
        lines.append("")
        for t in real:
            box = "x" if t.get("done") else " "
            lines.append(f"- [{box}] {t['title']}（{t['minutes']} 分钟）")
            for s in t.get("steps", []):
                lines.append(f"  - {s}")
        lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"已导出：{out}")
    return 0


def cmd_materials(args) -> int:
    plan = pe.load_plan()
    mat = plan.get("materials", {})
    mdir = ROOT / mat.get("dir", "materials")
    mdir.mkdir(exist_ok=True)
    fp = pe.material_fingerprint(plan)
    print(f"材料目录：{mdir}")
    if not fp:
        print("  （空）把课程大纲、校历、保研细则等文件放进来即可。")
    for k, v in fp.items():
        print(f"  · {k}　{v['size']} B　{v['mtime']}")
    print("\n待补充清单：")
    for x in mat.get("pending_intake", []):
        print(f"  □ {x}")
    rules = mat.get("intake_rules")
    if rules:
        print("\n格式要求（material intake rules）：")
        print("  " + rules.get("summary", ""))
        print("  可读格式：" + "、".join(rules.get("extensions", [])))
        print("  编码：" + rules.get("encoding", ""))
        naming = rules.get("naming", {})
        print("  命名：" + naming.get("normal", ""))
        print("        " + naming.get("underscore_prefix", ""))
        print("  " + rules.get("office_files", ""))
        print("  推荐写法：")
        for s in rules.get("preferred_shape", []):
            print("    - " + s)
        print("  " + rules.get("after_adding", ""))
    print("\n放入文件后运行：python app.py replan")
    if getattr(args, "guide", False):
        print("""
——————————————————————————————————————————————————————————————
新增材料后，如何让我（AI）修订计划：
1) 把文件放进 materials/（.md / .txt / .csv / .docx / .pdf / .xlsx 都可以）；
2) 运行 python app.py replan，材料会被登记并提示；
3) 若要让计划真正变化，编辑 plan.json 对应区块后再次运行 replan。
   也可以直接把材料发给我，我会读完后改好 plan.json。
——————————————————————————————————————————————————————————————""")
    return 0


def cmd_report_serve(args) -> int:
    import socket
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class ExclusiveHTTPServer(ThreadingHTTPServer):
        """禁止"二次绑定同一个端口"。

        http.server 默认 allow_reuse_address = 1，Windows 上 SO_REUSEADDR 的语义
        和 Unix 不同：它允许第二个进程绑定到已经被监听的同一个地址端口，之后
        连接会被系统随机分给两个进程。结果就是——重启服务后，旧进程还在的话，
        页面会随机显示旧内容，而且刷新多少次都不稳定（真的踩过：两个 python
        同时 LISTENING 8765，请求一半命中旧代码）。
        这里用 SO_EXCLUSIVEADDRUSE 独占端口，占用时 bind 直接失败，由上面的
        for candidate 循环自动顺延到下一个端口。
        """

        allow_reuse_address = False

        def server_bind(self):
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()

    plan = pe.load_plan()
    day = pe.parse_date(args.date) if getattr(args, "date", None) else pe.today(plan)
    rd.write_dashboard(plan, day)
    rendered = {"date": day}  # 记着页面是按哪一天渲染的，跨夜时重算
    root = ROOT

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *a):  # 安静模式
            pass

        def _send(self, code, body: bytes, ctype="application/json; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path, _, query = self.path.partition("?")
            if path in ("/", "/index.html", "/dashboard.html"):
                # 服务可能跨夜运行：日期变了就重算一次页面，避免第二天还在展示昨天的清单
                today_now = pe.today(pe.load_plan())
                if today_now != rendered["date"] and not getattr(args, "date", None):
                    rd.write_dashboard(pe.load_plan(), today_now)
                    rendered["date"] = today_now
                data = DASH.read_bytes()
                return self._send(200, data, "text/html; charset=utf-8")
            if path == "/api/day":
                pl = pe.load_plan()
                d = day if getattr(args, "date", None) else pe.today(pl)
                # 允许 ?date=YYYY-MM-DD 查询任意一天，便于核对未来/历史清单
                wanted = ""
                for pair in query.split("&"):
                    k, _, v = pair.partition("=")
                    if k == "date" and v:
                        wanted = v
                if wanted:
                    try:
                        d = pe.parse_date(wanted)
                    except Exception:  # noqa: BLE001
                        return self._send(400, json.dumps(
                            {"ok": False, "error": "日期格式应为 YYYY-MM-DD：" + wanted},
                            ensure_ascii=False).encode())
                tasks = pe.tasks_for_day(pl, d)
                return self._send(200, json.dumps(
                    {"date": d.isoformat(), "week": pe.semester_week(pl, d),
                     "tasks": tasks}, ensure_ascii=False).encode())
            target = (root / path.lstrip("/")).resolve()
            if str(target).startswith(str(root)) and target.is_file():
                ctype = "text/plain; charset=utf-8"
                if target.suffix == ".json":
                    ctype = "application/json; charset=utf-8"
                elif target.suffix == ".md":
                    ctype = "text/markdown; charset=utf-8"
                return self._send(200, target.read_bytes(), ctype)
            return self._send(404, b'{"ok":false,"error":"not found"}')

        def do_POST(self):
            route = self.path.split("?")[0]
            if route not in ("/api/toggle", "/api/custom", "/api/custom/delete"):
                return self._send(404, b'{"ok":false,"error":"not found"}')
            length = int(self.headers.get("Content-Length") or 0)
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if route == "/api/custom":
                    task = pe.add_custom_task(
                        title=payload.get("title", ""),
                        from_date=payload.get("from", ""),
                        to_date=payload.get("to", ""),
                        days=payload.get("days") or [],
                        minutes=payload.get("minutes", 30),
                        steps=payload.get("steps") or [],
                        proof=payload.get("proof", ""))
                    pl = pe.load_plan()
                    rd.write_dashboard(pl, day)
                    return self._send(200, json.dumps(
                        {"ok": True, "id": task["id"], "from": task["from"], "to": task["to"]},
                        ensure_ascii=False).encode())
                if route == "/api/custom/delete":
                    hit = pe.remove_custom_task(str(payload.get("id", "")))
                    if not hit:
                        return self._send(200, json.dumps(
                            {"ok": False, "error": "找不到这个自定义任务（可能已被删除）"},
                            ensure_ascii=False).encode())
                    pl = pe.load_plan()
                    rd.write_dashboard(pl, day)
                    return self._send(200, json.dumps(
                        {"ok": True, "title": hit["title"]}, ensure_ascii=False).encode())
                key = payload["key"]
                day_s = key.split("::")[0]
                d = pe.parse_date(day_s)
                pl = pe.load_plan()
                status = "done" if payload.get("done") else "undone"
                pe.mark(pl, d, key.split("::", 1)[1], status=status,
                        amount=payload.get("amount"))
                tasks = [t for t in pe.tasks_for_day(pl, d) if t["kind"] != "class"]
                done_count = sum(1 for t in tasks if t.get("done"))
                rd.write_dashboard(pl, d)
                body = json.dumps({"ok": True, "done_count": done_count,
                                   "total": len(tasks)}, ensure_ascii=False).encode()
                return self._send(200, body)
            except Exception as exc:  # noqa: BLE001
                return self._send(200, json.dumps(
                    {"ok": False, "error": str(exc)}, ensure_ascii=False).encode())

    port = int(args.port)
    httpd = None
    for candidate in range(port, port + 20):
        try:
            httpd = ExclusiveHTTPServer(("127.0.0.1", candidate), Handler)
            port = candidate
            break
        except OSError:
            continue
    if httpd is None:
        print("端口都被占用，换一个 --port 再试。")
        return 1
    print(f"工作台已启动：http://127.0.0.1:{port}/　（Ctrl+C 停止）")
    if port != int(args.port):
        print(f"注意：{args.port} 已被占用（很可能已有工作台在运行），本次改用 {port}。")
    print(f"静态页面也可直接双击打开：{DASH}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="app.py", description="AI 职业生涯规划学习实践工作台")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("today", help="生成今天的 todo 清单")
    p.add_argument("--date")
    p.set_defaults(func=cmd_today)

    p = sub.add_parser("week", help="未来若干天一览")
    p.add_argument("--date")
    p.add_argument("--days", type=int, default=7)
    p.set_defaults(func=cmd_week)

    for name, status in (("done", "done"), ("undone", "undone"), ("skip", "skipped")):
        p = sub.add_parser(name, help={"done": "确认完成", "undone": "撤销", "skip": "顺延"}[name])
        p.add_argument("selectors", nargs="*")
        p.add_argument("--date")
        if name == "done":
            p.add_argument("--amount", type=float, help="真实数量，如刷题数、模考得分")
        if name == "skip":
            p.add_argument("--reason", default="")
        p.set_defaults(func=lambda a, s=status: cmd_mark(a, s))

    p = sub.add_parser("note", help="给某条任务写复盘")
    p.add_argument("selector")
    p.add_argument("text")
    p.add_argument("--date")
    p.set_defaults(func=cmd_note)

    p = sub.add_parser("add", help="为某天增加临时任务（只影响那一天，不进计划）")
    p.add_argument("title")
    p.add_argument("--minutes", type=int, default=0)
    p.add_argument("--date")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("addtask", help="新增自定义任务（某一天或一个时间段，会进清单）")
    p.add_argument("title")
    p.add_argument("--from", dest="from_date", required=True, help="开始日期 YYYY-MM-DD")
    p.add_argument("--to", dest="to_date", default="", help="结束日期，留空＝只有一天")
    p.add_argument("--days", default="", help="限定星期，如 6,7；留空＝每天")
    p.add_argument("--minutes", type=int, default=30)
    p.add_argument("--steps", default="", help="步骤，用 | 分隔")
    p.add_argument("--proof", default="")
    p.set_defaults(func=cmd_addtask)

    p = sub.add_parser("tasks", help="列出自定义任务")
    p.set_defaults(func=cmd_tasks)

    p = sub.add_parser("deltask", help="删除自定义任务（按 id 前缀）")
    p.add_argument("task_id")
    p.set_defaults(func=cmd_deltask)

    p = sub.add_parser("report", help="学习实践报告")
    p.add_argument("--date")
    p.add_argument("--month", action="store_true")
    p.add_argument("--quarter", action="store_true")
    p.add_argument("--year", action="store_true")
    p.add_argument("--range", help="自定义区间，如 2026-09-30..2026-12-31")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("replan", help="加了新材料后重算未来清单")
    p.set_defaults(func=cmd_replan)

    p = sub.add_parser("export", help="导出 Markdown 打卡清单")
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--date")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("materials", help="查看材料库与待补充清单")
    p.add_argument("--guide", action="store_true")
    p.set_defaults(func=cmd_materials)

    p = sub.add_parser("serve", help="打开可视化工作台（本地服务）")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--date")
    p.set_defaults(func=cmd_report_serve)

    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return cmd_today(argparse.Namespace(date=None))
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
