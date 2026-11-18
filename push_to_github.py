# -*- coding: utf-8 -*-
"""把 buzhi-climbing-ops 推到 GitHub（用 PAT，一次搞定）。

用法：
    set GH_TOKEN=ghp_xxx
    python push_to_github.py                # 默认 public
    python push_to_github.py --private      # 建私有仓库

做的事：
  1. 校验 token（GET /user）
  2. 建仓库（已存在就跳过）
  3. 配 remote 并 push（token 只在命令里用，不落盘到 .git/config）
  4. 把 remote 还原成不含 token 的地址
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GIT = r"C:\Program Files\WorkBuddy\resources\vendor\PortableGit\cmd\git.exe"
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_NAME = "buzhi-climbing-ops"


def api(path, token, method="GET", payload=None):
    url = "https://api.github.com" + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "buzhi-climbing-ops-push")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body[:400]}


def git(*args, cwd=REPO_DIR, quiet=False):
    p = subprocess.run([GIT] + list(args), cwd=cwd, capture_output=True)
    out = (p.stdout or b"").decode("utf-8", "replace").strip()
    err = (p.stderr or b"").decode("utf-8", "replace").strip()
    if not quiet:
        if out:
            print("   " + out.replace("\n", "\n   "))
        if err and p.returncode != 0:
            print("   ! " + err.replace("\n", "\n   ! "))
    return p.returncode, out, err


def main():
    private = "--private" in sys.argv
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("请先设置环境变量 GH_TOKEN（GitHub 个人访问令牌，classic，勾 repo）")
        return 2
    token = token.strip()

    print("[1/4] 校验 token …")
    code, me = api("/user", token)
    if code != 200:
        print(f"  token 无效（HTTP {code}）：{me.get('message', me)}")
        return 3
    owner = me["login"]
    print(f"  ok，账号：{owner}")

    print(f"[2/4] 建仓库 {owner}/{REPO_NAME}（{'私有' if private else '公开'}）…")
    code, repo = api("/repos/" + owner + "/" + REPO_NAME, token)
    if code == 200:
        print("  已存在，直接推")
    else:
        payload = {
            "name": REPO_NAME,
            "description": "不止攀岩 · 抖音/小红书数据采集 + 复盘 + 飞书日报 Agent（可复现）",
            "private": private,
            "has_issues": True,
            "has_wiki": False,
            "auto_init": False,
        }
        code, repo = api("/user/repos", token, "POST", payload)
        if code not in (200, 201):
            print(f"  建仓库失败（HTTP {code}）：{repo.get('message', repo)}")
            if code == 403:
                print("  提示：token 缺少 repo 权限，或账号不允许建仓库")
            return 4
        print("  建好：" + repo["html_url"])

    clone_url = repo["clone_url"]
    authed = re.sub(r"^https://", "https://x-access-token:" + token + "@", clone_url)

    print("[3/4] 推送 main …")
    git("remote", "remove", "origin", quiet=True)
    git("remote", "add", "origin", authed, quiet=True)
    code, out, err = git("-c", "credential.helper=", "push", "-u", "origin", "main")
    if code != 0:
        print("  推送失败")
        return 5
    print("  ok")

    print("[4/4] 还原 remote（去掉 token）…")
    git("remote", "set-url", "origin", clone_url)
    code, out, _ = git("remote", "-v")
    print(out)
    print("\n完成：" + repo["html_url"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
