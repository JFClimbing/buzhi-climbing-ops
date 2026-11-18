# -*- coding: utf-8 -*-
"""
小红书创作者中心 —— 登录 / 抓数

用法：
  # 1) 登录（弹出 Edge 窗口，扫码或短信登录）
  python xhs_login.py --login-only

  # 2) 抓笔记列表（登录态已存在时）
  python xhs_login.py

  # 3) 无头抓数（确认登录态可用之后）
  python xhs_login.py --headless

登录态目录：<repo>/.auth-xhs   （等同账号密码：不复制、不上传、不提交）
"""
import argparse
import datetime as dt
import io
import json
import os
import re
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROFILE = os.path.join(ROOT, ".auth-xhs")
DATA = os.path.join(ROOT, "data", "xiaohongshu")
LOGIN_URL = "https://creator.xiaohongshu.com/login"
MANAGER_URL = "https://creator.xiaohongshu.com/new/note-manager"

# 小红书登录态 cookie（出现其一即视为已登录）
SESSION_COOKIES = ("web_session", "web_session_fe", "access-token-creator.xiaohongshu.com", "gid")


def logged_in(ctx, page):
    """先看 cookie，再看 URL。"""
    try:
        names = {c.get("name") for c in ctx.cookies()}
        if any(n in names for n in ("web_session", "web_session_fe")):
            return True
    except Exception:
        pass
    u = page.url
    return ("/login" not in u) and ("xiaohongshu.com" in u)


def wait_login(ctx, page, timeout=1800):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        if page.url != last:
            print("  url:", page.url, flush=True)
            last = page.url
        if logged_in(ctx, page):
            time.sleep(3)
            if logged_in(ctx, page):
                return True
        time.sleep(2)
    return False


NUM = re.compile(r"[\d,]+(?:\.\d+)?")


def _num(s):
    m = NUM.search(s or "")
    if not m:
        return None
    try:
        return int(float(m.group(0).replace(",", "")))
    except Exception:
        return None


def scrape(page, rounds=60):
    """滚到底，按 note-card 结构解析。"""
    try:
        page.wait_for_selector("div.note-card", timeout=30000)
    except Exception:
        print("  ⚠️ 没等到 div.note-card", flush=True)
        return []

    notes, seen = [], set()
    for i in range(rounds):
        for card in page.query_selector_all("div.note-card"):
            try:
                title_el = card.query_selector(".note-card__title")
                title = (title_el.inner_text() if title_el else card.inner_text()).strip()
                title = title.split("\n")[0].strip()
                if not title or title in seen:
                    continue
                seen.add(title)
                stat_txt = ""
                stats = card.query_selector_all(".note-card__stat")
                vals = []
                for st in stats:
                    t = (st.inner_text() or "").strip()
                    stat_txt += " " + t
                    vals.append(_num(t))
                while len(vals) < 5:
                    vals.append(None)
                notes.append({
                    "title": title,
                    "views": vals[0], "comments": vals[1], "likes": vals[2],
                    "collects": vals[3], "shares": vals[4],
                    "stats_raw": stat_txt.strip(),
                    "card_text": (card.inner_text() or "").strip(),
                })
            except Exception as e:
                print("  card err:", e, flush=True)
        try:
            page.eval_on_selector("div.content", "el => el.scrollTop = el.scrollHeight")
        except Exception:
            page.mouse.wheel(0, 1400)
        time.sleep(1.3)
        if i % 5 == 0:
            print("  scroll %d -> %d notes" % (i, len(notes)), flush=True)
    return notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--login-only", action="store_true")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args()

    os.makedirs(DATA, exist_ok=True)
    os.makedirs(PROFILE, exist_ok=True)

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            PROFILE, channel="msedge", headless=args.headless,
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(LOGIN_URL if args.login_only else MANAGER_URL,
                  wait_until="domcontentloaded", timeout=60000)
        time.sleep(4)

        if not logged_in(ctx, page):
            print("👉 请在打开的 Edge 窗口里登录小红书（扫码或短信）", flush=True)
            print("   登录完成后什么都不用做，脚本会自己继续。", flush=True)
            if not wait_login(ctx, page, args.timeout):
                print("❌ 等待登录超时（%d 秒）" % args.timeout, flush=True)
                ctx.close()
                return 1
            print("✅ 已登录:", page.url, flush=True)
        else:
            print("✅ 登录态可用:", page.url, flush=True)

        if args.login_only:
            print("--login-only：登录态已存到", PROFILE, flush=True)
            ctx.close()
            return 0

        page.goto(MANAGER_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(6)
        print("列表页:", page.url, flush=True)

        notes = scrape(page)
        today = dt.date.today().isoformat()
        out = os.path.join(DATA, "xhs_notes_%s.json" % today)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(notes, f, ensure_ascii=False, indent=1)
        print("OK %s  notes=%d" % (out, len(notes)), flush=True)

        png = os.path.join(DATA, "xhs_manager_%s.png" % today)
        try:
            page.screenshot(path=png)
            print("截图:", png, flush=True)
        except Exception:
            pass
        ctx.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
