# -*- coding: utf-8 -*-
"""生成工作台可视化页面（单文件、零依赖、内联 SVG 图表）。

注意：模板大量使用 CSS/JS 花括号，因此这里刻意不用 f-string，
统一用字符串拼接，避免与 Python 表达式语法冲突。
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
from pathlib import Path

import plan_engine as pe

CSS = """
:root{
  /* —— 表面层级：page < sunken < panel < raised —— */
  --bg:#eef1f6; --sunken:#eaeef4; --panel:#ffffff; --panel-2:#f6f8fb; --raised:#ffffff;
  --line:#dbe1ea; --line-2:#e9edf3; --ink:#101828; --muted:#5c6779; --faint:#8b95a6;
  /* —— 主色 / 品牌 —— */
  --primary:#2f5fd0; --primary-deep:#24499f; --primary-soft:#eaf0fe;
  /* —— 语义色：绿=完成 蓝=进行中 琥珀=提醒 红=冲突/逾期 —— */
  --ok:#0d8a4f; --ok-soft:#e7f7ee; --info:#2f5fd0; --info-soft:#eaf0fe;
  --warn:#a86400; --warn-soft:#fff6e5; --danger:#c8383d; --danger-soft:#fdecec;
  /* —— 各轨道的专属色（左侧色条 / 进度条 / 标签）—— */
  --gpa:#2f5fd0; --code:#0d8a4f; --english:#a86400; --research:#6d3bd1;
  --class:#5a6b86; --phase:#c8383d; --extra:#0b7f78; --custom:#cf5000;
  --shadow:0 1px 2px rgba(16,24,40,.06),0 6px 18px -8px rgba(16,24,40,.16);
  --shadow-hi:0 2px 4px rgba(16,24,40,.06),0 16px 34px -16px rgba(16,24,40,.24);
  --hero-pattern:radial-gradient(circle at 92% 8%,rgba(255,255,255,.22),transparent 42%),radial-gradient(circle at 6% 96%,rgba(120,240,208,.24),transparent 46%);
}
@media (prefers-color-scheme:dark){
  :root{
    --bg:#0c0f14; --sunken:#12161d; --panel:#161b23; --panel-2:#1b212b; --raised:#1d242f;
    --line:#28303c; --line-2:#212836; --ink:#e9edf3; --muted:#9aa5b6; --faint:#78849a;
    --primary:#6f9bfa; --primary-deep:#3f6fd8; --primary-soft:#18233a;
    --ok:#3ec27f; --ok-soft:#12271c; --info:#6f9bfa; --info-soft:#18233a;
    --warn:#e0a53c; --warn-soft:#2b2110; --danger:#f0757a; --danger-soft:#2d1719;
    --gpa:#6f9bfa; --code:#3ec27f; --english:#e0a53c; --research:#b28bff;
    --class:#8fa0bb; --phase:#f0757a; --extra:#3ec8bd; --custom:#ff9d5c;
    --shadow:0 1px 2px rgba(0,0,0,.5),0 8px 22px -10px rgba(0,0,0,.55);
    --shadow-hi:0 2px 4px rgba(0,0,0,.5),0 18px 36px -18px rgba(0,0,0,.6);
    --hero-pattern:radial-gradient(circle at 92% 8%,rgba(255,255,255,.14),transparent 42%),radial-gradient(circle at 6% 96%,rgba(62,200,189,.18),transparent 46%);
  }
}
*{box-sizing:border-box}
body{margin:0;color:var(--ink);
  background:radial-gradient(1200px 520px at 12% -8%,var(--primary-soft),transparent 62%),
             radial-gradient(1000px 460px at 96% 4%,rgba(11,127,120,.07),transparent 58%),
             linear-gradient(180deg,var(--bg),var(--sunken));
  background-attachment:fixed;
  font-family:"Inter","Segoe UI",system-ui,-apple-system,"Microsoft YaHei","PingFang SC","Noto Sans SC",sans-serif;
  font-size:14.5px;line-height:1.6;-webkit-font-smoothing:antialiased}
a{color:var(--primary);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1180px;margin:0 auto;padding:22px 18px 60px}
header.hero{background:linear-gradient(135deg,#123a86 0%,#2456b4 42%,#0f8f7d 100%);
  color:#fff;border-radius:18px;padding:26px 28px;box-shadow:var(--shadow-hi);position:relative;overflow:hidden;
  border:1px solid rgba(255,255,255,.14)}
header.hero:before{content:"";position:absolute;inset:0;background:var(--hero-pattern);pointer-events:none}
header.hero:after{content:"";position:absolute;right:-80px;top:-80px;width:280px;height:280px;
  background:radial-gradient(circle,rgba(255,255,255,.20),transparent 70%)}
header.hero > *{position:relative;z-index:1}
.hero h1{margin:0 0 4px;font-size:22px;letter-spacing:.3px;text-shadow:0 1px 2px rgba(0,0,0,.18)}
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
.grid{display:grid;gap:18px;margin-top:18px}
/* align-items:start：两栏各自按内容高度收尾，否则左栏会被右栏的长列表拉高、
   卡片里留出一大片空白（用户反馈过的"左侧大量空白"） */
@media(min-width:980px){ .cols{grid-template-columns:1fr 340px;align-items:start} }
.card{background:var(--panel);border:1px solid var(--line);border-radius:15px;padding:18px 20px;
  box-shadow:var(--shadow);position:relative;overflow:hidden}
/* 卡片之间用顶部一条渐隐色带拉出层次：第一张用主色，其余用中性 -->
.card:before{content:"";position:absolute;left:0;right:0;top:0;height:3px;
  background:linear-gradient(90deg,var(--line),transparent 76%);opacity:1}
.card:first-child:before{background:linear-gradient(90deg,var(--primary),var(--extra) 58%,transparent)}
/* 卡片标题做成"有厚度的头"：浅色底 + 下边线，标题层级一眼可辨 */
.card > h2{margin:-18px -20px 14px;padding:12px 20px 11px;font-size:15.5px;letter-spacing:.2px;
  display:flex;align-items:center;gap:8px;flex-wrap:wrap;
  background:linear-gradient(180deg,var(--panel-2),var(--panel));border-bottom:1px solid var(--line-2)}
.card > h2:before{content:"";width:4px;height:15px;border-radius:2px;background:var(--primary);flex:0 0 auto}
.card h2 .tag{font-size:11px;font-weight:600;color:var(--muted);background:var(--panel);
  border:1px solid var(--line);border-radius:7px;padding:2px 8px}
.card > h2 .tag{margin-left:auto}
.card .hint{color:var(--muted);font-size:12.5px;margin:0 0 14px}
/* 深色模式 / 打印：不要让色带喧宾夺主 */
@media (prefers-color-scheme:dark){
  .card{background:linear-gradient(180deg,var(--panel),var(--panel-2))}
}
.kv{display:flex;justify-content:space-between;gap:10px;font-size:13px;padding:5px 0;border-bottom:1px dashed var(--line)}
.kv:last-child{border-bottom:0}
.kv b{font-weight:600}
ul.tasks{list-style:none;margin:0;padding:0}
li.task{display:flex;gap:12px;padding:12px 12px 12px 4px;border-top:1px solid var(--line-2);border-radius:9px}
li.task:hover{background:var(--panel-2)}
li.task:first-child{border-top:0}
.bar{flex:0 0 4px;border-radius:3px;background:var(--gpa);min-height:22px;align-self:stretch}
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
.btn{border:1px solid var(--line);background:var(--raised);color:var(--ink);border-radius:8px;
  padding:6px 12px;font:inherit;font-size:12.5px;cursor:pointer;transition:background .15s,border-color .15s,color .15s}
.btn.primary{background:linear-gradient(180deg,var(--primary),var(--primary-deep));border-color:var(--primary-deep);
  color:#fff;font-weight:600;box-shadow:0 1px 2px rgba(16,24,40,.18)}
.btn:hover{filter:none;background:var(--primary-soft);border-color:var(--primary);color:var(--primary)}
.btn.primary:hover{background:linear-gradient(180deg,var(--primary-deep),var(--primary-deep));color:#fff}
.btn.mini{padding:2px 8px;font-size:11.5px}
.warn{margin-top:8px;padding:8px 10px;border-radius:8px;background:var(--warn-soft);border:1px solid var(--warn);
  color:var(--warn);font-size:12px;font-weight:600}
.warn[hidden]{display:none}
.ctlist{list-style:none;margin:8px 0 0;padding:0}
.ctlist li{display:flex;gap:8px;align-items:flex-start;padding:7px 0;border-top:1px solid var(--line-2);font-size:12.5px}
.ctlist .t{flex:1;min-width:0}
.ctlist .m{color:var(--muted);font-size:11.5px}
.ct-empty{color:var(--muted);font-size:12.5px;margin-top:6px}
ul.tl{list-style:none;margin:4px 0 0;padding:0}
ul.tl li.tl-hidden{display:none}
ul.tl.tl-expanded li.tl-hidden{display:block}
ul.tl li.tl-date{border-top:1px solid var(--line-2)}
ul.tl > li.tl-date:first-child{border-top:0}
ul.tl summary.tl-head{display:grid;grid-template-columns:10px 46px 34px 1fr auto;gap:8px;
  align-items:center;padding:9px 2px;cursor:pointer;list-style:none;font-size:13px;border-radius:7px}
ul.tl summary.tl-head:hover{background:var(--panel-2)}
ul.tl summary.tl-head::-webkit-details-marker{display:none}
ul.tl summary.tl-head::marker{content:""}
ul.tl .dot{width:8px;height:8px;border-radius:99px;background:var(--faint);opacity:.55}
ul.tl details[open] > summary.tl-head .dot{background:var(--primary);opacity:1}
ul.tl .tld{font-variant-numeric:tabular-nums;font-weight:700}
ul.tl .tlw{color:var(--muted)}
/* 相对天数与条数放在此行右端，不挤占标题宽度 */
ul.tl .tlmeta{text-align:right;color:var(--muted);font-size:11.5px;white-space:nowrap}
ul.tl .tlmeta b{color:var(--ink);font-weight:600}
ul.tl .tltoday{color:var(--primary);font-weight:700}
/* 展开后的任务：标题占满整行、需要时换行，不再被省略号截断 */
ul.tl ul.tl-items{list-style:none;margin:0 0 8px;padding:0}
ul.tl ul.tl-items li{display:flex;gap:8px;align-items:flex-start;padding:5px 2px 5px 18px;font-size:12.6px}
ul.tl ul.tl-items li .ti{flex:1;min-width:0;overflow-wrap:anywhere;line-height:1.55}
ul.tl ul.tl-items li .tag{flex:0 0 auto;margin-top:1px}
ul.tl ul.tl-items li.hit .ti{font-weight:600;color:var(--primary)}
ul.tl ul.tl-items .ti .sub{display:block;color:var(--muted);font-weight:400;font-size:12.1px;margin-top:2px}
.tl-more{color:var(--primary);font-size:12.5px;cursor:pointer;padding:6px 0;user-select:none;font-weight:600}
.tl-more:hover{text-decoration:underline}

/* —— 轨道标签：每类任务一个颜色，扫一眼就知道是哪条线 —— */
.tag.tg{background:var(--panel-2);border:1px solid var(--line);color:var(--muted);
  border-radius:6px;padding:1px 7px;font-size:10.8px;font-weight:600;white-space:nowrap}
.tg-gpa{color:var(--gpa);background:color-mix(in srgb,var(--gpa) 12%,transparent);border-color:color-mix(in srgb,var(--gpa) 34%,transparent)}
.tg-code{color:var(--code);background:color-mix(in srgb,var(--code) 12%,transparent);border-color:color-mix(in srgb,var(--code) 34%,transparent)}
.tg-english{color:var(--english);background:color-mix(in srgb,var(--english) 14%,transparent);border-color:color-mix(in srgb,var(--english) 36%,transparent)}
.tg-research{color:var(--research);background:color-mix(in srgb,var(--research) 12%,transparent);border-color:color-mix(in srgb,var(--research) 34%,transparent)}
.tg-class{color:var(--class);background:color-mix(in srgb,var(--class) 12%,transparent);border-color:color-mix(in srgb,var(--class) 32%,transparent)}
.tg-phase{color:var(--phase);background:color-mix(in srgb,var(--phase) 12%,transparent);border-color:color-mix(in srgb,var(--phase) 34%,transparent)}
.tg-extra{color:var(--extra);background:color-mix(in srgb,var(--extra) 12%,transparent);border-color:color-mix(in srgb,var(--extra) 34%,transparent)}
.tg-custom{color:var(--custom);background:color-mix(in srgb,var(--custom) 12%,transparent);border-color:color-mix(in srgb,var(--custom) 36%,transparent)}
.tg-event{color:var(--research);background:color-mix(in srgb,var(--research) 12%,transparent);border-color:color-mix(in srgb,var(--research) 34%,transparent)}
/* —— 状态胶囊：✓完成 / 今天 / N 天后 / 冲突 —— */
.stat{font-size:10.8px;font-weight:600;border-radius:6px;padding:1px 7px;white-space:nowrap;
  border:1px solid transparent;flex:0 0 auto;align-self:flex-start;margin-top:2px}
.stat-ok{color:var(--ok);background:var(--ok-soft);border-color:color-mix(in srgb,var(--ok) 30%,transparent)}
.stat-today{color:#fff;background:var(--primary);border-color:var(--primary-deep)}
.stat-soon{color:var(--warn);background:var(--warn-soft);border-color:color-mix(in srgb,var(--warn) 32%,transparent)}
.stat-info{color:var(--primary);background:var(--info-soft);border-color:color-mix(in srgb,var(--primary) 28%,transparent)}
.stat-alert{color:var(--danger);background:var(--danger-soft);border-color:color-mix(in srgb,var(--danger) 34%,transparent)}

/* —— 本周全景：一周条带 + 逐日清单 —— */
.wk{display:grid;grid-template-columns:repeat(7,1fr);gap:8px}
.wk-cell{display:block;position:relative;border:1px solid var(--line);border-radius:11px;padding:9px 7px 10px;
  text-align:center;background:var(--panel);cursor:pointer;text-decoration:none;color:inherit;
  transition:border-color .15s,box-shadow .15s,transform .15s,background .15s}
.wk-cell:hover{border-color:var(--primary);background:var(--primary-soft);transform:translateY(-1px);
  box-shadow:var(--shadow);text-decoration:none}
.wk-cell.today{border-color:var(--primary);background:linear-gradient(180deg,var(--primary-soft),var(--panel));
  box-shadow:0 0 0 2px color-mix(in srgb,var(--primary) 22%,transparent)}
.wk-wd{font-size:11px;color:var(--muted);font-weight:600}
.wk-cell.today .wk-wd{color:var(--primary)}
.wk-dd{font-weight:700;font-size:15.5px;font-variant-numeric:tabular-nums;line-height:1.25}
.wk-when{font-size:10px;color:var(--faint)}
.wk-cnt{font-size:10.5px;color:var(--muted);margin-top:4px;min-height:14px}
.wk-bar{height:5px;background:var(--sunken);border-radius:99px;margin-top:7px;overflow:hidden}
.wk-bar i{display:block;height:100%;background:var(--ok);border-radius:99px}
.wk-panel{margin-top:10px}
/* 每 7 天一个分隔，视觉上把"这一周"与后面的内容分开 */
.wk-panel > hr.wk-gap{border:0;border-top:2px dashed var(--line);margin:16px 0 12px}
.wk-panel > hr.wk-gap:first-child{display:none}
.wk-tools{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;
  font-size:12.5px;color:var(--muted);margin:6px 0 9px}
.wk-tools .tl-more{padding:0}
.wk-days{display:grid;gap:8px}
.wk-day{display:flex;gap:10px;border:1px solid var(--line);border-radius:11px;
  background:var(--panel-2);padding:9px 12px;scroll-margin-top:14px;transition:border-color .2s,box-shadow .2s}
.wk-day.hit{border-color:var(--primary);box-shadow:0 0 0 2px color-mix(in srgb,var(--primary) 20%,transparent)}
.wk-day.is-today{background:linear-gradient(180deg,var(--primary-soft),var(--panel-2));
  border-color:color-mix(in srgb,var(--primary) 42%,transparent)}
.wk-mark{flex:0 0 4px;border-radius:3px;background:var(--line);align-self:stretch}
.wk-day.is-today .wk-mark{background:var(--primary)}
.wk-main{flex:1;min-width:0}
.wk-hd{display:flex;align-items:center;gap:7px;flex-wrap:wrap;cursor:pointer;list-style:none}
.wk-hd::-webkit-details-marker{display:none}
.wk-hd::marker{content:""}
.wk-hd:hover .wk-title{color:var(--primary)}
.wk-title{font-size:13.2px;font-weight:700;font-variant-numeric:tabular-nums}
.wk-sum{color:var(--muted);font-size:11.8px}
.wk-prog{margin-left:auto;color:var(--muted);font-size:11.5px;white-space:nowrap;font-variant-numeric:tabular-nums}
.wk-chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:5px;font-size:11px;color:var(--muted)}
.chip{border:1px solid var(--line);border-radius:6px;padding:1px 7px;background:var(--panel)}
.chip.ev{border-color:color-mix(in srgb,var(--extra) 34%,transparent);color:var(--extra);
  background:color-mix(in srgb,var(--extra) 10%,transparent);font-weight:600}
.chip.key{border-color:color-mix(in srgb,var(--warn) 34%,transparent);color:var(--warn);
  background:var(--warn-soft);font-weight:600}
.wk-rest{color:var(--muted);font-size:12.2px;padding:4px 0 2px}
.wk-items{list-style:none;margin:9px 0 2px;padding:0}
.wk-items > li{display:flex;gap:9px;align-items:flex-start;padding:8px 2px;border-top:1px solid var(--line-2)}
.wk-items > li:first-child{border-top:0}
.wk-items > li .bar{align-self:stretch;min-height:18px}
.wk-items .wk-body{flex:1;min-width:0}
.wk-items .wk-tt{font-size:12.9px;font-weight:600;overflow-wrap:anywhere;line-height:1.5}
.wk-items li.done .wk-tt{text-decoration:line-through;color:var(--muted);font-weight:500}
.wk-items li.done .wk-steps{opacity:.55}
.wk-items .wk-meta{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-top:4px}
.wk-items .wk-min{color:var(--muted);font-size:11.4px;overflow-wrap:anywhere}
.wk-items .wk-steps{margin:5px 0 0;padding-left:18px;color:var(--muted);font-size:11.9px}
.wk-items .wk-steps li{margin:1px 0}
.wk-items .wk-steps li.wk-morestep{list-style:none;margin-left:-14px;color:var(--faint);font-style:italic}
.wk-items .wk-sid{font-size:10.6px;color:var(--faint);background:var(--panel);border:1px solid var(--line);
  border-radius:5px;padding:0 5px;white-space:nowrap;align-self:flex-start;margin-top:3px}
.wk-items .check{width:17px;height:17px;border-radius:5px;margin-top:3px}
.wk-empty{border:1px dashed var(--line);border-radius:11px;padding:14px;text-align:center;
  color:var(--muted);font-size:12.5px;background:var(--panel-2)}
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
.track{height:7px;background:var(--sunken);border-radius:99px;overflow:hidden;border:1px solid var(--line-2)}
.track i{display:block;height:100%;border-radius:99px}
.bg-gpa{background:var(--gpa)} .bg-code{background:var(--code)}
.bg-english{background:var(--english)} .bg-research{background:var(--research)}
.dates{list-style:none;margin:0;padding:0}
.dates li{display:flex;gap:10px;padding:8px 0;border-bottom:1px dashed var(--line-2);font-size:13px}
.dates li:last-child{border-bottom:0}
.dates .d{color:var(--muted);font-variant-numeric:tabular-nums;white-space:nowrap;flex:0 0 76px;font-size:12.5px}
.dates .k{font-size:10.5px;padding:1px 6px;border-radius:5px;background:var(--panel-2);border:1px solid var(--line);
  color:var(--muted);flex:0 0 auto;margin-top:3px;height:18px}
table.simple{width:100%;border-collapse:collapse;font-size:12.5px}
table.simple th,table.simple td{text-align:left;padding:6px 7px;border-bottom:1px solid var(--line-2)}
table.simple th{color:var(--muted);font-weight:600;font-size:11.5px;background:var(--panel-2);
  border-bottom:1px solid var(--line)}
table.simple tbody tr:nth-child(even),table.simple tr:nth-child(even) td{background:color-mix(in srgb,var(--panel-2) 55%,transparent)}
table.simple td.n{font-variant-numeric:tabular-nums;text-align:right}
footer{margin-top:26px;color:var(--muted);font-size:12px;text-align:center;line-height:1.9}
.cmd{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:1px 6px;
  font-family:ui-monospace,Consolas,"Cascadia Mono",monospace;font-size:12px;color:var(--primary-deep)}
@media (prefers-color-scheme:dark){ .cmd{color:var(--primary)} }
"""

JS = """
const OFFICIAL = location.protocol.indexOf('http') === 0;
function barMsg(s){ return String(s).split('|').join(String.fromCharCode(10)); }
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
    alert(barMsg('未保存：' + e.message + '|请先运行 python app.py serve，再从 http://127.0.0.1:8765/ 打开本页面。'));
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
// —— 本周全景：逐日展开 / 收起（点击某一天的数字也能跳转） ——
function setWeekText(){
  const box = document.getElementById('wk-days');
  const lab = document.getElementById('wk-toggle');
  if(!box || !lab){ return; }
  const ds = box.querySelectorAll('details.wk-day');
  let open = 0;
  ds.forEach(function(d){ if(d.open){ open += 1; } });
  lab.textContent = (ds.length && open === ds.length) ? '收起全部日期' : '展开全部日期';
}
function toggleWeekDays(mode){
  const box = document.getElementById('wk-days');
  if(!box){ return; }
  const ds = Array.prototype.slice.call(box.querySelectorAll('details.wk-day'));
  let to = (mode === 'all');
  if(mode !== 'all' && mode !== 'none'){
    to = ds.some(function(d){ return !d.open; });
  }
  ds.forEach(function(d){ d.open = to; });
  setWeekText();
}
function weekJump(iso){
  if(!iso){ return; }
  const el = document.querySelector('#wk-day-' + iso);
  if(!el){ return; }
  el.open = true;
  setWeekText();
  const card = document.getElementById('week');
  if(card){ card.scrollIntoView({behavior:'smooth', block:'start'}); }
  el.classList.add('hit');
  setTimeout(function(){ el.classList.remove('hit'); }, 1800);
}
(function(){
  const card = document.getElementById('week');
  if(!card){ return; }
  setWeekText();
  card.addEventListener('click', function(ev){
    const cell = ev.target.closest('[data-jump]');
    if(cell){ ev.preventDefault(); weekJump(cell.getAttribute('data-jump')); return; }
    if(ev.target.closest('#wk-toggle')){ toggleWeekDays(); }
  });
})();

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


def track_class(track) -> str:
    """轨道 → 标签类名。未知轨道退回中性样式，不至于没有颜色。"""
    t = str(track or "").strip().lower()
    known = {"gpa", "code", "english", "research", "class", "phase", "extra", "custom", "event"}
    return ("tg tg-" + t) if t in known else "tg"


def _when_label(delta: int) -> str:
    if delta < 0:
        return "已过 " + str(-delta) + " 天"
    if delta == 0:
        return "今天"
    if delta == 1:
        return "明天"
    if delta == 2:
        return "后天"
    return str(delta) + " 天后"


def _stat_class(delta: int) -> str:
    if delta < 0:
        return "stat stat-info"
    if delta == 0:
        return "stat stat-today"
    if delta <= 3:
        return "stat stat-soon"
    return "stat stat-info"


def _base_title(s) -> str:
    """去掉行尾的（8-9节）/（与科技哲学史冲突）这类括号后缀，用于"同一件事"的粗匹配。"""
    return re.sub(r"（[^（）]*）\s*$", "", str(s or "").strip()).strip()


def _event_item(iso: str, ev: dict) -> dict:
    """一次性固定事项（讲座/开放日）→ 与 tasks_for_day 里同形状的任务项。"""
    return {
        "key": pe.task_key(pe.parse_date(iso), ev["id"]),
        "template_id": None,
        "kind": "event",
        "track": ev.get("track", "research"),
        "title": f"{ev['title']}（{ev.get('periods','')}）",
        "minutes": int(ev.get("minutes", 0)),
        "steps": ev.get("steps", []),
        "proof": ev.get("proof", ""),
        "note": ev.get("note", ""),
        "unit": ev.get("unit", "次"),
        "done": False,
    }


def _keydate_item(iso: str, k: dict) -> dict:
    return {
        "key": "keydate::" + iso + "::" + str(k.get("title", "")),
        "kind": "keydate",
        "track": "phase",
        "title": k.get("title", ""),
        "minutes": 0,
        "steps": [k["action"]] if k.get("action") else [],
        "proof": "",
        "note": str(k.get("kind", "") or ""),
        "done": False,
    }


def _day_items(plan: dict, base: dt.date, days: int, with_classes: bool,
               kinds: tuple = ("class", "event", "task", "phase", "custom", "extra")) -> dict:
    """按日期收集"要盯的事"。

    与「今日清单」同源，保证页面上两处说法一致：
      课程 + 一次性固定事项（讲座/开放日）= pe.tasks_for_day 的前两类；
      关键日期（考试、报名窗口等）单独补进来，并按基础标题去重，
      避免"教授开放日 · 蒲亦非"既在固定事项里出现、又被 key_dates 再算一次。

    kinds 用来收窄范围：右栏时间线跨 400 天，只需要 class/event，
    这时绕开 task_templates 的逐日编译（20 个模板 × 400 天，白烧 CPU）。
    """
    out: dict[str, dict] = {}
    WDC = pe.WEEKDAY_CN
    plan_keydates = plan.get("key_dates", [])

    for i in range(days):
        d = base + dt.timedelta(days=i)
        iso = d.isoformat()
        seen, items = set(), []

        if kinds == ("event",):
            # 最快路径：固定事项只按日期匹配，完全不用编译模板
            for ev in pe.fixed_events_on(plan, d):
                item = _event_item(iso, ev)
                seen.add(_base_title(item["title"]))
                items.append(item)
        else:
            for t in pe.tasks_for_day(plan, d):
                if t["kind"] not in kinds:
                    continue
                seen.add(_base_title(t["title"]))
                items.append(t)

        for k in plan_keydates:
            if str(k.get("date", "")) != iso:
                continue
            if _base_title(k.get("title", "")) in seen:
                continue
            seen.add(_base_title(k.get("title", "")))
            items.append(_keydate_item(iso, k))

        out[iso] = {"date": d, "week": pe.semester_week(plan, d), "weekday": WDC[d.weekday()],
                    "items": items}
    return out


def render_mini_task(t: dict, max_steps: int = 3) -> str:
    """「本周全景」里的一条任务：与今日清单同样的信息，但更紧凑。

    max_steps：每一步单独一行会让页面迅速变胖（14 天 × 每天近 10 项），
    超出部分压成一行「另有 N 步」，细节仍可在今日清单里看到。
    """
    cls = ["task", "track-" + str(t.get("track", "gpa"))]
    if t.get("done"):
        cls.append("done")
    kind = str(t.get("kind", "task"))
    kind_txt = {"class": "课程", "event": "活动", "custom": "自定义", "keydate": "关键日期",
                "phase": "阶段", "extra": "临时"}.get(kind, "任务")
    all_steps = [s for s in t.get("steps", []) if str(s).strip()]
    steps_html = ""
    if all_steps:
        shown = all_steps[:max_steps]
        more = ""
        if len(all_steps) > len(shown):
            more = '<li class="wk-morestep">另有 ' + str(len(all_steps) - len(shown)) + ' 步（见今日清单）</li>'
        steps_html = ('<ol class="wk-steps">'
                      + "".join("<li>" + esc(s) + "</li>" for s in shown) + more + '</ol>')
    done = '<span class="stat stat-ok">已完成</span>' if t.get("done") else ""
    if t.get("minutes"):
        meta = '<span class="wk-min">' + str(t["minutes"]) + " 分钟</span>"
    elif kind == "class":
        meta = '<span class="wk-min">课程</span>'
    else:
        meta = ""
    tag = '<span class="' + track_class(t.get("track")) + '">' + esc(kind_txt) + "</span>"
    if kind == "keydate":
        tag = '<span class="' + track_class("event") + '">' + esc(t.get("note") or kind_txt) + "</span>"
    box = ""
    if kind not in ("class", "keydate"):
        checked = " checked" if t.get("done") else ""
        box = ('<input class="check" type="checkbox" data-key="' + esc(t["key"]) + '"' + checked
               + ' title="勾选即确认完成">')
    sid = {"class": "课", "event": "活", "custom": "自", "keydate": "日"}.get(kind, "任")
    return (
        '<li class="' + " ".join(cls) + '" data-key="' + esc(t["key"]) + '">'
        + '<span class="bar"></span>' + box
        + '<div class="wk-body"><div class="wk-tt">' + esc(t.get("title", "")) + '</div>'
        + '<div class="wk-meta">' + tag + meta + done + '</div>' + steps_html + '</div>'
        + '<span class="wk-sid" title="' + esc(kind_txt) + '">' + esc(sid) + '</span></li>'
    )


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


def render_timeline(plan: dict, base: dt.date, max_days: int = 16, fold_after: int = 12,
                    span_days: int = 401) -> tuple[str, int]:
    """「接下来要盯的日期」：按【日期】折叠的时间线。

    折的是"每一天"这一层，不是每条说明：
      · 收起时只看到 `日期 · 星期 · 还有几天 · N 项`，一屏能放下十几天；
      · 点日期行才展开那天要做的事，任务标题占满整行、该换行就换行；
      · 今天与明天默认展开；超过 fold_after 天的默认不显示，可一键放出。
    返回 (HTML, 未折叠时的天数)。
    """
    WDC = pe.WEEKDAY_CN
    until = base + dt.timedelta(days=400)
    # bucket：0=固定事项（与今日清单同源，信息最全）1=自定义 2=关键日期
    rows: list[tuple[str, int, int, str, str, str, str]] = []

    def add(date_s, bucket, seq, tag, title, detail, track):
        d = pe.parse_date(date_s)
        if d < base or d > until:
            return
        rows.append((date_s, bucket, seq, tag, title, detail, track))

    # 与今日清单同源的一次性事项（讲座/开放日）；span_days 覆盖到明年，与 until 对齐
    events = _day_items(plan, base, span_days, with_classes=False, kinds=("event",))
    # 关键日期里的讲座（教授开放日）与 fixed_events 是同一件事，按基础标题去重，
    # 避免同一天同一个活动在时间线里出现两次。
    fixed_seen = {iso: {_base_title(t["title"]) for t in rec["items"]}
                  for iso, rec in events.items()}
    for n, k in enumerate(plan.get("key_dates", [])):
        date_s = str(k.get("date", ""))
        if _base_title(k.get("title", "")) in fixed_seen.get(date_s, set()):
            continue
        add(date_s, 2, n, str(k.get("kind", "") or "日期"), k["title"], k.get("action", ""), "phase")
    for iso, items in sorted(pe.custom_dates(400, base).items()):
        for n, t in enumerate(items):
            rng = t["from"] if t.get("to", t["from"]) == t["from"] else t["from"] + " ~ " + t["to"]
            add(iso, 1, n, "自定义", t["title"],
                "自定义任务　" + rng + "　" + str(t.get("minutes", 0)) + " 分钟", "custom")
    for iso, rec in events.items():
        for n, t in enumerate(rec["items"]):
            detail = (t.get("steps") or [""])[0]
            if t.get("minutes"):
                detail = (str(t["minutes"]) + " 分钟　" + detail).strip("　")
            add(iso, 0, n, "固定事项", t["title"], detail, str(t.get("track", "event")))

    # 同一件事（同一天 + 同基础标题）只留信息最全的那条
    seen = set()
    groups: dict[str, list[tuple[str, str, str, str]]] = {}
    for date_s, _, _, tag, title, detail, track in sorted(rows, key=lambda z: (z[0], z[1], z[2])):
        tk = (date_s, _base_title(title))
        if tk in seen:
            continue
        seen.add(tk)
        groups.setdefault(date_s, []).append((tag, title, detail, track))

    dates = sorted(groups)
    if not dates:
        return '<li class="tl-empty">暂无需要盯的日期。</li>', 0

    out = []
    for n, date_s in enumerate(dates[:max_days]):
        d = pe.parse_date(date_s)
        delta = (d - base).days
        when = _when_label(delta)
        # 今天与明天默认展开
        opening = " open" if delta <= 1 else ""
        hidden = ' class="tl-hidden"' if n >= fold_after else ''
        items = groups[date_s]
        lis = []
        for tag, title, detail, track in items:
            # 标题里的方向/说明拆成副行，避免和标题挤在一行被截断
            sub = ''
            if detail:
                sub = '<span class="sub">' + esc(detail) + '</span>'
            lis.append(
                '<li><span class="' + track_class(track) + '">' + esc(tag) + '</span>'
                '<span class="ti">' + esc(title) + sub + '</span></li>'
            )
        out.append(
            '<li' + hidden + '><details class="tl-date" data-idx="' + str(n) + '"' + opening + '>'
            '<summary class="tl-head">'
            '<span class="dot"></span>'
            '<span class="tld">' + esc(date_s[5:]) + '</span>'
            '<span class="tlw">' + esc(WDC[d.weekday()]) + '</span>'
            '<span class="tlmeta">'
            + (('<span class="tltoday">' + esc(when) + '</span>')
               if delta == 0 else ('<span class="' + _stat_class(delta) + '">' + esc(when) + '</span>'))
            + '　<b>' + str(len(items)) + '</b> 项</span>'
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


def render_week_panel(plan: dict, base: dt.date, span_days: int = 14,
                      open_days: int = 1) -> tuple[str, int]:
    """「本周全景」：一周条带 + 下面直接铺开这一周每一天的具体清单。

    以前只画 7 个格子，左栏下面留一大片空白、还得自己去今日清单里一天天翻；
    现在条带负责"概览"（哪天最重、哪天的完成率低），下面的清单负责"内容"：
      · 每 7 天一段，段间用虚线分隔，往后多看的几天不会和本周混在一起；
      · 每一天是一个 <details>，默认展开今天及随后的 open_days 天，其余收起；
      · 点条带里的日期数字 = 展开那天并滚过去（JS weekJump），不打断阅读。
    返回 (HTML, 覆盖天数)。
    """
    first = base - dt.timedelta(days=base.weekday())
    info = _day_items(plan, first, span_days, with_classes=True)
    dates = sorted(info)

    def real_items(rec):
        return [t for t in rec["items"] if t["kind"] != "class"]

    cells = []
    # 条带只放"本周"7 天；往后一周只出现在下面的逐日清单里（14 个格子会撑坏 7 列布局）
    for iso in dates[:7]:
        rec = info[iso]
        d = rec["date"]
        delta = (d - base).days
        tasks, real = rec["items"], real_items(rec)
        done = sum(1 for t in real if t.get("done"))
        pct = (done / len(real) * 100) if real else 0
        courses = len([t for t in tasks if t["kind"] == "class"])
        classes = ["wk-cell"]
        if d == base:
            classes.append("today")
        cells.append(
            '<a class="' + " ".join(classes) + '" href="#wk-day-' + iso + '" data-jump="' + iso
            + '" title="' + esc(iso + " 周" + str(d.weekday() + 1) + "　" + str(courses) + " 门课 · "
                                + str(len(real)) + " 项任务　点击看这一天的清单") + '">'
            '<div class="wk-wd">' + esc(pe.WEEKDAY_CN[d.weekday()]) + '</div>'
            '<div class="wk-dd">' + str(d.day) + '</div>'
            '<div class="wk-when">' + esc(_when_label(delta)) + '</div>'
            '<div class="wk-cnt">' + str(courses) + ' 课 · ' + str(len(real)) + ' 任务</div>'
            '<div class="wk-bar"><i style="width:' + f"{pct:.0f}" + '%"></i></div></a>'
        )

    same_week = [t for iso in dates if (info[iso]["date"] - first).days < 7
                 for t in real_items(info[iso])]
    week_done = sum(1 for t in same_week if t.get("done"))
    week_min = sum(int(t.get("minutes") or 0) for t in same_week)
    all_real = [t for iso in dates for t in real_items(info[iso])]
    all_min = sum(int(t.get("minutes") or 0) for t in all_real)

    blocks, i = [], 0
    while i < len(dates):
        chunk = dates[i:i + 7]
        chunk_first = info[chunk[0]]["date"]
        parts = []
        for iso in chunk:
            rec = info[iso]
            d = rec["date"]
            delta = (d - base).days
            tasks, real = rec["items"], real_items(rec)
            done = sum(1 for t in real if t.get("done"))
            courses = [t for t in tasks if t["kind"] == "class"]
            events = [t for t in tasks if t["kind"] != "class"]
            events_html = "".join(
                '<span class="chip ev">' + esc(t["title"]) + "</span>" for t in events[:3]
            )
            keyed = [t for t in tasks if t["kind"] == "keydate"]
            key_html = "".join('<span class="chip key">' + esc(t["title"]) + "</span>"
                               for t in keyed[:2])
            chips = events_html + key_html
            if len(events) > 3:
                chips += '<span class="chip">还有 ' + str(len(events) - 3) + " 项…</span>"
            if not tasks:
                chips = '<span class="chip">空档日：没有课，也没有排任务</span>'
            body = "".join(render_mini_task(t) for t in tasks)
            if body:
                body = '<ul class="wk-items">' + body + "</ul>"
            # 默认展开"今天及其后 open_days 天"；往前翻到的过去日期不自动展开
            opening = " open" if 0 <= delta <= open_days else ""
            hint = "今日" if delta == 0 else _when_label(delta)
            parts.append(
                '<details class="wk-day' + (" is-today" if delta == 0 else "") + '" id="wk-day-'
                + iso + '" data-date="' + iso + '"' + opening + '>'
                '<summary class="wk-hd">'
                '<span class="wk-title">' + esc(iso[5:] + " " + info[iso]["weekday"]) + "</span>"
                '<span class="stat ' + ("stat-today" if delta == 0 else
                                       ("stat-soon" if 0 < delta <= 3 else "stat-info")) + '">'
                + esc(hint) + "</span>"
                '<span class="wk-sum">' + str(len(courses)) + " 门课 · " + str(len(real))
                + " 项 · " + str(sum(int(t.get("minutes") or 0) for t in real)) + " 分钟</span>"
                '<span class="wk-prog">完成 ' + str(done) + "/" + str(len(real)) + "</span>"
                "</summary>" + body + "</details>"
            )
        wk_head = ("本周 " + chunk_first.isoformat() + " 起（周一 → 周日）"
                   if i == 0 else
                   "往后一周 " + chunk_first.isoformat() + " 起（周一 → 周日）")
        blocks.append('<hr class="wk-gap"><div class="wk-tools"><span><b>'
                      + esc(wk_head) + "</b>　" + str(len(chunk)) + " 天</span></div>"
                      + "".join(parts))
        i += 7

    strip = (
        '<div class="wk">' + "".join(cells) + '</div>'
    )

    tools = (
        '<div class="wk-tools" style="margin-top:10px">'
        '<span><b>逐日清单</b>　覆盖 ' + str(len(dates)) + ' 天（本周 + 往后一周）· 共 '
        + str(len(all_real)) + " 项自主任务 / " + str(all_min) + " 分钟"
        + '<span class="tag" style="margin-left:8px">默认展开今天起 ' + str(open_days + 1)
        + ' 天</span></span>'
        '<span class="tl-more" id="wk-toggle" onclick="toggleWeekDays()">展开全部日期</span></div>'
        '<p class="hint" style="margin:0 0 4px">点某一天的标题行可折叠/展开；'
        '点上面的日期数字可直接跳到那一天。本周 ' + str(len(same_week)) + " 项自主任务，已完成 "
        + str(week_done) + " 项 · 计划投入 " + str(week_min) + " 分钟。</p>"
    )
    return strip + tools + '<div class="wk-panel" id="wk-days">' + "".join(blocks) + "</div>", len(dates)


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

    week_html, week_days = render_week_panel(plan, base)
    left = (
        '<div class="grid" style="margin:0">'
        + render_day_card(base, week, tasks)
        + '<section class="card" id="week"><h2>本周全景 <span class="tag">'
        + esc((base - dt.timedelta(days=base.weekday())).isoformat()) + ' 起 · 覆盖 '
        + str(week_days) + ' 天</span></h2>'
        '<p class="hint">上面 7 个格子是概览：柱条＝该日自主任务的完成比例，完成度低于 '
        '50% 会明显偏空；下面直接铺开每一天的清单，不用来回翻。改完计划后运行 '
        '<span class="cmd">python app.py replan</span> 重算。</p>'
        + week_html + '</section>'
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
