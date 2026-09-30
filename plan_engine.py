# -*- coding: utf-8 -*-
"""计划引擎：把 plan.json 编译成"每天可打卡的清单"。

设计要点
--------
* plan.json 是唯一真源；任何改动后调用 replan() 就能重算未来所有清单。
* 完成状态单独存放在 state/completions.json，与计划分离，便于回滚与统计。
* 任务支持两种进度口径：
    - progress_mode="days"     统计"完成了多少天"（习惯类，如背单词）
    - progress_mode="quantity" 累加 amount 字段（计数类，如刷题、模考）
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state"
COMPLETIONS = STATE / "completions.json"
NOTES = STATE / "notes.json"
MATERIALS = STATE / "materials.json"
CACHE = STATE / "cache"

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


# --------------------------------------------------------------------------
# 基础读写
# --------------------------------------------------------------------------
def load_plan(path: Path | None = None) -> dict:
    p = Path(path) if path else ROOT / "plan.json"
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def save_plan(plan: dict, path: Path | None = None) -> None:
    p = Path(path) if path else ROOT / "plan.json"
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return default


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def load_completions() -> dict:
    return _load_json(COMPLETIONS, {"version": 1, "records": {}})


def save_completions(data: dict) -> None:
    _save_json(COMPLETIONS, data)


# --------------------------------------------------------------------------
# 日期与学期
# --------------------------------------------------------------------------
def parse_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def today(plan: dict) -> dt.date:
    return dt.date.today()


def week1_monday(plan: dict) -> dt.date:
    """本学期的第 1 教学周周一。

    优先使用 `week_anchor`（某一天 = 第几教学周），因为这是校历上直接能读到的事实；
    只有没有锚点时才回退到 `week1_monday`。改锚点即可整体平移所有周次。
    """
    sem = plan["calendar"]["semester"]
    anchor = sem.get("week_anchor")
    if anchor:
        d = parse_date(anchor["date"])
        monday = d - dt.timedelta(days=d.weekday())
        return monday - dt.timedelta(days=(int(anchor["week"]) - 1) * 7)
    return parse_date(sem["week1_monday"])


def semester_week(plan: dict, day: dt.date) -> int | None:
    """返回该日期属于第几教学周（1 起）；不在学期内返回 None。"""
    sem = plan["calendar"]["semester"]
    start = week1_monday(plan)
    total = int(sem.get("teaching_weeks", 18)) + 2
    delta = (day - start).days
    if delta < 0:
        return None
    week = delta // 7 + 1
    return week if week <= total else None


def current_phase(plan: dict, day: dt.date) -> dict | None:
    for phase in plan.get("phase_overrides", []):
        if parse_date(phase["from"]) <= day <= parse_date(phase["to"]):
            return phase
    return None


def meets_on(meeting: dict, day: dt.date, plan: dict) -> bool:
    """判断某次课程安排当天是否上课（按周次与星期几）。"""
    if meeting.get("day") != day.weekday() + 1:
        return False
    week = semester_week(plan, day)
    if week is None:
        return False
    spec = str(meeting.get("weeks", "")).strip()
    if not spec:
        return True
    for part in re.split(r"[,，]", spec):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, _, hi = part.partition("-")
            try:
                if int(lo) <= week <= int(hi):
                    return True
            except ValueError:
                continue
        else:
            try:
                if int(part) == week:
                    return True
            except ValueError:
                continue
    return False


def courses_on(plan: dict, day: dt.date) -> list[dict]:
    items = [m for m in plan.get("course_meetings", []) if meets_on(m, day, plan)]
    return sorted(items, key=lambda m: _period_start(m.get("periods", "")))


def _period_start(periods: str) -> int:
    m = re.match(r"(\d+)", str(periods))
    return int(m.group(1)) if m else 99


def fixed_events_on(plan: dict, day: dt.date) -> list[dict]:
    """当天的一次性固定事项（教授开放日、讲座、报告会等）。

    与 course_meetings 的区别：这些不按周次重复，只在指定日期出现一次，
    所以直接按 date 匹配；缺 id 的条目用日期+标题自动生成一个稳定 id。
    """
    iso = day.isoformat()
    items = []
    for ev in plan.get("fixed_events", []):
        if str(ev.get("date", "")) != iso:
            continue
        ev = dict(ev)
        if not ev.get("id"):
            ev["id"] = "event-" + hashlib.md5(
                (iso + str(ev.get("title", ""))).encode("utf-8")).hexdigest()[:8]
        items.append(ev)
    return sorted(items, key=lambda e: _period_start(e.get("periods", "")))


# --------------------------------------------------------------------------
# 自定义任务：某一天，或一个日期区间（可选限定星期）
# --------------------------------------------------------------------------
CUSTOM_TASKS = CACHE / "custom_tasks.json"


def load_custom_tasks() -> list[dict]:
    return _load_json(CUSTOM_TASKS, {"version": 1, "tasks": []}).get("tasks", [])


def save_custom_tasks(tasks: list[dict]) -> None:
    _save_json(CUSTOM_TASKS, {"version": 1, "tasks": tasks})


def custom_task_on(task: dict, day: dt.date) -> bool:
    """自定义任务是否落在这一天。"""
    iso = day.isoformat()
    lo = str(task.get("from") or "")
    hi = str(task.get("to") or lo)
    if not lo or not (lo <= iso <= hi):
        return False
    days = task.get("days") or []
    if days and (day.weekday() + 1) not in [int(x) for x in days]:
        return False
    return True


def custom_tasks_on(day: dt.date) -> list[dict]:
    return [t for t in load_custom_tasks() if custom_task_on(t, day)]


def custom_dates(days: int = 60, base: dt.date | None = None) -> dict[str, list[dict]]:
    """未来若干天里，哪些天有自定义任务（给仪表盘"接下来要盯的日期"用）。"""
    start = base or dt.date.today()
    out: dict[str, list[dict]] = {}
    for i in range(days + 1):
        d = start + dt.timedelta(days=i)
        items = custom_tasks_on(d)
        if items:
            out[d.isoformat()] = items
    return out


def add_custom_task(title: str, from_date: str, to_date: str = "", days: list[int] | None = None,
                    minutes: int = 30, steps: list[str] | None = None, proof: str = "",
                    note: str = "", unit: str = "次", at: str | None = None) -> dict:
    """新增一个自定义任务。to_date 留空表示只有一天。"""
    title = (title or "").strip()
    if not title:
        raise ValueError("任务名不能为空")
    lo = parse_date(from_date)
    hi = parse_date(to_date) if str(to_date or "").strip() else lo
    if hi < lo:
        raise ValueError("结束日期不能早于开始日期")
    stamp = at or dt.datetime.now().isoformat(timespec="seconds")
    task = {
        "id": "c" + hashlib.md5((stamp + title).encode("utf-8")).hexdigest()[:8],
        "title": title,
        "from": lo.isoformat(),
        "to": hi.isoformat(),
        "days": [int(x) for x in (days or [])],
        "minutes": int(minutes or 0),
        "steps": [s for s in (steps or []) if str(s).strip()],
        "proof": proof or "",
        "note": note or "",
        "unit": unit or "次",
        "created_at": stamp,
    }
    tasks = load_custom_tasks()
    tasks.append(task)
    save_custom_tasks(tasks)
    return task


def remove_custom_task(task_id: str) -> dict | None:
    """删除自定义任务，并清掉它产生的打卡记录（避免留下孤儿记录）。"""
    tasks = load_custom_tasks()
    hit = None
    keep = []
    for t in tasks:
        if t.get("id") == task_id or str(t.get("id", "")).startswith(task_id):
            hit = t
        else:
            keep.append(t)
    if hit is None:
        return None
    save_custom_tasks(keep)
    data = load_completions()
    recs = data.get("records", {})
    suffix = "::custom-" + hit["id"]
    for k in [k for k in recs if k.endswith(suffix)]:
        recs.pop(k, None)
    save_completions(data)
    notes = _load_json(NOTES, {})
    for k in [k for k in notes if k.endswith(suffix)]:
        notes.pop(k, None)
    _save_json(NOTES, notes)
    return hit


# --------------------------------------------------------------------------
# 任务生成
# --------------------------------------------------------------------------
def task_key(day: dt.date, template_id: str) -> str:
    return f"{day.isoformat()}::{template_id}"


def _scale_for(phase: dict | None, template_id: str) -> float:
    if not phase:
        return 1.0
    return float(phase.get("scale", {}).get(template_id, 1.0))


def tasks_for_day(plan: dict, day: dt.date) -> list[dict]:
    """编译某一天的任务清单。"""
    weekday = day.weekday() + 1
    phase = current_phase(plan, day)
    keep = set(phase.get("keep_task_ids", [])) if phase else set()
    restrict = bool(keep)
    weekend_boost = (
        float(plan.get("day_rules", {}).get("weekend_multiplier", 1.0))
        if weekday >= 6
        else 1.0
    )

    tasks: list[dict] = []

    # 1) 课程（时间固定，不参与完成度统计，只作提示）
    for m in courses_on(plan, day):
        tasks.append(
            {
                "key": task_key(day, f"class-{m['code']}-{m.get('periods','')}"),
                "template_id": None,
                "kind": "class",
                "track": "class",
                "title": f"{m['name']}（{m.get('periods','')}）",
                "minutes": 0,
                "steps": [f"地点：{m.get('place','')}　教师：{m.get('teacher','')}"],
                "proof": "",
                "done": False,
                "skippable": True,
            }
        )

    # 2) 一次性固定事项（讲座、开放日、报告会等：有确定日期的单次活动）
    for ev in fixed_events_on(plan, day):
        tasks.append(
            {
                "key": task_key(day, ev["id"]),
                "template_id": None,
                "kind": "event",
                "track": ev.get("track", "research"),
                "title": f"{ev['title']}（{ev.get('periods','')}）",
                "minutes": int(ev.get("minutes", 0)),
                "steps": ev.get("steps", []),
                "proof": ev.get("proof", ""),
                "note": ev.get("note", ""),
                "unit": ev.get("unit", "次"),
                "progress_mode": "days",
                "done": False,
                "skippable": True,
            }
        )

    # 3) 模板任务
    force_daily = set(phase.get("force_daily", [])) if phase else set()
    for tpl in plan.get("task_templates", []):
        days = tpl.get("days") or [1, 2, 3, 4, 5, 6, 7]
        forced = tpl["id"] in force_daily
        if weekday not in days and not forced:
            continue
        # phase 的 keep_task_ids 会把当天收窄成"只保留这几项"（国庆、期末复习期的做法）。
        # 但有些任务是外部有硬约束的固定事项——体育课要求的校园跑、平台布置的英语作业，
        # 它们不会因为你在放假就消失，所以标记 always 让它们不受收窄影响。
        if restrict and tpl["id"] not in keep and not tpl.get("always"):
            continue
        scale = _scale_for(phase, tpl["id"])
        if scale <= 0:
            continue
        # 有些任务时长是"生理/平台固定"的（跑步 20 分钟、慕课作业 40 分钟），
        # 不该被周末系数或阶段倍率放大——放大它并不能让人多跑或多写。
        if tpl.get("ignore_weekend_multiplier") or tpl.get("fixed_minutes"):
            minutes = int(round(tpl.get("minutes", 30) * scale))
        else:
            minutes = int(round(tpl.get("minutes", 30) * scale * weekend_boost))
        tasks.append(
            {
                "key": task_key(day, tpl["id"]),
                "template_id": tpl["id"],
                "kind": "task",
                "track": tpl.get("track", "gpa"),
                "title": tpl["title"],
                "minutes": minutes,
                "steps": tpl.get("steps", []),
                "proof": tpl.get("proof", ""),
                "note": tpl.get("note", ""),
                "unit": tpl.get("unit", "次"),
                "progress_mode": tpl.get("progress_mode")
                or ("quantity" if tpl.get("unit") in ("题", "次", "篇") else "days"),
                "done": False,
                "skippable": False,
            }
        )

    # 4) 阶段附加任务
    if phase:
        for i, extra in enumerate(phase.get("extra", [])):
            tasks.append(
                {
                    "key": task_key(day, f"phase-{phase['id']}-{i}"),
                    "template_id": None,
                    "kind": "phase",
                    "track": "phase",
                    "title": extra.get("title", "阶段任务"),
                    "minutes": int(extra.get("minutes", 30)),
                    "steps": extra.get("steps", []),
                    "proof": "",
                    "done": False,
                    "skippable": True,
                }
            )

    # 5) 自定义任务（网页端/CLI 添加：某一天，或一个日期区间 + 星期）
    for ct in custom_tasks_on(day):
        tasks.append(
            {
                "key": task_key(day, "custom-" + ct["id"]),
                "template_id": None,
                "kind": "custom",
                "track": "custom",
                "title": ct["title"],
                "minutes": int(ct.get("minutes", 0)),
                "steps": ct.get("steps", []),
                "proof": ct.get("proof", ""),
                "note": ct.get("note", ""),
                "unit": ct.get("unit", "次"),
                "progress_mode": ct.get("progress_mode", "days"),
                "done": False,
                "skippable": True,
                "custom": True,
                "custom_range": (ct.get("from"), ct.get("to")),
            }
        )

    # 6) 附加到当天的一条备注任务（由 CLI 添加）
    extras = _load_json(CACHE / "extras.json", {})
    for i, extra in enumerate(extras.get(day.isoformat(), [])):
        tasks.append(
            {
                "key": task_key(day, f"extra-{i}-{hashlib.md5(extra['title'].encode()).hexdigest()[:6]}"),
                "template_id": None,
                "kind": "extra",
                "track": "extra",
                "title": extra["title"],
                "minutes": int(extra.get("minutes", 0)),
                "steps": [],
                "proof": "",
                "done": False,
                "skippable": True,
            }
        )

    # 7) 叠加完成状态
    recs = load_completions().get("records", {})
    for t in tasks:
        r = recs.get(t["key"])
        if r and r.get("status") == "done":
            t["done"] = True
            t["done_at"] = r.get("at")
            t["amount"] = r.get("amount")
        elif r and r.get("status") == "skipped":
            t["done"] = True
            t["skipped"] = True
            t["skip_reason"] = r.get("reason", "")
        r2 = _load_json(NOTES, {}).get(t["key"])
        if r2:
            t["journal"] = r2 if isinstance(r2, str) else r2.get("text", "")
    return tasks


# --------------------------------------------------------------------------
# 打卡
# --------------------------------------------------------------------------
def mark(plan: dict, day: dt.date, selector: str, status: str = "done",
         amount: float | None = None, reason: str = "", at: str | None = None) -> list[str]:
    """把某天的任务标记为 done / undone / skipped。

    selector 可以是：任务序号(1,2,...)、模板 id、或 id 的前缀。
    """
    tasks = tasks_for_day(plan, day)
    targets = _resolve(tasks, selector)
    if not targets:
        return []
    data = load_completions()
    recs = data.setdefault("records", {})
    stamp = at or dt.datetime.now().isoformat(timespec="seconds")
    touched = []
    for t in targets:
        if status == "undone":
            recs.pop(t["key"], None)
        else:
            rec = {"status": status, "at": stamp, "day": day.isoformat(),
                   "title": t["title"], "template_id": t.get("template_id")}
            if amount is not None:
                rec["amount"] = amount
            if reason:
                rec["reason"] = reason
            recs[t["key"]] = rec
        touched.append(t["title"])
    save_completions(data)
    return touched


def _resolve(tasks: list[dict], selector: str) -> list[dict]:
    sel = str(selector).strip()
    if not sel or sel.lower() in ("all", "*"):
        return [t for t in tasks if t["kind"] != "class"]
    if sel.isdigit():
        idx = int(sel)
        # 序号只数自主任务：与 `app.py today` 打印出来的编号一致
        numbered = [t for t in tasks if t["kind"] != "class"]
        if 1 <= idx <= len(numbered):
            return [numbered[idx - 1]]
        return []
    # 完整 key（date::template）也可直接使用
    if "::" in sel:
        hit = [t for t in tasks if t["key"] == sel]
        if hit:
            return hit
    hit = [t for t in tasks if t.get("template_id") == sel]
    if hit:
        return hit
    return [t for t in tasks if t["key"].split("::")[-1].startswith(sel)]


def add_extra(day: dt.date, title: str, minutes: int = 0) -> None:
    extras = _load_json(CACHE / "extras.json", {})
    extras.setdefault(day.isoformat(), []).append({"title": title, "minutes": minutes})
    _save_json(CACHE / "extras.json", extras)


def set_journal(day: dt.date, selector: str, text: str, plan: dict) -> list[str]:
    tasks = tasks_for_day(plan, day)
    targets = _resolve(tasks, selector)
    notes = _load_json(NOTES, {})
    for t in targets:
        notes[t["key"]] = {"text": text, "at": dt.datetime.now().isoformat(timespec="seconds")}
    _save_json(NOTES, notes)
    return [t["title"] for t in targets]


# --------------------------------------------------------------------------
# 统计
# --------------------------------------------------------------------------
def template_index(plan: dict) -> dict:
    return {t["id"]: t for t in plan.get("task_templates", [])}


def progress(plan: dict, day: dt.date | None = None) -> list[dict]:
    """按轨道统计累计进度（围绕今天向前累计，含目标截止日约束）。"""
    recs = load_completions().get("records", {})
    tpls = plan.get("task_templates", [])
    out = []
    for tpl in tpls:
        tid = tpl["id"]
        target = tpl.get("target")
        mode = tpl.get("progress_mode") or ("quantity" if tpl.get("unit") in ("题", "次", "篇") else "days")
        days_done, total_amount = 0, 0.0
        for key, rec in recs.items():
            if rec.get("template_id") != tid:
                continue
            if rec.get("status") != "done":
                continue
            day_s = key.split("::")[0]
            days_done += 1
            total_amount += float(rec.get("amount") or 1)
        value = total_amount if mode == "quantity" else days_done
        out.append(
            {
                "id": tid,
                "track": tpl.get("track"),
                "title": tpl["title"],
                "mode": mode,
                "value": round(value, 1) if value % 1 else int(value),
                "target": target,
                "target_by": tpl.get("target_by"),
                "unit": tpl.get("unit", "次"),
                "ratio": (value / target) if target else None,
            }
        )
    return out


def plan_start(plan: dict) -> dt.date:
    """计划真正开始生效的日子（教学周第 1 周的周一）。"""
    return week1_monday(plan)


def window_completion(plan: dict, start: dt.date, end: dt.date) -> dict:
    """统计区间内任务的完成率。

    两条边界都会被裁剪：
      · end 裁到今天——未来的日子还没机会完成，放进分母会永久压低完成率；
      · start 裁到计划生效日——计划还没开始时并不存在这些任务。
    """
    base = today(plan)
    effective_end = min(end, base)
    start = max(start, plan_start(plan))
    if start > effective_end:
        return {"start": start.isoformat(), "end": effective_end.isoformat(),
                "planned": 0, "done": 0, "ratio": None, "per_track": {}}
    planned = done = 0
    per_track: dict[str, list[int]] = {}
    day = start
    while day <= effective_end:
        for t in tasks_for_day(plan, day):
            if t["kind"] == "class":
                continue
            track = t.get("track", "other")
            slot = per_track.setdefault(track, [0, 0])
            planned += 1
            slot[0] += 1
            if t.get("skipped"):
                planned -= 1
                slot[0] -= 1
            elif t["done"]:
                done += 1
                slot[1] += 1
        day += dt.timedelta(days=1)
    return {
        "start": start.isoformat(),
        "end": effective_end.isoformat(),
        "planned": planned,
        "done": done,
        "ratio": (done / planned) if planned else None,
        "per_track": {
            k: {"planned": v[0], "done": v[1], "ratio": (v[1] / v[0]) if v[0] else None}
            for k, v in per_track.items()
        },
    }


def streak(plan: dict, template_id: str, end: dt.date) -> int:
    recs = load_completions().get("records", {})
    n = 0
    day = end
    while True:
        key = task_key(day, template_id)
        rec = recs.get(key)
        if not rec or rec.get("status") != "done":
            # 该模板今天本就不需要做，则跳过而不算断
            tpl = template_index(plan).get(template_id, {})
            if day.weekday() + 1 not in (tpl.get("days") or []):
                day -= dt.timedelta(days=1)
                if (end - day).days > 400:
                    break
                continue
            break
        n += 1
        day -= dt.timedelta(days=1)
        if (end - day).days > 400:
            break
    return n


def minutes_planned(plan: dict, day: dt.date) -> int:
    return sum(t["minutes"] for t in tasks_for_day(plan, day) if t["kind"] != "class")


def adjustable_minutes(plan: dict, day: dt.date) -> int:
    """当天"可自主伸缩"的分钟数。

    三类不计入每日预算：
      · class —— 有固定上课时间的课程；
      · event —— 一次性固定事项（讲座/开放日），是约会，不存在"今天太满就顺延"；
      · phase —— 阶段附加任务（如期中核对、期末冲刺），本身就是"有余力才做"的加练，
                 计入预算会让临考阶段天天报超限。
    自定义任务（custom）是用户主动加进来的、明确知道要花多少时间，所以计入预算——
    这样"今天排了多久"的提示才有意义。否则会在有讲座或处于阶段窗口的日子误报超限。
    """
    return sum(
        t["minutes"] for t in tasks_for_day(plan, day)
        if t["kind"] in ("task", "extra", "custom")
    )


def clamp_day(plan: dict, day: dt.date) -> list[str]:
    """按每日上限把任务时长裁剪到合理区间，返回提示信息。"""
    rules = plan.get("day_rules", {})
    cap = int(rules.get("max_minutes_per_day", 210))
    msgs = []
    total = adjustable_minutes(plan, day)
    events = [t for t in tasks_for_day(plan, day) if t["kind"] == "event"]
    ev_minutes = sum(t["minutes"] for t in events)
    if total > cap:
        tail = ""
        if ev_minutes:
            tail = f"（另有 {len(events)} 项固定事项 {ev_minutes} 分钟，属约会，已排除在上限之外）"
        msgs.append(
            f"当天自主任务 {total} 分钟，超过建议上限 {cap} 分钟；建议只做前 3 项，其余顺延。{tail}"
        )
    if total < int(rules.get("min_minutes_per_day", 60)):
        msgs.append(rules.get("rest_low_load_message", "今天任务很轻，可以加练。"))
    return msgs


# --------------------------------------------------------------------------
# replan：材料 -> 计划
# --------------------------------------------------------------------------
def material_fingerprint(plan: dict) -> dict:
    out = {}
    mdir = ROOT / plan.get("materials", {}).get("dir", "materials")
    if not mdir.exists():
        return out
    for p in sorted(mdir.glob("**/*")):
        if p.is_file() and not p.name.startswith("_") and p.name != ".gitkeep":
            h = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
            out[str(p.relative_to(ROOT)).replace("\\", "/")] = {
                "sha256_16": h,
                "size": p.stat().st_size,
                "mtime": dt.datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
            }
    return out


def replan(plan: dict | None = None, quiet: bool = False) -> dict:
    """重算：刷新材料指纹、清理旧缓存、重建未来清单缓存。

    计划真源是 plan.json；本函数保证：
      1. state/materials.json 与 materials/ 目录同步（新增材料会被登记）；
      2. 完成记录中引用了已删除模板或已过期日期的条目被隔离（不删除，仅标记）；
      3. 重新生成未来 120 天的清单快照（state/cache/days/*.json）。
    """
    plan = plan or load_plan()
    report = {"materials": {}, "orphans": [], "rebuilt": 0}

    old = _load_json(MATERIALS, {}).get("files", {})
    new = material_fingerprint(plan)
    added = [k for k in new if k not in old]
    changed = [k for k in new if k in old and old[k].get("sha256_16") != new[k]["sha256_16"]]
    removed = [k for k in old if k not in new]
    report["materials"] = {"added": added, "changed": changed, "removed": removed}
    _save_json(MATERIALS, {"version": 1, "files": new, "updated": dt.datetime.now().isoformat(timespec="seconds")})

    # 重建未来 120 天快照
    days_dir = CACHE / "days"
    if days_dir.exists():
        shutil.rmtree(days_dir)
    days_dir.mkdir(parents=True, exist_ok=True)
    base = today(plan)
    for i in range(0, 120):
        d = base + dt.timedelta(days=i)
        snap = {"date": d.isoformat(), "weekday": WEEKDAY_CN[d.weekday()],
                "week": semester_week(plan, d), "tasks": tasks_for_day(plan, d)}
        _save_json(days_dir / f"{d.isoformat()}.json", snap)
        report["rebuilt"] += 1

    # 隔离孤儿记录
    valid_ids = {t["id"] for t in plan.get("task_templates", [])}
    data = load_completions()
    for key, rec in data.get("records", {}).items():
        tid = rec.get("template_id")
        if tid and tid not in valid_ids:
            report["orphans"].append(key)

    if not quiet:
        for k in added:
            print(f"+ 新材料登记：{k}")
        for k in changed:
            print(f"~ 材料已更新：{k}（计划可能需要修订，请检查 plan.json）")
        for k in removed:
            print(f"- 材料已移除：{k}")
        print(f"已重建未来 {report['rebuilt']} 天的清单快照。")
        if report["orphans"]:
            print(f"注意：有 {len(report['orphans'])} 条打卡记录指向已删除的任务模板（已保留历史，不影响统计）。")
    return report


# --------------------------------------------------------------------------
# 便捷：默认今天
# --------------------------------------------------------------------------
def today_tasks(plan: dict | None = None) -> tuple[dt.date, list[dict]]:
    plan = plan or load_plan()
    d = today(plan)
    return d, tasks_for_day(plan, d)
