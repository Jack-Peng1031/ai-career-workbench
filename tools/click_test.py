# -*- coding: utf-8 -*-
"""用真实浏览器点一遍「本周全景」的格子，验证切换真的生效。

为什么需要它：以前的检查都是"看 HTML 里有没有某个类名"，而这次的 bug 恰好是
JS 选择器写错（`.wk-day` vs 实际类名 `wk-day-card`）——静态文本检查全绿，
但用户点下去高亮变了、下面内容不变。只有真的点一次才能发现。

用法： python tools/click_test.py [页面路径或 URL]
默认点本地 dashboard.html（file:// 打开也能跑，因为切换是纯前端行为）。
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import socket
import struct
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")

EDGE = next((p for p in (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
) if Path(p).exists()), None)

fails: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("  ok   " if cond else "  FAIL ") + name + (("  -> " + str(detail)) if detail and not cond else ""))
    if not cond:
        fails.append(name)


# --------------------------------------------------------------------------
# 极简 CDP 客户端（只用标准库：HTTP 拿 target，WebSocket 发命令）
# --------------------------------------------------------------------------
class WS:
    def __init__(self, url: str):
        _, _, rest = url.partition("://")
        hostport, _, path = rest.partition("/")
        host, _, port = hostport.partition(":")
        self.sock = socket.create_connection((host, int(port)), timeout=20)
        key = base64.b64encode(secrets.token_bytes(16)).decode()
        req = (f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\n"
               f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
               "Sec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.sock.recv(4096)
        if b"101" not in buf.split(b"\r\n")[0]:
            raise RuntimeError("WebSocket 握手失败：" + buf[:120].decode("utf-8", "replace"))
        self._id = 0

    def send(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        payload = json.dumps({"id": self._id, "method": method, "params": params or {}}).encode()
        mask = secrets.token_bytes(4)
        n = len(payload)
        header = b"\x81"
        if n < 126:
            header += bytes([0x80 | n])
        elif n < 1 << 16:
            header += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            header += bytes([0x80 | 127]) + struct.pack(">Q", n)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(header + mask + masked)
        while True:
            msg = self._recv()
            data = json.loads(msg)
            if data.get("id") == self._id:
                return data

    def _recv(self) -> str:
        first = self._read(2)
        length = first[1] & 0x7F
        if length == 126:
            length = struct.unpack(">H", self._read(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", self._read(8))[0]
        return self._read(length).decode("utf-8", "replace")

    def _read(self, n: int) -> bytes:
        out = b""
        while len(out) < n:
            chunk = self.sock.recv(n - len(out))
            if not chunk:
                raise RuntimeError("连接被关闭")
            out += chunk
        return out

    def eval(self, expr: str):
        res = self.send("Runtime.evaluate",
                        {"expression": expr, "returnByValue": True, "awaitPromise": True})
        result = res.get("result", {}).get("result", {})
        if "value" in result:
            return result["value"]
        return result.get("description")


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main() -> int:
    if not EDGE:
        print("  skip  找不到 Edge/Chrome，跳过点击测试")
        return 0
    target = sys.argv[1] if len(sys.argv) > 1 else (ROOT / "dashboard.html").as_uri()
    port = free_port()
    # 必须用绝对路径：相对路径的 --user-data-dir 会让 Edge 直接不起来（调试端口永远不监听）
    profile = (ROOT / "exports" / "_click_profile").resolve()
    errlog = open(ROOT / "exports" / "_click_edge.log", "wb")
    proc = subprocess.Popen(
        [EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
         "--disable-extensions", f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
         "--window-size=1400,1000", target],
        stdout=subprocess.DEVNULL, stderr=errlog)

    ws = None
    try:
        # 等调试端口就绪。注意：Edge 会先开自己的登录/同步标签页，
        # 直接取 pages[0] 会连到那个页面上（症状：document.title 是"同步你的浏览数据"）。
        # 所以按 URL 认领我们自己那个 target。
        ws_url = None
        want = target.split("?")[0]
        for _ in range(60):
            if proc.poll() is not None:
                print("  skip  浏览器自己退出了（见 exports/_click_edge.log），跳过点击测试")
                return 0
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=2) as r:
                    tabs = json.loads(r.read().decode())
                pages = [t for t in tabs
                         if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
                mine = [t for t in pages if want in (t.get("url") or "")]
                pick = (mine or pages)
                if pick:
                    ws_url = pick[-1]["webSocketDebuggerUrl"]
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.5)
        if not ws_url:
            print("  skip  浏览器调试端口没起来，跳过点击测试")
            return 0

        ws = WS(ws_url)
        time.sleep(1.5)
        # 万一还是连到了别的标签页，直接导航到目标页
        if not ws.eval("!!document.getElementById('week')"):
            ws.send("Page.enable")
            ws.send("Page.navigate", {"url": target})
            for _ in range(40):
                time.sleep(0.5)
                if ws.eval("!!document.getElementById('week')"):
                    break
        # 固定视口，保证"滚进视野后算坐标"这件事可预期
        ws.send("Emulation.setDeviceMetricsOverride",
                {"width": 1400, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
        time.sleep(0.4)
        print("点击测试目标：" + target + "\n")

        def click_cell(index: int) -> None:
            """把第 index 个格子滚进视野，再按视口坐标真的点一下。

            注意：Input.dispatchMouseEvent 用的是**视口坐标**，格子如果在屏幕外
            （页面很长时很容易），点到的其实是页面根元素——先 scrollIntoView 再取 rect。
            """
            box = ws.eval("""(function(){var c=document.querySelectorAll('#week .wk-cell')[%d];
              c.scrollIntoView({block:'center'}); var r=c.getBoundingClientRect();
              return JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2});})()""" % index)
            pt = json.loads(box)
            ws.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": pt["x"], "y": pt["y"],
                                                "button": "left", "clickCount": 1})
            ws.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": pt["x"], "y": pt["y"],
                                                "button": "left", "clickCount": 1})
            time.sleep(0.7)

        state = """(function(){var v=document.getElementById('wk-day');
          return v? v.innerText.replace(/\\s+/g,' ').trim() : null;})()"""
        count = """document.querySelectorAll('#week .wk-cell').length"""
        cells = ws.eval(count)
        check("页面里有 7 个可点的格子", cells == 7, cells)
        if cells != 7:
            return 1

        first = ws.eval(state)
        check("初始就显示了某一天的事项", bool(first and len(str(first)) > 10), str(first)[:80])
        # 记住初始选中的是哪一格（是"今天"，不一定是第 0 格）——注意要在点击之前取
        home = int(ws.eval("""(function(){var c=document.querySelectorAll('#week .wk-cell');
          for(var i=0;i<c.length;i++){ if(c[i].classList.contains('is-sel')){ return i; } }
          return 0;})()"""))

        # 真的在屏幕上点第 4 个格子（不是直接调函数）
        click_cell(3)
        second = ws.eval(state)
        want = ws.eval("document.querySelectorAll('#week .wk-cell')[3].getAttribute('data-day')")
        check("点击后下面的内容确实换了", second != first,
              f"点击前={str(first)[:40]}… 点击后={str(second)[:40]}…")
        check("换出来的内容属于被点的那一天", want and str(want)[5:] in str(second), str(want))
        check("高亮跟着移动到被点的格子",
              ws.eval("""document.querySelectorAll('#week .wk-cell')[3].classList.contains('is-sel')""") is True)
        check("其他格子不再高亮",
              ws.eval("""document.querySelectorAll('#week .wk-cell.is-sel').length""") == 1,
              ws.eval("document.querySelectorAll('#week .wk-cell.is-sel').length"))

        # 再点回"今天"那一格，验证来回切换都正常
        click_cell(home)
        third = ws.eval(state)
        check("来回点两次仍然会切换", third == first, f"{str(third)[:40]}… vs {str(first)[:40]}…")
        check("切回来的那天也高亮",
              ws.eval("""document.querySelectorAll('#week .wk-cell')[%d].classList.contains('is-sel')"""
                      % home) is True)
    finally:
        if ws:
            try:
                ws.sock.close()
            except Exception:  # noqa: BLE001
                pass
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            proc.kill()
        time.sleep(0.5)
        errlog.close()
        import shutil
        shutil.rmtree(profile, ignore_errors=True)

    print("\n" + ("点击测试全部通过 ✅" if not fails else f"失败 {len(fails)} 项：" + "、".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
