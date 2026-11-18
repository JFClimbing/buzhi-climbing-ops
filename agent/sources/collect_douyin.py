# -*- coding: utf-8 -*-
"""抖音采集层：把创作者中心导出的 CSV/JSON 变成标准「素材记录」

导出路径：抖音创作者中心 → 数据中心 → 作品数据 → 导出（Excel/CSV）
把导出文件丢进 data/inbox/，文件名以 douyin_ 开头即可（如 douyin_export_2026-11-18.csv）
"""
import os

from _util import find_files, pick, short, to_int, to_ts_ms

PLATFORM = "抖音"


def collect(inbox_dir, date_str=None):
    """date_str: 'YYYY-MM-DD'，只取这一天发布的；None=全都要"""
    files = find_files(inbox_dir, "douyin_")
    if not files:
        raise FileNotFoundError(f"{inbox_dir} 下没有 douyin_ 开头的导出文件")

    path = files[-1]
    from _util import read_table

    rows = read_table(path)
    if not rows:
        raise ValueError(f"{os.path.basename(path)} 里没有数据行")

    records, skipped = [], []
    for r in rows:
        cid = str(pick(r, "作品ID", "视频ID", "aweme_id", "id", "内容ID") or "").strip()
        pub_raw = pick(r, "发布时间", "发布日期", "publish_time", "create_time", "时间")
        pub_ts = to_ts_ms(pub_raw)
        if not cid:
            skipped.append(f"缺作品ID：{str(r)[:80]}")
            continue
        if date_str and pub_ts:
            from datetime import datetime

            if datetime.fromtimestamp(pub_ts / 1000).strftime("%Y-%m-%d") != date_str:
                continue

        title = short(pick(r, "作品描述", "标题", "desc", "title", "文案"))
        plays = to_int(pick(r, "播放量", "播放", "play_count", "views"))
        likes = to_int(pick(r, "点赞量", "点赞", "digg_count", "likes")) or 0
        comments = to_int(pick(r, "评论量", "评论", "comment_count", "comments")) or 0
        collects = to_int(pick(r, "收藏量", "收藏", "collect_count", "collects")) or 0
        shares = to_int(pick(r, "分享量", "分享", "share_count", "shares")) or 0
        fans = to_int(pick(r, "吸粉量", "新增粉丝", "fans_gained", "涨粉"))
        ctype = str(pick(r, "作品类型", "类型", "type") or "").strip() or None
        link = str(pick(r, "作品链接", "链接", "url", "share_url") or "").strip()
        if not link:
            link = f"https://www.douyin.com/video/{cid}"

        records.append({
            "素材ID": f"douyin_{cid}",
            "内容ID": cid,
            "平台": PLATFORM,
            "发布日期": pub_ts,
            "标题/文案": title,
            "素材链接": {"link": link, "text": "抖音作品"},
            "内容类型": ctype if ctype in ("视频", "图文") else None,
            "播放/浏览量": plays,
            "点赞": likes,
            "评论": comments,
            "收藏": collects,
            "分享/转发": shares,
            "新增粉丝": fans,
            "互动合计": likes + comments + collects + shares,
            "数据来源": "后台导出",
        })
    return records, skipped, path
