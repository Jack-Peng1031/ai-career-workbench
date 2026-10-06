# -*- coding: utf-8 -*-
"""本地 ↔ PythonAnywhere 同步（纯标准库，不需要 pip 装任何东西）。

和 gitpush.bat 是一对：gitpush.bat 管「版本历史」，这个脚本管「线上那份文件」。

原理
----
PythonAnywhere 上的项目和本地是两份独立的文件。这个脚本用两种通道把本地改动送上去：
  1. SSH（推荐）：调用系统自带的 ssh / scp，先配一次公钥，之后免密；
  2. Files API：只有 API Token 也能用（逐文件上传），不需要开 SSH。

用法（在项目根目录）
--------------------
    python tools/pa_sync.py setup       # 生成/显示 SSH 公钥，并给出配置步骤
    python tools/pa_sync.py check       # 检查连通性、认证方式、远端目录是否存在
    python tools/pa_sync.py diff        # 只看哪些文件会同步（不传任何文件）
    python tools/pa_sync.py push        # 本地 → PythonAnywhere
    python tools/pa_sync.py push --all  # 忽略增量判断，全量覆盖（推荐首次使用）
    python tools/pa_sync.py pull        # PythonAnywhere → 本地（会覆盖本地同名文件）
    python tools/pa_sync.py reload      # 通知 PythonAnywhere 重新加载 Web App
    python tools/pa_sync.py push --reload   # 推完顺手 reload

配置（任选其一，环境变量优先）
------------------------------
    .pa_sync.json    放在项目根目录（已加入 .gitignore，不会进 Git）：
       {"user": "JackPeng", "host": "ssh.pythonanywhere.com",
        "remote_dir": "ai-career-workbench", "key": "~/.ssh/id_ed25519_pa",
        "token": "", "domain": "JackPeng.pythonanywhere.com"}
    环境变量：PA_USER / PA_HOST / PA_DIR / PA_KEY / PA_TOKEN / PA_DOMAIN

安全
----
token 与私钥都不会写进仓库；脚本只读它们，不做任何上传以外的操作。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / ".pa_sync.json"
STAMP = ".pa_sync_stamp"

# 这些目录/文件不同步：本机运行数据、缓存、Git 元数据、脚本自身的配置
EXCLUDE_DIRS = {"__pycache__", ".git", ".idea", ".vscode", "state", "logs", "exports",
                "records", "node_modules", ".pytest_cache"}
EXCLUDE_FILES = {".pa_sync.json", STAMP, "Thumbs.db", ".DS_Store", "desktop.ini"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".log", ".png", ".jpg", ".jpeg", ".zip", ".tmp"}

DEFAULTS = {
    "user": os.environ.get("PA_USER", "JackPeng"),
    "host": os.environ.get("PA_HOST", "ssh.pythonanywhere.com"),
    "remote_dir": os.environ.get("PA_DIR", "ai-career-workbench"),
    "key": os.environ.get("PA_KEY", "~/.ssh/id_ed25519_pa"),
    "token": os.environ.get("PA_TOKEN", ""),
    "domain": os.environ.get("PA_DOMAIN", ""),
}


class Fail(Exception):
    """预期内的错误：只打印一句话，不抛栈。"""


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG.exists():
        try:
            data = json.loads(CONFIG.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise Fail(".pa_sync.json 不是合法 JSON：" + str(exc)) from exc
        for k, v in data.items():
            cfg[k] = v
    for k, env in (("user", "PA_USER"), ("host", "PA_HOST"), ("remote_dir", "PA_DIR"),
                   ("key", "PA_KEY"), ("token", "PA_TOKEN"), ("domain", "PA_DOMAIN")):
        if os.environ.get(env):
            cfg[k] = os.environ[env]
    cfg["key"] = str(Path(os.path.expanduser(str(cfg["key"]))))
    return cfg


def banner(text: str) -> None:
    print("\n" + "=" * 62)
    print("  " + text)
    print("=" * 62)


# --------------------------------------------------------------------------
# 本地文件清单
# --------------------------------------------------------------------------
def local_files() -> list[Path]:
    out = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if any(part in EXCLUDE_DIRS for part in rel.parts[:-1]):
            continue
        if rel.name in EXCLUDE_FILES or rel.suffix.lower() in EXCLUDE_SUFFIX:
            continue
        if rel.name.startswith("_shot") or rel.name.startswith("_devcheck"):
            continue
        out.append(rel)
    return out


def human(n: int) -> str:
    for unit in ("B", "KB", "MB"):
        if n < 1024 or unit == "MB":
            return (f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}")
        n /= 1024.0
    return f"{n:.1f} MB"


# --------------------------------------------------------------------------
# SSH / SCP 通道
# --------------------------------------------------------------------------
def _run(cmd: list[str], timeout: int = 120) -> tuple[int, str]:
    """跑外部命令。ssh 会把 PythonAnywhere 的欢迎语写到 stderr，这里合并处理。"""
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise Fail("找不到命令 " + cmd[0] + "，请确认 Windows 自带的 OpenSSH 客户端可用") from exc
    except subprocess.TimeoutExpired as exc:
        raise Fail("命令超时：" + " ".join(cmd[:3])) from exc
    out = (proc.stdout or b"").decode("utf-8", "replace")
    err = (proc.stderr or b"").decode("utf-8", "replace")
    text = (out + "\n" + err).strip()
    # 过滤掉 PythonAnywhere 的登录横幅，只留真正有用的输出
    keep = [ln for ln in text.splitlines()
            if "PythonAnywhere SSH" not in ln and "help.pythonanywhere.com" not in ln
            and not ln.startswith("<<<<<<")]
    return proc.returncode, "\n".join(keep).strip()


class SSHSync:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.target = f"{cfg['user']}@{cfg['host']}"
        self.key = Path(cfg["key"])
        self.dir = str(cfg["remote_dir"]).strip("/")
        # 默认非交互：没配公钥时 ssh 会弹密码提示，脚本调用会一直挂在那里等输入。
        # 想手输密码就加 --ask（或设 PA_INTERACTIVE=1）。
        self.batch = not (getattr(cfg, "interactive", False)
                          or os.environ.get("PA_INTERACTIVE") == "1")

    def _opts(self) -> list[str]:
        opts = ["-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=accept-new"]
        if self.batch:
            opts += ["-o", "BatchMode=yes"]
        if self.key.exists():
            opts += ["-i", str(self.key)]
        return opts

    def ssh(self, script: str, timeout: int = 120) -> tuple[int, str]:
        return _run(["ssh"] + self._opts() + [self.target, script], timeout=timeout)

    def scp(self, sources: list[str], dest: str, timeout: int = 300) -> tuple[int, str]:
        return _run(["scp", "-p", "-q"] + self._opts() + sources + [dest], timeout=timeout)

    # —— 常用远端动作 ——
    def check(self) -> tuple[bool, str]:
        code, out = self.ssh("echo PA_OK; whoami; pwd; ls -d " + self.dir + " 2>/dev/null || echo NO_DIR")
        return (code == 0 and "PA_OK" in out), out

    def mkdirs(self, rels: list[Path]) -> None:
        dirs = sorted({str(r.parent).replace("\\", "/") for r in rels if str(r.parent) != "."})
        if not dirs:
            return
        script = "; ".join(f"mkdir -p {self.dir}/{d}" for d in dirs)
        code, out = self.ssh(script)
        if code != 0:
            raise Fail("创建远端目录失败：" + out)

    def stamp(self) -> None:
        now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.ssh(f"echo '{now}' > {self.dir}/{STAMP}")

    def listing(self) -> dict[str, int]:
        """远端文件 → 字节数。"""
        code, out = self.ssh(
            f"cd {self.dir} 2>/dev/null && find . -type f ! -name '{STAMP}' "
            f"-printf '%s\\t%p\\n' | sed 's|^\\([0-9]*\\)\\t\\./|\\1\\t|'")
        if code != 0:
            raise Fail("读取远端文件列表失败：" + out)
        res: dict[str, int] = {}
        for line in out.splitlines():
            size, _, path = line.partition("\t")
            if path.strip() and size.strip().isdigit():
                res[path.strip()] = int(size)
        return res


# --------------------------------------------------------------------------
# Files API 通道（没有 SSH 也能用）
# --------------------------------------------------------------------------
def _multipart(field: str, filename: str, data: bytes) -> tuple[bytes, str]:
    """手搓 multipart/form-data（标准库没有，而 PythonAnywhere 的 Files API 只认这个）。"""
    boundary = "----pa-sync-" + os.urandom(12).hex()
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    return head + data + tail, "multipart/form-data; boundary=" + boundary


class ApiSync:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.user = cfg["user"]
        self.token = cfg["token"]
        if not self.token:
            raise Fail("没有 API Token：请在 .pa_sync.json 里填 token，或先配置 SSH 公钥")
        self.base = f"https://www.pythonanywhere.com/api/v0/user/{self.user}/files/path"

    def _req(self, url: str, data: bytes | None = None, method: str | None = None):
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Authorization": "Token " + self.token})
        if data is not None and method is None:
            req.add_header("Content-Type", "application/octet-stream")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()
        except urllib.error.URLError as exc:
            raise Fail("连不上 PythonAnywhere API：" + str(exc.reason)) from exc

    def remote_path(self, rel: str) -> str:
        home = f"/home/{self.user}"
        parts = [p for p in str(self.cfg["remote_dir"]).strip("/").split("/") if p]
        return "/".join([home] + parts + [rel.replace("\\", "/")])

    def upload(self, rel: Path) -> None:
        """Files API 要求 multipart 表单，字段名固定为 content（附带的文件名会被忽略）。"""
        url = self.base + self.remote_path(str(rel))
        body, ctype = _multipart("content", Path(rel).name, (ROOT / rel).read_bytes())
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Authorization": "Token " + self.token, "Content-Type": ctype})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                status = r.status
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:200].decode("utf-8", "replace")
            raise Fail(f"上传 {rel} 失败（HTTP {exc.code}）：{detail}") from exc
        # 201 = 新建，200 = 覆盖已有文件
        if status not in (200, 201):
            raise Fail(f"上传 {rel} 失败（HTTP {status}）")

    def download(self, rel: str) -> bytes:
        status, body = self._req(self.base + self.remote_path(rel))
        if status != 200:
            raise Fail(f"下载 {rel} 失败（HTTP {status}）")
        return body


def reload_webapp(cfg: dict) -> str:
    """让 PythonAnywhere 重新加载 Web App。只有配了 token 才能远程触发。"""
    if not cfg.get("token"):
        return ("没配 API Token，无法远程 reload。\n"
                "  纯静态文件（dashboard.html）不需要 reload，刷新页面即可；\n"
                "  如果你挂的是 WSGI/Flask 应用，请在 Web 标签页点一次 Reload。")
    domain = cfg.get("domain") or (str(cfg["user"]) + ".pythonanywhere.com")
    url = f"https://www.pythonanywhere.com/api/v0/user/{cfg['user']}/webapps/{domain}/reload/"
    req = urllib.request.Request(url, data=b"", method="POST",
                                 headers={"Authorization": "Token " + cfg["token"]})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return f"已通知 PythonAnywhere 重新加载 {domain}（HTTP {r.status}）。"
    except urllib.error.HTTPError as exc:
        return (f"reload 失败（HTTP {exc.code}）：{exc.read()[:200].decode('utf-8', 'replace')}\n"
                "  请到 Web 标签页手动点一次 Reload。")
    except urllib.error.URLError as exc:
        return "reload 失败（网络）：" + str(exc.reason)


# --------------------------------------------------------------------------
# 子命令
# --------------------------------------------------------------------------
def _public_key(cfg: dict, create: bool = True) -> str:
    """读（必要时生成）公钥内容。"""
    key = Path(cfg["key"])
    if not key.exists():
        if not create:
            raise Fail("还没有密钥：" + str(key) + "，先运行 python tools/pa_sync.py setup")
        key.parent.mkdir(parents=True, exist_ok=True)
        code, out = _run(["ssh-keygen", "-t", "ed25519", "-f", str(key),
                          "-N", '""', "-C", f"{cfg['user']}@pythonanywhere"], timeout=60)
        if not key.exists():
            raise Fail("生成密钥失败：" + out)
    return Path(str(key) + ".pub").read_text(encoding="utf-8").strip()


def cmd_setup(cfg: dict, args) -> int:
    banner("配置 SSH 公钥（做一次就够，之后免密同步）")
    pub = _public_key(cfg)
    key = Path(cfg["key"])
    print("注：PythonAnywhere 的 SSH 需要付费账号（help.pythonanywhere.com/pages/SSHAccess）。")
    print("    免费账号请改用「控制台粘贴」（菜单 8 / python tools/pa_sync.py keyfile）")
    print("    或 API Token 通道（--api），两者都不需要 SSH。\n")
    print("方式 A · 网页版（付费账号）")
    print("  打开账号页： https://www.pythonanywhere.com/account/")
    print("  找到「SSH keys」小节，把下面这一整行粘进去并保存（名字随便写）：\n")
    print("   " + pub + "\n")
    print("方式 B · 控制台（免费账号也能用，推荐）")
    print("  运行 python tools/pa_sync.py keyfile，把打印出来的那一行贴进 Bash 控制台。")
    print("\n粘好后运行： python tools/pa_sync.py check")
    print("提示：公钥可以公开，私钥（" + str(key) + "）不要发给任何人。")
    return 0


def cmd_keyfile(cfg: dict, args) -> int:
    """打印可以直接粘进 PythonAnywhere Bash 控制台的一行命令。"""
    pub = _public_key(cfg)
    banner("把下面这一行整行粘进 PythonAnywhere 的 Bash 控制台并回车")
    print(f"mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo '{pub}' >> ~/.ssh/authorized_keys"
          " && chmod 600 ~/.ssh/authorized_keys && echo 公钥已安装")
    print("\n装好后回到本机运行： python tools/pa_sync.py check")
    print("如果 check 仍报 Permission denied，说明你的账号是免费版（SSH 需付费）：")
    print("  改走 API 通道 —— 到 https://www.pythonanywhere.com/account/#api_token 复制 Token，")
    print("  填进 .pa_sync.json 的 token 字段，然后 python tools/pa_sync.py push --api")
    return 0


def cmd_check(cfg: dict, args) -> int:
    banner("连通性检查")
    print(f"账号　　　：{cfg['user']}")
    print(f"主机　　　：{cfg['host']}")
    print(f"远端目录　：~/{cfg['remote_dir']}")
    print(f"私钥　　　：{cfg['key']}　{'存在' if Path(cfg['key']).exists() else '不存在（将退化为密码登录）'}")
    print(f"API Token ：{'已配置' if cfg.get('token') else '未配置'}")
    sync = SSHSync(cfg)
    ok, out = sync.check()
    if not ok:
        print("\nSSH 未通过：")
        print("  " + out.replace("\n", "\n  "))
        print("\n两条路，任选一条：")
        print("  A. 装公钥： python tools/pa_sync.py keyfile")
        print("     （把打印的那一行粘进 PythonAnywhere 的 Bash 控制台；网页版在")
        print("       https://www.pythonanywhere.com/account/ 的 SSH keys 小节）")
        print("     注意：PythonAnywhere 的 SSH 只对付费账号开放。")
        print("  B. 不用 SSH：到 https://www.pythonanywhere.com/account/#api_token 复制 Token，")
        print("     填进项目根目录 .pa_sync.json 的 token 字段，然后")
        print("       python tools/pa_sync.py push --api")
        return 1
    print("\nSSH 认证通过。")
    remote = sync.listing()
    print(f"远端文件：{len(remote)} 个，共 {human(sum(remote.values()))}")
    local = local_files()
    lset, rset = set(map(str, local)), set(remote)
    newer = [r for r in sorted(lset - rset)]
    print(f"本地待同步：{len(local)} 个文件，共 {human(sum((ROOT / f).stat().st_size for f in local))}")
    print(f"  仅本地有（{len(newer)}）：" + ("、".join(newer[:8]) + ("…" if len(newer) > 8 else "")
                                          if newer else "无"))
    only_remote = sorted(rset - lset)
    print(f"  仅远端有（{len(only_remote)}）：" + ("、".join(only_remote[:8]) + ("…" if len(only_remote) > 8 else "")
                                           if only_remote else "无"))
    return 0


def cmd_diff(cfg: dict, args) -> int:
    banner("同步预览（不会修改任何文件）")
    sync = SSHSync(cfg)
    ok, out = sync.check()
    if not ok:
        raise Fail("SSH 不通，先跑 python tools/pa_sync.py check\n" + out)
    remote = sync.listing()
    rows = []
    for rel in local_files():
        size = (ROOT / rel).stat().st_size
        rsize = remote.get(str(rel).replace("\\", "/"))
        if rsize is None:
            rows.append(("新增", rel, size))
        elif rsize != size:
            rows.append(("大小不同", rel, size))
    for rel, size in sorted(remote.items()):
        if not (ROOT / rel).exists():
            rows.append(("远端多出", Path(rel), size))
    if not rows:
        print("两边文件大小一致，无需同步。")
        return 0
    for kind, rel, size in rows:
        print(f"  [{kind}] {rel}　{human(size)}")
    print(f"\n合计 {len(rows)} 处差异。执行 python tools/pa_sync.py push 同步上去。")
    return 0


def cmd_push(cfg: dict, args) -> int:
    files = local_files()
    if not files:
        raise Fail("没有找到要同步的文件")
    total = sum((ROOT / f).stat().st_size for f in files)

    if args.api:
        if not cfg.get("token"):
            raise Fail("--api 需要 API Token")
        banner(f"API 上传 {len(files)} 个文件（{human(total)}）")
        api = ApiSync(cfg)
        for i, rel in enumerate(files, 1):
            api.upload(rel)
            print(f"  [{i}/{len(files)}] {rel}")
    else:
        banner(f"SSH 上传 {len(files)} 个文件（{human(total)}）")
        sync = SSHSync(cfg)
        if not args.no_check:
            ok, out = sync.check()
            if not ok:
                raise Fail("SSH 不通，先配置公钥（python tools/pa_sync.py setup）。\n" + out)
        sync.mkdirs(files)
        # 分批 scp：一次几十个文件比逐个快得多，也避免命令行过长
        batch_size = args.batch
        for i in range(0, len(files), batch_size):
            chunk = files[i:i + batch_size]
            code, out = sync.scp([str((ROOT / f)) for f in chunk],
                                 f"{sync.target}:{sync.dir}/")
            if code != 0:
                raise Fail("scp 失败：" + out)
            print(f"  已上传 {min(i + batch_size, len(files))}/{len(files)}"
                  f"　（{chunk[0]} … {chunk[-1]}）")
        sync.stamp()
        print(f"\n完成：{len(files)} 个文件 → ~/{sync.dir}/")
        remote = sync.listing()
        print(f"远端现在有 {len(remote)} 个文件，共 {human(sum(remote.values()))}")

    if args.reload:
        banner("重新加载 Web App")
        print(reload_webapp(cfg))
    else:
        print("\n静态页（dashboard.html）刷新浏览器即可看到；")
        print("挂的是 WSGI/Flask 应用的话，运行 python tools/pa_sync.py reload（需 API Token）。")
    return 0


def cmd_pull(cfg: dict, args) -> int:
    banner("从 PythonAnywhere 拉回本地")
    sync = SSHSync(cfg)
    ok, out = sync.check()
    if not ok:
        raise Fail("SSH 不通，先跑 python tools/pa_sync.py check\n" + out)
    remote = sync.listing()
    keep = [r for r in sorted(remote)
            if not any(part in EXCLUDE_DIRS for part in Path(r).parts[:-1])
            and Path(r).suffix.lower() not in EXCLUDE_SUFFIX
            and Path(r).name not in EXCLUDE_FILES]
    print(f"远端可拉取 {len(keep)} 个文件。")
    if not args.yes:
        print("这会覆盖本地同名文件（state/、logs/、exports/ 不在范围内）。")
        ans = input("确认继续？输入 yes 回车：").strip().lower()
        if ans != "yes":
            print("已取消。")
            return 0
    for rel in keep:
        dest = ROOT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        code, out = sync.scp([f"{sync.target}:{sync.dir}/{rel}"], str(dest))
        if code != 0:
            print(f"  [失败] {rel}　{out}")
        else:
            print(f"  [拉回] {rel}")
    print("\n完成。注意：远端那份 state/completions.json 没有拉下来（打卡数据仍以本机为准）。")
    return 0


def cmd_reload(cfg: dict, args) -> int:
    banner("重新加载 Web App")
    print(reload_webapp(cfg))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pa_sync.py",
                                 description="本地 ↔ PythonAnywhere 文件同步（纯标准库）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # 所有子命令都支持 --ask：允许 ssh 交互式输入密码（默认非交互，避免脚本挂住）
    def add(name: str, help_text: str):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--ask", action="store_true",
                       help="允许 ssh 提示输入密码（默认禁止，防止脚本一直卡在提示上）")
        return p

    add("setup", "生成/显示 SSH 公钥并给出配置步骤").set_defaults(func=cmd_setup)
    add("keyfile", "打印可直接粘进 PythonAnywhere 控制台的一行命令").set_defaults(func=cmd_keyfile)
    add("check", "检查连通性、认证与远端目录").set_defaults(func=cmd_check)
    add("diff", "只看差异，不做修改").set_defaults(func=cmd_diff)
    p = add("push", "本地 → PythonAnywhere")
    p.add_argument("--api", action="store_true", help="改用 Files API（需要 token）")
    p.add_argument("--all", action="store_true", help="忽略差异，全量上传（默认行为，保留此参数兼容）")
    p.add_argument("--no-check", action="store_true", help="跳过前置连通性检查")
    p.add_argument("--batch", type=int, default=25, help="每次 scp 的文件数（默认 25）")
    p.add_argument("--reload", action="store_true", help="上传完顺手 reload Web App")
    p.set_defaults(func=cmd_push)
    p = add("pull", "PythonAnywhere → 本地")
    p.add_argument("-y", "--yes", action="store_true", help="不再确认")
    p.set_defaults(func=cmd_pull)
    add("reload", "通知 PythonAnywhere 重新加载 Web App").set_defaults(func=cmd_reload)

    args = ap.parse_args(argv)
    try:
        cfg = load_config()
        cfg["interactive"] = bool(getattr(args, "ask", False)
                                  or os.environ.get("PA_INTERACTIVE") == "1")
        return args.func(cfg, args)
    except Fail as exc:
        print("\n[错误] " + str(exc))
        return 1
    except KeyboardInterrupt:
        print("\n已中断。")
        return 130


if __name__ == "__main__":
    sys.exit(main())
