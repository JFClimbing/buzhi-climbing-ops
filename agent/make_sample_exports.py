# -*- coding: utf-8 -*-
"""把已有数据文件转成「平台导出 CSV」，方便没有导出文件时先跑通链路/做演示

用法：python make_sample_exports.py
产出：data/inbox/douyin_export_<date>.csv、data/inbox/xhs_export_<date>.csv
"""
import csv
import json
import os
import re
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.dirname(BASE)          # 仓库根（或原工作区）
REPO_DATA = os.path.join(WORKSPACE, "data")

# 优先 1) 环境变量  2) 仓库自带 data/  3) 原工作区项目
DY_DATA = os.environ.get("DY_DATA_DIR") or (
    os.path.join(REPO_DATA, "douyin") if os.path.isdir(os.path.join(REPO_DATA, "douyin"))
    else os.path.join(WORKSPACE, "zzhclimbing-content-system", "data"))
XHS_DATA = os.environ.get("XHS_DATA_DIR") or (
    os.path.join(REPO_DATA, "xiaohongshu") if os.path.isdir(os.path.join(REPO_DATA, "xiaohongshu"))
    else os.path.join(os.path.dirname(WORKSPACE), "jfclimbing-content-system", "data", "xiaohongshu"))


def newest(dir_path, prefix):
    names = sorted(n for n in os.listdir(dir_path) if n.startswith(prefix) and n.endswith(".json"))
    return os.path.join(dir_path, names[-1]) if names else None


def to_int(v):
    if v is None:
        return 0
    s = str(v).strip().replace(",", "")
    mult = 1
    if s.endswith("万"):
        mult, s = 10000, s[:-1]
    s = re.sub(r"[^\d.]", "", s)
    try:
        return int(round(float(s) * mult))
    except ValueError:
        return 0


def dy_rows():
    path = newest(DY_DATA, "dy_works_")
    with open(path, "r", encoding="utf-8") as f:
        works = json.load(f)
    rows = []
    for w in works:
        cid = w.get("id") or w.get("aweme_id") or str(abs(hash(w.get("title") or "")))[:18]
        m = w.get("metrics_all") or {}
        rows.append({
            "作品ID": cid,
            "发布时间": w.get("date") or "",
            "作品描述": w.get("title") or "",
            "作品类型": "视频" if (w.get("duration") or "").strip() else "图文",
            "播放量": m.get("播放") or 0,
            "点赞量": m.get("点赞") or 0,
            "评论量": m.get("评论") or 0,
            "收藏量": m.get("收藏") or 0,
            "分享量": m.get("分享") or 0,
            "吸粉量": m.get("吸粉量") or "",
            "作品链接": f"https://www.douyin.com/video/{cid}",
        })
    return rows, path


def xhs_rows():
    path = newest(XHS_DATA, "xhs_notes_")
    with open(path, "r", encoding="utf-8") as f:
        notes = json.load(f)
    rows = []
    for i, n in enumerate(notes):
        card = (n.get("card_text") or "").splitlines()
        pub = ""
        for line in card:
            if re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$", line.strip()):
                pub = line.strip()
                break
        nid = f"{abs(hash(n.get('title') or '')) % 10**16:016d}"
        rows.append({
            "笔记ID": nid,
            "发布时间": pub,
            "笔记标题": n.get("title") or "",
            "观看量": n.get("views") or 0,
            "点赞": n.get("likes") or 0,
            "评论": n.get("comments") or 0,
            "收藏": n.get("collects") or 0,
            "分享": n.get("shares") or 0,
            "笔记链接": f"https://www.xiaohongshu.com/explore/{nid}",
        })
    return rows, path


def write_csv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    inbox = os.path.join(BASE, "data", "inbox")
    today = datetime.now().strftime("%Y-%m-%d")

    rows, src = dy_rows()
    p1 = os.path.join(inbox, f"douyin_export_{today}.csv")
    write_csv(p1, rows)
    print(f"抖音 {len(rows)} 行 ← {os.path.basename(src)}")
    print(f"  → {p1}")

    rows, src = xhs_rows()
    p2 = os.path.join(inbox, f"xhs_export_{today}.csv")
    write_csv(p2, rows)
    print(f"小红书 {len(rows)} 行 ← {os.path.basename(src)}")
    print(f"  → {p2}")


if __name__ == "__main__":
    main()
