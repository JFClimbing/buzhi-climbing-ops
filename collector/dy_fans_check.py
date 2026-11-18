#!/usr/bin/env python3
"""抖音粉丝数交叉校验 —— 主页 + 创作者中心数据概览/粉丝数据

用途：作品管理列表里的「吸粉量」对新片有延迟（可能显示 0），
必须用「主页粉丝总数」与「创作者中心粉丝净增」双向核对，防止单一口径误判。

用法:
  python tools/dy_fans_check.py           # 抓三处数据 + 存 JSON
  python tools/dy_fans_check.py --dump    # 额外打印页面文本片段（诊断）

输出:
  data/dy_fans_check_<YYYYMMDD>.json
"""
import json
import os
import re
import sys
import time
import datetime

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("❌ 缺少 playwright")
    sys.exit(1)

CHANNEL = os.environ.get("DSH_BROWSER_CHANNEL") or (
    "msedge" if os.name == "nt" else "chrome")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
USER_DATA = os.path.join(ROOT, ".auth-edge")
os.makedirs(DATA, exist_ok=True)

PROFILE_URL = "https://www.douyin.com/user/self"
OVERVIEW_URL = "https://creator.douyin.com/creator-micro/data-center/overview"
FANS_URL = "https://creator.douyin.com/creator-micro/data-center/fans"


def launch(pw):
    return pw.chromium.launch_persistent_context(
        USER_DATA, channel=CHANNEL, headless=False,
        viewport=None, args=["--start-maximized"],
    )


def norm(t):
    return re.sub(r"[ \t\r\n\u00a0]+", "", t or "")


def to_num(s):
    if s is None:
        return None
    s = s.strip()
    m = re.match(r"^([\d.]+)万$", s)
    if m:
        return int(round(float(m.group(1)) * 10000))
    m = re.match(r"^([\d.]+)亿$", s)
    if m:
        return int(round(float(m.group(1)) * 100000000))
    m = re.match(r"^(\d+)$", s)
    if m:
        return int(m.group(1))
    return None


def parse_profile_stats(page):
    """主页统计：排版是「关注5粉丝265获赞815」，数字在标签后。"""
    txt = norm(page.inner_text("body"))
    out = {}
    for label, key in (("关注", "following"), ("粉丝", "fans"), ("获赞", "likes")):
        m = re.search(label + r"(\d+(?:\.\d+)?[万亿]?)", txt)
        if m:
            out[key] = m.group(1)
            out[key + "_num"] = to_num(m.group(1))
    m = re.search(r"抖音号[:：]([\w.\-]+)", txt)
    if m:
        out["douyin_id"] = m.group(1)
    out["_raw_len"] = len(txt)
    out["_head"] = txt[:300]
    return out


def grab_text(page, url, wait_ms=6000):
    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    time.sleep(wait_ms / 1000.0)
    for _ in range(3):
        try:
            page.mouse.wheel(0, 400)
            time.sleep(1.0)
        except Exception:
            break
    return norm(page.inner_text("body"))


def pick_fans_facts(txt):
    """从长文本里挑出和粉丝数/涨粉相关的片段。"""
    facts = {}
    pats = [
        ("粉丝总数", r"粉丝总数[:：]?([\d.]+[万亿]?)"),
        ("总粉丝量", r"总粉丝量[:：]?([\d.]+[万亿]?)"),
        ("粉丝净增", r"粉丝净增[:：]?([+\-]?[\d.]+[万亿]?)"),
        ("净增粉丝", r"净增粉丝(?:数|量)?[:：]?([+\-]?[\d.]+[万亿]?)"),
        ("新增粉丝", r"新增粉丝(?:数|量)?[:：]?([+\-]?[\d.]+[万亿]?)"),
        ("涨粉", r"涨粉(?:数|量)?[:：]?([+\-]?[\d.]+[万亿]?)"),
        ("掉粉", r"掉粉(?:数|量)?[:：]?([+\-]?[\d.]+[万亿]?)"),
    ]
    for name, pat in pats:
        m = re.search(pat, txt)
        if m:
            facts[name] = m.group(1)
    # 7 日/30 日窗口的「粉丝净增」
    for win in ("7日", "30日", "近7天", "近30天"):
        m = re.search(win + r"[^。]{0,40}?粉丝[^。]{0,20}?([+\-]?\d+(?:\.\d+)?[万亿]?)", txt)
        if m:
            facts["window_" + win] = m.group(1)
    return facts


def main():
    dump = "--dump" in sys.argv
    result = {
        "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "profile": {},
        "overview": {},
        "fans_page": {},
    }
    with sync_playwright() as pw:
        ctx = launch(pw)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.set_default_timeout(60000)

        print("① 主页 https://www.douyin.com/user/self")
        page.goto(PROFILE_URL, wait_until="domcontentloaded", timeout=90000)
        time.sleep(6)
        prof = parse_profile_stats(page)
        result["profile"] = prof
        print("   主页统计:", {k: v for k, v in prof.items() if not k.startswith("_")})

        print("② 创作者中心 · 数据概览")
        txt_ov = grab_text(page, OVERVIEW_URL, 8000)
        result["overview"] = pick_fans_facts(txt_ov)
        if dump:
            print("   [overview 片段]", txt_ov[:1200])
        print("   粉丝相关:", result["overview"])

        print("③ 创作者中心 · 粉丝数据")
        txt_fans = grab_text(page, FANS_URL, 8000)
        result["fans_page"] = pick_fans_facts(txt_fans)
        if dump:
            print("   [fans 片段]", txt_fans[:1500])
        print("   粉丝相关:", result["fans_page"])

        # 兜底：把两个数据页面的正文片段也存下来，便于人工复核
        result["overview_text_head"] = txt_ov[:2000]
        result["fans_text_head"] = txt_fans[:2000]

        ctx.close()

    out = os.path.join(DATA, "dy_fans_check_%s.json" %
                       datetime.date.today().strftime("%Y%m%d"))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print("💾 已写", out)


if __name__ == "__main__":
    main()
