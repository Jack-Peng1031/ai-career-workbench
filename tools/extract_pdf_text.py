# -*- coding: utf-8 -*-
"""Extract positioned text from a browser-printed (Skia/PDF) document.

Skia emits one Type3 font per glyph with its own /ToUnicode CMap. This module
maps resource name (/F4 ...) -> glyph code -> Unicode, then replays the content
stream text operators to rebuild rows and columns.
"""
import re
import sys
import zlib

sys.stdout.reconfigure(encoding="utf-8")
sys.setrecursionlimit(10000)

PDF = sys.argv[1] if len(sys.argv) > 1 else r"D:\applications\downloads\11212\课程表.pdf"
OUT = sys.argv[2] if len(sys.argv) > 2 else None

data = open(PDF, "rb").read()
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
    mapping = {}
    if not raw:
        return mapping
    for cm in re.finditer(rb"beginbfchar(.*?)endbfchar", raw, re.S):
        for a, b in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", cm.group(1)):
            mapping[int(a, 16)] = bytes.fromhex(b.decode()).decode("utf-16-be", "ignore")
    for cm in re.finditer(rb"beginbfrange(.*?)endbfrange", raw, re.S):
        for lo, hi, dst in re.findall(
            rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", cm.group(1)
        ):
            lo_i, hi_i, d_i = int(lo, 16), int(hi, 16), int(dst, 16)
            for k in range(lo_i, hi_i + 1):
                mapping[k] = chr(d_i + (k - lo_i))
    return mapping


# ---- resource name -> glyph map, via the page /Font dictionary
resources = {}
for m in re.finditer(rb"/(F\d+)\s+(\d+) 0 R", data):
    resources[m.group(1).decode()] = int(m.group(2))

font_maps = {}
for resname, onum in resources.items():
    body = objects.get(onum)
    if not body:
        continue
    tu = re.search(rb"/ToUnicode\s+(\d+) 0 R", body)
    if not tu:
        continue
    font_maps[resname] = parse_cmap(stream_of(objects.get(int(tu.group(1)), b"")))

sys.stderr.write("font resources: %d, with ToUnicode: %d\n" % (len(resources), len(font_maps)))

# ---- content streams
pages = []
for onum, body in objects.items():
    st = stream_of(body)
    if st and b"BT" in st:
        pages.append((onum, st.decode("latin-1")))
pages.sort()
sys.stderr.write("content streams: %d\n" % len(pages))

NUM = r"[-+]?[\d.]+"
TOKEN = re.compile(
    r"/(?P<font>F\d+)\s+" + NUM + r"\s+Tf"
    r"|(?P<tm>" + NUM + r"\s+" + NUM + r"\s+" + NUM + r"\s+" + NUM + r"\s+(?P<tmx>" + NUM + r")\s+(?P<tmy>" + NUM + r")\s+Tm)"
    r"|(?P<tdx>" + NUM + r")\s+(?P<tdy>" + NUM + r")\s+(?:Td|TD)"
    r"|/ActualText\s*<(?P<at>[0-9A-Fa-f]+)>"
    r"|<(?P<hex>[0-9A-Fa-f]*)>\s*Tj"
    r"|(?P<bt>\bBT\b)"
)


def parse(content):
    out = []
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
                out.append((x, y, pending))
                pending = None
            else:
                mp = font_maps.get(font, {})
                s = "".join(mp.get(b, "") for b in bytes.fromhex(t.group("hex") or "00"))
                if s:
                    out.append((x, y, s))
        elif t.group("bt"):
            pending = None
    return out


rows = []
for onum, content in pages:
    items = [it for it in parse(content) if it[2].strip()]
    if not items:
        continue
    items.sort(key=lambda it: (round(it[1] / 4.0), it[0]))
    buckets = {}
    for x, y, s in items:
        buckets.setdefault(round(y / 4.0), []).append((x, y, s))
    for key in sorted(buckets):
        cells = sorted(buckets[key], key=lambda t: t[0])
        text = ""
        prev_end = None
        for x, y, s in cells:
            if prev_end is not None and x - prev_end > 9:
                text += " "
            text += s
            prev_end = x + 7.2 * len(s)
        rows.append((round(cells[0][1], 1), text.strip()))

lines = [f"[y={y:8.1f}] {t}" for y, t in sorted(rows, key=lambda r: -r[0])]
result = "\n".join(lines)
if OUT:
    open(OUT, "w", encoding="utf-8").write(result)
print(result)
