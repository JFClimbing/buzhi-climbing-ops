# -*- coding: utf-8 -*-
"""小红书采集层：把创作服务平台导出的 CSV/JSON 变成标准「素材记录」

导出路径：小红书创作服务平台 → 数据中心 → 笔记数据 → 导出
把导出文件丢进 data/inbox/，文件名以 xhs_ 开头即可（如 xhs_export_2026-11-18.csv）
"""
import os
from datetime import datetime

from _util import find_files, pick, read_table, short, to_int, to_ts_ms

PLATFORM = "小红书"


def collect(inbox_dir, date_str=None):
    files = find_files(inbox_dir, "xhs_")
    if not files:
        raise FileNotFoundError(f"{inbox_dir} 下没有 xhs_ 开头的导出文件")

    path = files[-1]
    rows = read_table(path)
    if not rows:
        raise ValueError(f"{os.path.basename(path)} 里没有数据行")

    records, skipped = [], []
    for r in rows:
        nid = str(pick(r, "笔记ID", "笔记id", "note_id", "id", "内容ID") or "").strip()
        pub_raw = pick(r, "发布时间", "发布日期", "publish_time", "时间")
        pub_ts = to_ts_ms(pub_raw)
        if not nid:
            skipped.append(f"缺笔记ID：{str(r)[:80]}")
            continue
        if date_str and pub_ts:
            if datetime.fromtimestamp(pub_ts / 1000).strftime("%Y-%m-%d") != date_str:
                continue

        title = short(pick(r, "笔记标题", "标题", "title", "文案"))
        views = to_int(pick(r, "观看量", "阅读量", "浏览量", "views", "曝光量"))
        likes = to_int(pick(r, "点赞", "点赞量", "likes")) or 0
        collects = to_int(pick(r, "收藏", "收藏量", "collects")) or 0
        comments = to_int(pick(r, "评论", "评论量", "comments")) or 0
        shares = to_int(pick(r, "分享", "分享量", "shares", "转发")) or 0
        fans = to_int(pick(r, "涨粉", "新增粉丝", "fans_gained"))

        note = None
        zancang = to_int(pick(r, "赞藏", "赞藏数", "likes_and_collects"))
        if zancang and likes == 0 and collects == 0:
            likes = int(round(zancang * 0.75))
            collects = zancang - likes
            note = "赞藏合并估算"

        link = str(pick(r, "笔记链接", "链接", "url") or "").strip()
        if not link:
            link = f"https://www.xiaohongshu.com/explore/{nid}"

        records.append({
            "素材ID": f"xhs_{nid}",
            "内容ID": nid,
            "平台": PLATFORM,
            "发布日期": pub_ts,
            "标题/文案": title,
            "素材链接": {"link": link, "text": "小红书笔记"},
            "内容类型": str(pick(r, "笔记类型", "类型", "type") or "").strip() or None,
            "播放/浏览量": views,
            "点赞": likes,
            "评论": comments,
            "收藏": collects,
            "分享/转发": shares,
            "新增粉丝": fans,
            "互动合计": likes + comments + collects + shares,
            "数据来源": "后台导出",
            "备注": note,
        })
    return records, skipped, path
