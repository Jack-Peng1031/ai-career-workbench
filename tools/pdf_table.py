# -*- coding: utf-8 -*-
"""Rebuild the SCU course-schedule table using the PDF's own rule geometry.

Columns and rows are taken from the long/wide thin rectangles Skia emitted as
table borders, so cells no longer depend on guessed text spacing.
"""
import re
import sys
import zlib

sys.stdout.reconfigure(encoding="utf-8")
data = open(r"D:\applications\downloads\11212\课程表.pdf", "rb").read()
OBJ = re.compile(rb"(?:^|[\r\n])(\d+) 0 obj(.*?)endobj", re.S)
objects = {int(m.group(1)): m.group(2) for m in OBJ.finditer(data)}


def stream_of(body):
    sm = re.search(rb"stream\r?\n", body)
    if not sm:
        return None
    raw = body[sm.end():]
    raw = raw[: raw.rfind(b"endstream")]
    try:
        return zlib.decompress(raw)
    except Exception:
        return raw


def parse_cmap(raw):
    m = {}
    if not raw:
        return m
    for cm in re.finditer(rb"beginbfchar(.*?)endbfchar", raw, re.S):
        for a, b in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", cm.group(1)):
            m[int(a, 16)] = bytes.fromhex(b.decode()).decode("utf-16-be", "ignore")
    for cm in re.finditer(rb"beginbfrange(.*?)endbfrange", raw, re.S):
        for lo, hi, dst in re.findall(
            rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", cm.group(1)
        ):
            lo_i, hi_i, d_i = int(lo, 16), int(hi, 16), int(dst, 16)
            for k in range(lo_i, hi_i + 1):
                m[k] = chr(d_i + (k - lo_i))
    return m


resources = {m.group(1).decode(): int(m.group(2)) for m in re.finditer(rb"/(F\d+)\s+(\d+) 0 R", data)}
font_maps = {}
for rn, onum in resources.items():
    body = objects.get(onum, b"")
    tu = re.search(rb"/ToUnicode\s+(\d+) 0 R", body)
    if tu:
        font_maps[rn] = parse_cmap(stream_of(objects.get(int(tu.group(1)), b"")) or b"")

content = None
for onum, body in objects.items():
    st = stream_of(body)
    if st and b"BT" in st:
        content = st.decode("latin-1")

NUM = r"[-+]?[\d.]+"
TOKEN = re.compile(
    r"/(?P<font>F\d+)\s+(?P<fs>" + NUM + r")\s+Tf"
    r"|(?P<tm>" + NUM + r"\s+" + NUM + r"\s+" + NUM + r"\s+" + NUM + r"\s+(?P<tmx>" + NUM + r")\s+(?P<tmy>" + NUM + r")\s+Tm)"
    r"|(?P<tdx>" + NUM + r")\s+(?P<tdy>" + NUM + r")\s+(?:Td|TD)"
    r"|/ActualText\s*<(?P<at>[0-9A-Fa-f]+)>"
    r"|<(?P<hex>[0-9A-Fa-f]*)>\s+Tj"
)
glyphs = []
font = "F4"
x = y = 0.0
pending = None
for t in TOKEN.finditer(content):
    if t.group("font"):
        font = t.group("font")
    elif t.group("tm"):
        x, y = float(t.group("tmx")), float(t.group("tmy"))
    elif t.group("tdx") is not None:
        x += float(t.group("tdx"))
        y += float(t.group("tdy"))
    elif t.group("at") is not None:
        pending = bytes.fromhex(t.group("at")).decode("utf-16-be", "ignore")
    elif t.group("hex") is not None:
        if pending is not None:
            glyphs.append((round(x, 1), round(y, 1), pending))
            pending = None
        else:
            mp = font_maps.get(font, {})
            s = "".join(mp.get(b, "") for b in bytes.fromhex(t.group("hex") or "00"))
            if s and s.strip():
                glyphs.append((round(x, 1), round(y, 1), s))

rects = [tuple(float(v) for v in m.groups()) for m in re.finditer(r"([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+) re", content)]
VR = sorted({round(r[0]) for r in rects if abs(r[2] - 1) < 0.6 and r[3] > 40})
HR = sorted({round(r[1]) for r in rects if abs(r[3] - 1) < 0.6 and r[2] > 40}, reverse=True)
print("column boundaries x:", VR)
print("row boundaries y (top->bottom):", HR)

# column index by x
def col_of(gx):
    for i in range(len(VR) - 1):
        if VR[i] <= gx < VR[i + 1]:
            return i
    return None


# row band: y descending; glyph y just below a row line belongs to that row
def row_of(gy):
    for i in range(len(HR) - 1):
        if HR[i + 1] < gy <= HR[i]:
            return i
    if gy > HR[0]:
        return 0
    return len(HR) - 2


CELLS = {}
for gx, gy, s in glyphs:
    c, r = col_of(gx), row_of(gy)
    if c is None:
        continue
    CELLS.setdefault((r, c), []).append((gx, gy, s))

out = []
for (r, c) in sorted(CELLS):
    items = CELLS[(r, c)]
    # split into visual lines by y (23 units == one line box)
    items.sort(key=lambda z: (-z[1], z[0]))
    lines, cur = [], [items[0]]
    for it in items[1:]:
        if abs(it[1] - cur[-1][1]) <= 4:
            cur.append(it)
        else:
            lines.append(cur)
            cur = [it]
    lines.append(cur)
    # top line first (higher y), glyphs left-to-right inside a line
    text = " ".join("".join(g[2] for g in sorted(ln, key=lambda z: z[0])) for ln in lines)
    out.append((r, c, text))

with open(r"D:\WorkSpace\ai-career-workbench\materials\_pdf_cells.txt", "w", encoding="utf-8") as fh:
    for r, c, text in out:
        fh.write(f"row{r:02d} col{c}: {text}\n")
        print(f"row{r:02d} col{c}: {text}")
