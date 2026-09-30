# -*- coding: utf-8 -*-
import re, sys, zlib
sys.stdout.reconfigure(encoding="utf-8")
data = open(r"D:\applications\downloads\11212\课程表.pdf", "rb").read()
print("=== objects mentioning Font ===")
n = 0
for m in re.finditer(rb"(\d+) 0 obj(.*?)endobj", data, re.S):
    body = m.group(2)
    if b"/Font" in body or b"/Type0" in body or b"/Type3" in body or b"/ToUnicode" in body:
        n += 1
        if n <= 25:
            print("---- obj", m.group(1).decode(), "len", len(body))
            print(body[:600].decode("latin-1"))
print("total font-ish objects:", n)
print("=== xref/pages ===")
i = data.find(b"/Pages")
print(data[i-100:i+400].decode("latin-1", "ignore"))
print("=== trailer ===")
j = data.rfind(b"trailer")
print(data[j:j+500].decode("latin-1", "ignore") if j > 0 else "no trailer kw")
print("=== all ToUnicode refs ===")
print(sorted(set(re.findall(rb"/ToUnicode\s+(\d+) 0 R", data))))
print("=== resources dict sample ===")
k = data.find(b"/Resources")
print(data[k:k+1500].decode("latin-1", "ignore"))
