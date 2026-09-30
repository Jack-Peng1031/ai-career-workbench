# -*- coding: utf-8 -*-
"""生成工作台可视化页面（单文件、零依赖、内联 SVG 图表）。

注意：模板大量使用 CSS/JS 花括号，因此这里刻意不用 f-string，
统一用字符串拼接，避免与 Python 表达式语法冲突。
"""
from __future__ import annotations

import datetime as dt
import html
import json
from pathlib import Path

import plan_engine as pe

CSS = """
:root{
  --bg:#f5f6f8; --panel:#ffffff; --ink:#14161a; --muted:#6b7280; --line:#e3e6ea;
  --gpa:#2f6feb; --code:#12a150; --english:#d29922; --research:#8250df;
  --class:#5b6472; --phase:#e5484d; --extra:#0d9488; --custom:#e36209;
  --ok:#12a150; --shadow:0 1px 2px rgba(16,24,40,.06),0 4px 16px rgba(16,24,40,.05);
}
@media (prefers-color-scheme:dark){
  :root{ --bg:#0f1115; --panel:#171a1f; --ink:#e8eaed; --muted:#9aa2ad; --line:#272b32;
         --shadow:0 1px 2px rgba(0,0,0,.4),0 4px 18px rgba(0,0,0,.35); }
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:"Inter","Segoe UI",system-ui,-apple-system,"Microsoft YaHei","PingFang SC","Noto Sans SC",sans-serif;
  font-size:14.5px;line-height:1.6;-webkit-font-smoothing:antialiased}
a{color:var(--gpa);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1180px;margin:0 auto;padding:22px 18px 60px}
header.hero{background:linear-gradient(135deg,#1f3a8a,#2f6feb 55%,#12a150);
  color:#fff;border-radius:16px;padding:24px 26px;box-shadow:var(--shadow);position:relative;overflow:hidden}
header.hero:after{content:"";position:absolute;right:-60px;top:-60px;width:240px;height:240px;
  background:radial-gradient(circle,rgba(255,255,255,.22),transparent 70%)}
.hero h1{margin:0 0 4px;font-size:22px;letter-spacing:.3px}
.hero .sub{opacity:.92;font-size:13.5px}
.hero-row{display:flex;flex-wrap:wrap;gap:18px;align-items:center;justify-content:space-between;margin-top:16px}
.pills{display:flex;flex-wrap:wrap;gap:8px;max-width:640px}
.pill{background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.28);
  padding:4px 11px;border-radius:999px;font-size:12.5px}
.ring{--p:0;width:96px;height:96px;flex:0 0 auto}
.ring circle{fill:none;stroke-width:9;stroke-linecap:round}
.ring .bg{stroke:rgba(255,255,255,.25)}
.ring .fg{stroke:#fff;stroke-dasharray:264;stroke-dashoffset:calc(264 - 264*var(--p)/100);
  transition:stroke-dashoffset .5s ease;transform:rotate(-90deg);transform-origin:50% 50%}
.ring text{fill:#fff;font-size:19px;font-weight:700;text-anchor:middle}
.ring .lab{font-size:10px;font-weight:500;opacity:.85}
.grid{display:grid;gap:16px;margin-top:16px}
@media(min-width:980px){ .cols{grid-template-columns:1fr 340px} }
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px 20px;box-shadow:var(--shadow)}
.card h2{margin:0 0 4px;font-size:15.5px;letter-spacing:.2px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.card h2 .tag{font-size:11px;font-weight:600;color:var(--muted);background:var(--bg);
  border:1px solid var(--line);border-radius:6px;padding:1px 7px}
.card .hint{color:var(--muted);font-size:12.5px;margin:0 0 14px}
.kv{display:flex;justify-content:space-between;gap:10px;font-size:13px;padding:5px 0;border-bottom:1px dashed var(--line)}
.kv:last-child{border-bottom:0}
.kv b{font-weight:600}
ul.tasks{list-style:none;margin:0;padding:0}
li.task{display:flex;gap:12px;padding:12px 0;border-top:1px solid var(--line)}
li.task:first-child{border-top:0}
.bar{flex:0 0 4px;border-radius:3px;background:var(--gpa)}
.track-gpa .bar{background:var(--gpa)} .track-code .bar{background:var(--code)}
.track-english .bar{background:var(--english)} .track-research .bar{background:var(--research)}
.track-class .bar{background:var(--class)} .track-phase .bar{background:var(--phase)}
.track-extra .bar{background:var(--extra)}
.track-custom .bar{background:var(--custom)}
.ctform{display:grid;gap:8px;margin:4px 0 2px}
.ctform label{font-size:12px;color:var(--muted);display:block;margin-bottom:3px}
.ctform input[type=text],.ctform input[type=date],.ctform input[type=number],.ctform textarea{
  width:100%;box-sizing:border-box;padding:6px 8px;border:1px solid var(--line);border-radius:7px;
  background:var(--panel);color:var(--ink);font:inherit;font-size:12.5px}
.ctform textarea{resize:vertical;min-height:38px}
.ctform .row{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.ctform .row3{display:grid;grid-template-columns:1fr 1fr 92px;gap:8px}
.ctform .wd{display:flex;flex-wrap:wrap;gap:10px;font-size:12px;color:var(--ink)}
.ctform .wd label{display:inline-flex;align-items:center;gap:3px;color:var(--ink);margin:0}
.btn{border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:7px;
  padding:6px 12px;font:inherit;font-size:12.5px;cursor:pointer}
.btn.primary{background:var(--gpa);border-color:var(--gpa);color:#fff;font-weight:600}
.btn:hover{filter:brightness(1.04)}
.btn.mini{padding:2px 8px;font-size:11.5px}
.warn{margin-top:8px;padding:7px 9px;border-radius:7px;background:#fff4e5;border:1px solid #f0c48a;
  color:#7a4700;font-size:12px}
.warn[hidden]{display:none}
.ctlist{list-style:none;margin:8px 0 0;padding:0}
.ctlist li{display:flex;gap:8px;align-items:flex-start;padding:7px 0;border-top:1px solid var(--line);font-size:12.5px}
.ctlist .t{flex:1;min-width:0}
.ctlist .m{color:var(--muted);font-size:11.5px}
.ct-empty{color:var(--muted);font-size:12.5px;margin-top:6px}
ul.tl{list-style:none;margin:4px 0 0;padding:0}
ul.tl li.tl-hidden{display:none}
ul.tl.tl-expanded li.tl-hidden{display:block}
ul.tl li.tl-date{border-top:1px solid var(--line)}
ul.tl > li.tl-date:first-child{border-top:0}
ul.tl summary.tl-head{display:grid;grid-template-columns:10px 46px 34px 1fr auto;gap:8px;
  align-items:center;padding:9px 2px;cursor:pointer;list-style:none;font-size:13px}
ul.tl summary.tl-head::-webkit-details-marker{display:none}
ul.tl summary.tl-head::marker{content:""}
ul.tl .dot{width:8px;height:8px;border-radius:99px;background:var(--muted);opacity:.55}
ul.tl details[open] > summary.tl-head .dot{background:var(--gpa);opacity:1}
ul.tl .tld{font-variant-numeric:tabular-nums;font-weight:700}
ul.tl .tlw{color:var(--muted)}
/* 相对天数与条数放在此行右端，不挤占标题宽度 */
ul.tl .tlmeta{text-align:right;color:var(--muted);font-size:11.5px;white-space:nowrap}
ul.tl .tlmeta b{color:var(--ink);font-weight:600}
ul.tl .tltoday{color:var(--gpa);font-weight:700}
/* 展开后的任务：标题占满整行、需要时换行，不再被省略号截断 */
ul.tl ul.tl-items{list-style:none;margin:0 0 8px;padding:0}
ul.tl ul.tl-items li{display:flex;gap:8px;align-items:flex-start;padding:5px 2px 5px 18px;font-size:12.6px}
ul.tl ul.tl-items li .ti{flex:1;min-width:0;overflow-wrap:anywhere;line-height:1.55}
ul.tl ul.tl-items li .tag{flex:0 0 auto;margin-top:1px}
ul.tl ul.tl-items li.hit .ti{font-weight:600;color:var(--gpa)}
ul.tl ul.tl-items .ti .sub{display:block;color:var(--muted);font-weight:400;font-size:12.1px;margin-top:2px}
.tl-more{color:var(--muted);font-size:12.5px;cursor:pointer;padding:6px 0;user-select:none}
.tl-more:hover{color:var(--gpa)}
.tmain{flex:1;min-width:0}
.ttop{display:flex;align-items:flex-start;gap:9px}
.ttitle{font-weight:600;font-size:14px}
.min{color:var(--muted);font-size:12px;margin-left:auto;white-space:nowrap;padding-top:2px}
ol.steps{margin:6px 0 0;padding-left:20px;color:var(--muted);font-size:12.8px}
ol.steps li{margin:2px 0}
.proof{margin-top:7px;font-size:12.4px;color:#0b7a3c;background:rgba(18,161,80,.09);
  border-left:3px solid var(--code);padding:5px 9px;border-radius:0 6px 6px 0}
.note{font-size:12.2px;color:var(--muted);margin-top:5px;font-style:italic}
.check{appearance:none;width:19px;height:19px;margin-top:2px;border:2px solid var(--line);
  border-radius:6px;cursor:pointer;flex:0 0 auto;position:relative;background:transparent}
.check:checked{background:var(--ok);border-color:var(--ok)}
.check:checked:after{content:"";position:absolute;left:5px;top:1px;width:5px;height:10px;
  border:solid #fff;border-width:0 2px 2px 0;transform:rotate(43deg)}
li.done .ttitle{text-decoration:line-through;color:var(--muted)}
li.done .proof,li.done ol.steps{opacity:.5}
.prog{margin:13px 0}
.prog .lab{display:flex;justify-content:space-between;font-size:12.8px;margin-bottom:5px;gap:8px}
.prog .lab .l{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.prog .lab .v{color:var(--muted);white-space:nowrap;font-variant-numeric:tabular-nums}
.track{height:7px;background:var(--bg);border-radius:99px;overflow:hidden;border:1px solid var(--line)}
.track i{display:block;height:100%;border-radius:99px}
.bg-gpa{background:var(--gpa)} .bg-code{background:var(--code)}
.bg-english{background:var(--english)} .bg-research{background:var(--research)}
.dates{list-style:none;margin:0;padding:0}
.dates li{display:flex;gap:10px;padding:8px 0;border-bottom:1px dashed var(--line);font-size:13px}
.dates li:last-child{border-bottom:0}
.dates .d{color:var(--muted);font-variant-numeric:tabular-nums;white-space:nowrap;flex:0 0 76px;font-size:12.5px}
.dates .k{font-size:10.5px;padding:1px 6px;border-radius:5px;background:var(--bg);border:1px solid var(--line);
  color:var(--muted);flex:0 0 auto;margin-top:3px;height:18px}
.week{display:grid;grid-template-columns:repeat(7,1fr);gap:7px}
.day{border:1px solid var(--line);border-radius:10px;padding:9px 6px;text-align:center;background:var(--panel)}
.day.today{border-color:var(--gpa);box-shadow:0 0 0 2px rgba(47,111,235,.18)}
.day .dn{font-size:11px;color:var(--muted)}
.day .dd{font-weight:700;font-size:15px;font-variant-numeric:tabular-nums}
.day .dc{font-size:10.5px;color:var(--muted);margin-top:4px;min-height:14px}
.day .pbar{height:5px;background:var(--bg);border-radius:99px;margin-top:7px;overflow:hidden}
.day .pbar i{display:block;height:100%;background:var(--ok)}
table.simple{width:100%;border-collapse:collapse;font-size:12.5px}
table.simple th,table.simple td{text-align:left;padding:6px 7px;border-bottom:1px solid var(--line)}
table.simple th{color:var(--muted);font-weight:600;font-size:11.5px}
table.simple td.n{font-variant-numeric:tabular-nums;text-align:right}
footer{margin-top:26px;color:var(--muted);font-size:12px;text-align:center;line-height:1.9}
.cmd{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:1px 6px;
  font-family:ui-monospace,Consolas,"Cascadia Mono",monospace;font-size:12px}
"""

JS = """
const OFFICIAL = location.protocol.indexOf('http') === 0;
async function toggle(box){
  const key = box.dataset.key;
  const done = box.checked;
  const li = box.closest('li');
  li.classList.toggle('done', done);
  if(!OFFICIAL){ return; }
  try{
    const r = await fetch('/api/toggle', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({key:key, done:done})});
    const j = await r.json();
    if(!j.ok){ throw new Error(j.error || '保存失败'); }
    const el = document.getElementById('kpi-done');
    if(el && j.done_count !== undefined){ el.textContent = j.done_count; }
  }catch(e){
    box.checked = !done;
    li.classList.toggle('done', !done);
    alert('未保存：' + e.message + '\\n请先运行 python app.py serve，再从 http://127.0.0.1:8765/ 打开本页面。');
  }
}
document.querySelectorAll('input.check').forEach(function(b){
  if(b.closest('li').classList.contains('track-class')){ b.style.display = 'none'; }
  b.addEventListener('change', function(){ toggle(b); });
});

// —— 自定义任务：网页端添加 / 删除 ——
function showOffline(msg){
  const w = document.getElementById('ct-warn');
  if(w){ w.textContent = msg; w.hidden = false; }
}
async function addCustom(ev){
  ev.preventDefault();
  const f = ev.target;
  const val = function(id){ const el = document.getElementById(id); return el ? el.value.trim() : ''; };
  const days = Array.prototype.slice.call(f.querySelectorAll('input.wdbox:checked'))
                 .map(function(x){ return parseInt(x.value, 10); });
  const payload = {
    title: val('ct-title'),
    from: val('ct-from'),
    to: val('ct-to') || val('ct-from'),
    minutes: parseInt(val('ct-min') || '30', 10),
    steps: val('ct-steps') ? val('ct-steps').split('\\n').filter(function(s){ return s.trim(); }) : [],
    proof: val('ct-proof'),
    days: days
  };
  if(!payload.title){ showOffline('请先填写任务名。'); return false; }
  if(!OFFICIAL){ showOffline('直接双击打开的页面不能添加任务：请先运行 python app.py serve，再用 http://127.0.0.1:8765/ 打开。'); return false; }
  try{
    const r = await fetch('/api/custom', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)});
    const j = await r.json();
    if(!j.ok){ throw new Error(j.error || '添加失败'); }
    location.reload();
  }catch(e){
    showOffline('添加失败：' + e.message);
  }
  return false;
}
async function removeCustom(id){
  if(!OFFICIAL){ showOffline('直接双击打开的页面不能删除任务：请从本地服务打开。'); return; }
  if(!confirm('删除这个自定义任务？已勾选的记录也会一并清除。')){ return; }
  try{
    const r = await fetch('/api/custom/delete', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id:id})});
    const j = await r.json();
    if(!j.ok){ throw new Error(j.error || '删除失败'); }
    location.reload();
  }catch(e){
    showOffline('删除失败：' + e.message);
  }
}
// —— 时间线：按日期折叠 / 展开 ——
// 折叠的单位是"日期"：收起时只看到 日期·星期·还有几天·N 项
const TL_FOLD = 12;
function toggleAllTimeline(){
  const list = document.getElementById('tl-list');
  if(!list){ return; }
  const items = Array.prototype.slice.call(list.querySelectorAll('details.tl-date'));
  const anyClosed = items.some(function(d){ return !d.open; });
  items.forEach(function(d){ d.open = anyClosed; });
  list.querySelectorAll('li.tl-hidden').forEach(function(li){ li.classList.remove('tl-hidden'); });
  const more = document.getElementById('tl-more-hint');
  if(more){ more.style.display = 'none'; }
  list.classList.add('tl-expanded');
}

(function(){
  const f = document.getElementById('ct-form');
  if(f){ f.addEventListener('submit', addCustom); }
  const from = document.getElementById('ct-from');
  const to = document.getElementById('ct-to');
  if(from && to){
    from.value = from.value || document.body.dataset.today || '';
    to.addEventListener('change', function(){ if(to.value){ from.value = to.value; } });
  }
})();
"""


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def ring(percent: float, label: str = "今日完成") -> str:
    p = max(0.0, min(100.0, percent or 0.0))
    return (
        '<svg class="ring" viewBox="0 0 96 96" style="--p:' + f"{p:.1f}" + '">'
        '<circle class="bg" cx="48" cy="48" r="42"/>'
        '<circle class="fg" cx="48" cy="48" r="42"/>'
        '<text x="48" y="50">' + str(round(p)) + '%</text>'
        '<text class="lab" x="48" y="64">' + esc(label) + '</text></svg>'
    )


def bar(label: str, value, target, unit: str, track: str, by: str = "") -> str:
    if target:
        ratio = min(1.0, float(value or 0) / float(target))
        right = f"{value:g}/{target:g} {esc(unit)}" + (f" · {esc(by)}前" if by else "")
    else:
        ratio, right = 0.0, f"{value:g} {esc(unit)}"
    return (
        '<div class="prog"><div class="lab"><span class="l">' + esc(label) +
        '</span><span class="v">' + right + '</span></div>'
        '<div class="track"><i class="bg-' + esc(track) + '" style="width:' +
        f"{ratio * 100:.1f}" + '%"></i></div></div>'
    )


def render_task(t: dict, index: int) -> str:
    cls = ["task", "track-" + str(t.get("track", "gpa"))]
    if t.get("done"):
        cls.append("done")
    steps = "".join("<li>" + esc(s) + "</li>" for s in t.get("steps", []))
    proof = ('<div class="proof">完成标准：' + esc(t["proof"]) + '</div>') if t.get("proof") else ""
    note = ('<div class="note">提示：' + esc(t["note"]) + '</div>') if t.get("note") else ""
    skip = '<span class="min" style="color:#0b7a3c">已顺延</span>' if t.get("skipped") else ""
    mins = ('<span class="min">' + str(t["minutes"]) + ' 分钟</span>') if t.get("minutes") \
        else '<span class="min">课程</span>'
    journal = ('<div class="note">复盘：' + esc(t["journal"]) + '</div>') if t.get("journal") else ""
    checked = " checked" if t.get("done") else ""
    key = esc(t["key"])
    return (
        '<li class="' + " ".join(cls) + '" data-key="' + key + '">'
        '<span class="bar"></span>'
        '<input class="check" type="checkbox" data-key="' + key + '"' + checked + ' title="勾选即确认完成">'
        '<div class="tmain"><div class="ttop"><span class="ttitle">' + str(index) + ". " +
        esc(t["title"]) + '</span>' + skip + mins + '</div>'
        + ('<ol class="steps">' + steps + '</ol>' if steps else "")
        + proof + note + journal + '</div></li>'
    )


def render_day_card(day: dt.date, week, tasks: list) -> str:
    real = [t for t in tasks if t["kind"] != "class"]
    done = sum(1 for t in real if t.get("done"))
    pct = (done / len(real) * 100) if real else 0
    total = sum(t["minutes"] for t in real)
    courses = [t for t in tasks if t["kind"] == "class"]
    weektxt = ("第 " + str(week) + " 教学周") if week else "假期 / 非教学周"
    body = "".join(render_task(t, i + 1) for i, t in enumerate(tasks))
    if not body:
        body = '<li class="task"><div class="tmain">今天没有安排任务，休息也是计划的一部分。</div></li>'
    return (
        '<section class="card" id="today"><h2>今日清单 <span class="tag">' + esc(day.isoformat()) + " " +
        esc(pe.WEEKDAY_CN[day.weekday()]) + " · " + esc(weektxt) + '</span></h2>'
        '<p class="hint">' + str(len(courses)) + ' 门课 · 自主任务 <b id="kpi-done">' + str(done) + '</b>/' +
        str(len(real)) + ' 项 · 计划投入 ' + str(total) + ' 分钟。勾选后会立即存档到 '
        '<span class="cmd">state/completions.json</span>。</p>'
        '<ul class="tasks">' + body + '</ul></section>'
    )


def render_timeline(plan: dict, base: dt.date, max_days: int = 16, fold_after: int = 12) -> tuple[str, int]:
    """「接下来要盯的日期」：按【日期】折叠的时间线。

    折的是"每一天"这一层，不是每条说明：
      · 收起时只看到 `日期 · 星期 · 还有几天 · N 项`，一屏能放下十几天；
      · 点日期行才展开那天要做的事，任务标题占满整行、该换行就换行；
      · 今天与明天默认展开；超过 fold_after 天的默认不显示，可一键放出。
    返回 (HTML, 未折叠时的天数)。
    """
    WDC = pe.WEEKDAY_CN
    until = base + dt.timedelta(days=400)
    rows: list[tuple[str, int, int, str, str, str]] = []

    def add(date_s: str, seq: int, tag: str, title: str, detail: str) -> None:
        d = pe.parse_date(date_s)
        if d < base or d > until:
            return
        rows.append((date_s, 0 if tag != "自定义" else 1, seq, tag, title, detail))

    for n, k in enumerate(plan.get("key_dates", [])):
        add(k["date"], n, str(k.get("kind", "") or "日期"), k["title"], k.get("action", ""))
    for iso, items in sorted(pe.custom_dates(400, base).items()):
        for n, t in enumerate(items):
            rng = t["from"] if t.get("to", t["from"]) == t["from"] else t["from"] + " ~ " + t["to"]
            add(iso, n, "自定义", t["title"], "区间 " + rng + "　" + str(t.get("minutes", 0)) + " 分钟")

    # 同一件事（同一天 + 同标题）可能同时来自 key_dates 与 fixed_events，去重
    seen = set()
    groups: dict[str, list[tuple[str, str, str]]] = {}
    for date_s, _, _, tag, title, detail in sorted(rows, key=lambda z: (z[0], z[1], z[2])):
        if (date_s, title) in seen:
            continue
        seen.add((date_s, title))
        groups.setdefault(date_s, []).append((tag, title, detail))

    dates = sorted(groups)
    if not dates:
        return '<li class="tl-empty">暂无需要盯的日期。</li>', 0

    out = []
    for n, date_s in enumerate(dates[:max_days]):
        d = pe.parse_date(date_s)
        delta = (d - base).days
        when = "今天" if delta == 0 else ("明天" if delta == 1 else str(delta) + " 天后")
        # 今天与明天默认展开
        opening = " open" if delta <= 1 else ""
        hidden = ' class="tl-hidden"' if n >= fold_after else ''
        cls = ' class="tltoday"' if delta == 0 else ''
        items = groups[date_s]
        lis = []
        for tag, title, detail in items:
            # 标题里的方向/说明拆成副行，避免和标题挤在一行被截断
            sub = ''
            if detail:
                sub = '<span class="sub">' + esc(detail) + '</span>'
            lis.append(
                '<li><span class="tag">' + esc(tag) + '</span>'
                '<span class="ti">' + esc(title) + sub + '</span></li>'
            )
        out.append(
            '<li' + hidden + '><details class="tl-date" data-idx="' + str(n) + '"' + opening + '>'
            '<summary class="tl-head">'
            '<span class="dot"></span>'
            '<span class="tld">' + esc(date_s[5:]) + '</span>'
            '<span class="tlw">' + esc(WDC[d.weekday()]) + '</span>'
            '<span class="tlmeta"><span' + cls + '>'
            + esc(when) + '</span>　<b>' + str(len(items)) + '</b> 项</span>'
            '</summary>'
            '<ul class="tl-items">' + "".join(lis) + '</ul>'
            '</details></li>'
        )
    return "".join(out), len(dates)



def render_custom_card(base: dt.date) -> str:
    """自定义任务面板：添加（某一天 / 一个时间段 + 星期）与删除。"""
    WDC = pe.WEEKDAY_CN
    wd_boxes = "".join(
        '<label><input type="checkbox" class="wdbox" value="' + str(i + 1) + '">' + WDC[i] + '</label>'
        for i in range(7)
    )
    items = pe.load_custom_tasks()
    if items:
        rows = []
        for t in sorted(items, key=lambda z: (z.get("from", ""), z.get("title", ""))):
            rng = t["from"] if t.get("to", t["from"]) == t["from"] else t["from"] + " ~ " + t["to"]
            days = t.get("days") or []
            wd = "、".join(WDC[int(d) - 1] for d in days) if days else ""
            meta = rng + ("　限 " + wd if wd else "") + "　" + str(t.get("minutes", 0)) + " 分钟"
            rows.append(
                '<li><span class="t"><b>' + esc(t["title"]) + '</b><br>'
                '<span class="m">' + esc(meta) + '</span></span>'
                '<button class="btn mini" onclick="removeCustom(\'' + esc(t["id"]) + '\')">删除</button></li>'
            )
        body = '<ul class="ctlist">' + "".join(rows) + '</ul>'
    else:
        body = '<div class="ct-empty">还没有自定义任务。</div>'
    return (
        '<section class="card" id="custom"><h2>自定义任务'
        '<span class="tag">某一天 / 一个时间段</span></h2>'
        '<p class="hint">添加后会出现在对应日期的<b>今日清单</b>里（可勾选），'
        '并进入右侧<b>接下来要盯的日期</b>时间线。留空结束日期＝只有一天；'
        '勾选星期＝该时间段内只在这些天出现（例如只勾周六周日）。</p>'
        '<form class="ctform" id="ct-form">'
        '<div><label>任务名（必填）</label>'
        '<input type="text" id="ct-title" placeholder="例如：交英语慕课作业 / 校园跑 20 分钟"></div>'
        '<div class="row3"><div><label>开始日期</label>'
        '<input type="date" id="ct-from" value="' + esc(base.isoformat()) + '"></div>'
        '<div><label>结束日期（可留空）</label><input type="date" id="ct-to"></div>'
        '<div><label>分钟</label><input type="number" id="ct-min" value="30" min="0" step="5"></div></div>'
        '<div><label>限定星期（不选＝每天）</label><div class="wd">' + wd_boxes + '</div></div>'
        '<div><label>步骤（每行一条，可选）</label><textarea id="ct-steps"></textarea></div>'
        '<div><label>完成标准（可选）</label>'
        '<input type="text" id="ct-proof" placeholder="例如：学习通无待交标记"></div>'
        '<div><button class="btn primary" type="submit">添加任务</button></div>'
        '</form>'
        '<div class="warn" id="ct-warn" hidden></div>'
        + body + '</section>'
    )


def render_week_strip(plan: dict, base: dt.date) -> str:
    monday = base - dt.timedelta(days=base.weekday())
    cells = []
    for i in range(7):
        d = monday + dt.timedelta(days=i)
        tasks = pe.tasks_for_day(plan, d)
        real = [t for t in tasks if t["kind"] != "class"]
        done = sum(1 for t in real if t.get("done"))
        pct = (done / len(real) * 100) if real else 0
        courses = len([t for t in tasks if t["kind"] == "class"])
        cls = "day today" if d == base else "day"
        cells.append(
            '<div class="' + cls + '"><div class="dn">' + esc(pe.WEEKDAY_CN[d.weekday()]) + '</div>'
            '<div class="dd">' + str(d.day) + '</div>'
            '<div class="dc">' + str(courses) + ' 课 · ' + str(len(real)) + ' 任务</div>'
            '<div class="pbar"><i style="width:' + f"{pct:.0f}" + '%"></i></div></div>'
        )
    return '<div class="week">' + "".join(cells) + '</div>'


def render_day_markdown(plan: dict, day: dt.date) -> str:
    """当天的纯文本打卡表（可打印、可粘贴到笔记软件）。"""
    tasks = pe.tasks_for_day(plan, day)
    week = pe.semester_week(plan, day)
    real = [t for t in tasks if t["kind"] != "class"]
    done = sum(1 for t in real if t.get("done"))
    out = [
        "# " + day.isoformat() + "（" + pe.WEEKDAY_CN[day.weekday()] + "）"
        + ((" 第 " + str(week) + " 教学周") if week else ""),
        "",
        "完成 " + str(done) + "/" + str(len(real)) + "　计划投入 "
        + str(sum(t["minutes"] for t in real)) + " 分钟",
        "",
    ]
    courses = [t for t in tasks if t["kind"] == "class"]
    if courses:
        out.append("## 今天的课")
        for c in courses:
            out.append("- " + c["title"] + "　" + (c["steps"][0] if c["steps"] else ""))
        out.append("")
    out.append("## 今日 todo")
    for t in real:
        box = "x" if t.get("done") else " "
        out.append("- [" + box + "] **" + t["title"] + "**（" + str(t["minutes"]) + " 分钟）")
        for s in t.get("steps", []):
            out.append("    - " + s)
        if t.get("proof"):
            out.append("    - 完成标准：" + t["proof"])
    out += ["", "## 复盘（三行）",
            "- 今天做对了什么：", "- 今天失控在哪：", "- 明天只改一件事：", ""]
    return "\n".join(out)


def write_dashboard(plan: dict, base: dt.date | None = None, path: Path | None = None) -> Path:
    base = base or pe.today(plan)
    target = Path(path) if path else (pe.ROOT / "dashboard.html")
    target.write_text(render_dashboard(plan, base), encoding="utf-8")
    snaps = pe.ROOT / "exports" / "daily"
    snaps.mkdir(parents=True, exist_ok=True)
    (snaps / ("todo-" + base.isoformat() + ".md")).write_text(
        render_day_markdown(plan, base), encoding="utf-8")
    return target


def render_dashboard(plan: dict, base: dt.date | None = None) -> str:
    base = base or pe.today(plan)
    week = pe.semester_week(plan, base)
    tasks = pe.tasks_for_day(plan, base)
    real = [t for t in tasks if t["kind"] != "class"]
    done = sum(1 for t in real if t.get("done"))
    pct = (done / len(real) * 100) if real else 0.0
    student = plan.get("student", {})

    tracks = {t["id"]: t for t in plan.get("tracks", [])}
    prog_rows = []
    for p in pe.progress(plan, base):
        if not p.get("target"):
            continue
        prog_rows.append(bar(p["title"], p["value"], p["target"], p["unit"],
                             p.get("track", "gpa"), p.get("target_by", "")))

    def win(days: int) -> dict:
        return pe.window_completion(plan, base - dt.timedelta(days=days - 1), base)

    w30, w90, w365 = win(30), win(90), win(365)

    kd_html, kd_note = render_timeline(plan, base)

    ms = []
    for m in plan.get("milestones", []):
        due = pe.parse_date(m["due"])
        checks = "".join("<li>" + esc(c) + "</li>" for c in m.get("checks", []))
        ms.append(
            '<div style="margin-bottom:14px"><div style="font-weight:600;font-size:13.5px">'
            + esc(m["title"]) + ' <span class="tag" style="font-weight:500">截止 ' + esc(m["due"])
            + "（" + str((due - base).days) + ' 天后）</span></div>'
            '<ol class="steps">' + checks + '</ol></div>'
        )

    phase = pe.current_phase(plan, base)
    phase_html = ""
    if phase:
        phase_html = (
            '<div class="kv"><span>当前阶段</span><b>' + esc(phase.get("title", ""))
            + "（" + esc(phase["from"][5:]) + " — " + esc(phase["to"][5:]) + '）</b></div>'
            '<p class="hint" style="margin-top:8px">'
            + esc(phase.get("note") or phase.get("intro") or "") + '</p>'
        )

    rows = []
    for m in plan.get("course_meetings", []):
        rows.append(
            "<tr><td>" + esc(pe.WEEKDAY_CN[m["day"] - 1]) + "</td><td>" + esc(m.get("periods", ""))
            + "</td><td>" + esc(m["name"]) + "</td><td>" + esc(m.get("teacher", ""))
            + "</td><td>" + esc(m.get("weeks", "")) + " 周</td><td>" + esc(m.get("place", ""))
            + "</td></tr>"
        )
    credits = sum(m.get("credits", 0) for m in plan.get("course_meetings", []))

    manifest = pe._load_json(pe.MATERIALS, {})
    files = manifest.get("files", {})
    mat_rows = "".join(
        '<div class="kv"><span>' + esc(k) + '</span><b>' + str(v["size"]) + ' B</b></div>'
        for k, v in sorted(files.items())
    )
    watched = "".join(
        '<div class="kv"><span>' + esc(w["path"]) + '<br><span style="color:var(--muted);font-size:12px">'
        + esc(w.get("extracted", "")) + '</span></span><b>' + esc(w.get("status", "")) + '</b></div>'
        for w in plan.get("materials", {}).get("watched", [])
    )
    pending = "".join("<li>" + esc(x) + "</li>" for x in plan.get("materials", {}).get("pending_intake", []))

    bootstrap = {"date": base.isoformat(),
                 "tasks": [{"key": t["key"], "done": bool(t.get("done"))} for t in tasks]}

    head = (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>AI 职业生涯规划学习实践工作台 · ' + esc(base.isoformat()) + '</title>'
        '<link rel="icon" href="data:image/svg+xml,'
        "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' "
        "font-size='90'%3E%F0%9F%8E%AF%3C/text%3E%3C/svg%3E\">"
        '<style>' + CSS + '</style></head><body data-today="' + esc(base.isoformat()) + '"><div class="wrap">'
    )

    hero = (
        '<header class="hero"><h1>AI 职业生涯规划 · 学习实践工作台</h1>'
        '<div class="sub">' + esc(student.get("university", "")) + " · " + esc(student.get("major", ""))
        + " · " + esc(student.get("cohort", "")) + "　｜　目标：" + esc(student.get("goal", "")) + '</div>'
        '<div class="hero-row"><div class="pills">'
        '<span class="pill">今天 ' + esc(base.isoformat()) + " " + esc(pe.WEEKDAY_CN[base.weekday()]) + '</span>'
        '<span class="pill">' + (("第 " + str(week) + " 教学周") if week else "非教学周") + '</span>'
        '<span class="pill">本学期 ' + str(len(plan.get("course_meetings", []))) + " 门课 · "
        + str(credits) + ' 学分</span>'
        '<span class="pill">今日自主任务 ' + str(done) + "/" + str(len(real)) + ' 项</span>'
        '<span class="pill">计划投入 ' + str(pe.adjustable_minutes(plan, base)) + ' 分钟</span>'
        '</div>' + ring(pct, "今日完成") + '</div></header>'
    )

    left = (
        '<div class="grid" style="margin:0">'
        + render_day_card(base, week, tasks)
        + '<section class="card"><h2>本周全景 <span class="tag">'
        + esc((base - dt.timedelta(days=base.weekday())).isoformat()) + ' 起</span></h2>'
        '<p class="hint">柱条是该日自主任务的完成比例；改完计划后运行 '
        '<span class="cmd">python app.py replan</span> 重算。</p>'
        + render_week_strip(plan, base) + '</section>'
        '<section class="card"><h2>阶段里程碑</h2>'
        '<p class="hint">一个月 / 90 天 / 一年三道关，逐条打勾；不达标就当场调计划。</p>'
        + "".join(ms) + '</section></div>'
    )

    def ratio_txt(w):
        return str(w["done"]) + "/" + str(w["planned"]) + "　" + str(round((w["ratio"] or 0) * 100)) + "%"

    right = (
        '<div class="grid" style="margin:0">'
        '<section class="card"><h2>区间完成率</h2><p class="hint">只统计自主任务（课程不计入）。</p>'
        '<div class="kv"><span>近 30 天</span><b>' + ratio_txt(w30) + '</b></div>'
        '<div class="kv"><span>近 90 天</span><b>' + ratio_txt(w90) + '</b></div>'
        '<div class="kv"><span>近一年</span><b>' + ratio_txt(w365) + '</b></div>'
        + phase_html + '</section>'
        '<section class="card"><h2>累计进度</h2>'
        '<p class="hint">刷题量、模考次数等按你填写的真实数量累加（'
        '<span class="cmd">app.py done leetcode --amount 3</span>）。</p>'
        + ("".join(prog_rows) or '<p class="hint">暂无带目标的任务。</p>') + '</section>'
        '<section class="card"><h2>接下来要盯的日期'
        '<span class="tag">点日期展开 · 共 ' + str(kd_note) + ' 天</span></h2>'
        '<div class="tl-more" id="tl-toggle" onclick="toggleAllTimeline()">展开/收起全部日期</div>'
        '<ul class="tl" id="tl-list">'
        + kd_html + '</ul></section>'
        + render_custom_card(base)
        + '<section class="card"><h2>本学期课表</h2><table class="simple">'
        '<tr><th>星期</th><th>节次</th><th>课程</th><th>教师</th><th>周次</th><th>地点</th></tr>'
        + "".join(rows) + '</table></section>'
        '<section class="card"><h2>材料库与待补充</h2>'
        '<p class="hint">把新文件丢进 <span class="cmd">materials/</span>，再运行 '
        '<span class="cmd">python app.py replan</span>：材料会被登记并提示需修订的计划项。</p>'
        + watched
        + '<div style="margin-top:12px;font-weight:600;font-size:13px">待补充材料（补上就能细化计划）</div>'
        '<ol class="steps">' + pending + '</ol>'
        '<div style="margin-top:12px;font-weight:600;font-size:13px">已登记文件指纹</div>'
        + (mat_rows or '<div class="kv"><span>尚无</span><b>—</b></div>')
        + '</section></div>'
    )

    foot = (
        '</div><footer>计划真源 <span class="cmd">plan.json</span>　·　打卡记录 '
        '<span class="cmd">state/completions.json</span>　·　可视化 <span class="cmd">dashboard.html</span><br>'
        '常用命令：<span class="cmd">python app.py today</span>　<span class="cmd">python app.py done 1</span>　'
        '<span class="cmd">python app.py report --quarter</span>　'
        '<span class="cmd">python app.py serve --port 8765</span><br>'
        '所有赛事时间、保研细则以四川大学教务处与学院当年正式通知为准。</footer>'
        '<script id="bootstrap" type="application/json">' + json.dumps(bootstrap, ensure_ascii=False)
        + '</script><script>' + JS + '</script></body></html>'
    )

    return head + hero + '<div class="grid cols">' + left + right + foot
