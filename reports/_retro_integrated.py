# -*- coding: utf-8 -*-
"""全量整合复盘：抖音 18 条 + 小红书 18 篇 → 指标底稿 JSON/Markdown"""
import json
import os
import re
import statistics as st
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WS = r"C:\Users\JF\Desktop\运营\工作室运营"
DY_PATH = os.path.join(WS, r"zzhclimbing-content-system\data\dy_works_2026-11-18.json")
DY_FANS = os.path.join(WS, r"zzhclimbing-content-system\data\dy_fans_check_20261118.json")
XHS_ROOT = os.path.join(os.path.dirname(WS), "jfclimbing-content-system", "data", "xiaohongshu")
XHS_PATH = os.path.join(XHS_ROOT, "xhs_notes_2026-11-18.json")
XHS_OLD = os.path.join(XHS_ROOT, "xhs_notes_2026-10-13.json")
OUT_MD = os.path.join(WS, "复盘_全量整合_2026-11-18_底稿.md")
OUT_JSON = os.path.join(WS, "复盘_全量整合_2026-11-18.json")

TODAY = datetime(2026, 11, 18)


def num(v):
    if v is None:
        return 0
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip().replace(",", "")
    if s in ("", "-", "—", "暂无"):
        return 0
    m = re.match(r"^([\d.]+)\s*(万|w|W)?$", s)
    if not m:
        return 0
    x = float(m.group(1))
    if m.group(2):
        x *= 10000
    return int(round(x))


def pct(v):
    if v in (None, "", "-", "—"):
        return None
    s = str(v).strip().rstrip("%")
    try:
        return float(s) / 100.0
    except ValueError:
        return None


def dur_sec(s):
    if not s:
        return None
    parts = str(s).strip().split(":")
    try:
        parts = [int(p) for p in parts]
    except ValueError:
        return None
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return None


def dstr(s):
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", str(s or ""))
    if not m:
        return None
    return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))


TOPICS = [
    ("保护器", ["保护器", "atc", "grigri", "gri gri", "管式", "龟龟", "smart", "jul", "辅助"]),
    ("主锁", ["主锁", "锁门", "d型", "h型", "o型", "梨形"]),
    ("快挂", ["快挂", "慢挂", "快挂长短"]),
    ("绳与绳结", ["绳", "结", "绳结", "裁绳", "动力绳"]),
    ("装备选购", ["装备", "买", "选", "推荐", "贵", "扁带", "头盔", "鞋"]),
    ("结组多段", ["结组", "多段", "领攀", "先锋", "顶绳", "建站", "保护站"]),
    ("训练与知识", ["训练", "教程", "技巧", "为什么", "原理"]),
]


def topic_of(title):
    t = title.lower()
    for name, kws in TOPICS:
        for k in kws:
            if k in t:
                return name
    return "其他"


def main():
    dy = json.load(open(DY_PATH, encoding="utf-8"))
    xhs = json.load(open(XHS_PATH, encoding="utf-8"))
    fans = json.load(open(DY_FANS, encoding="utf-8")) if os.path.exists(DY_FANS) else {}

    # ---------- 抖音 ----------
    d_items = []
    for it in dy:
        if it.get("status") != "published":
            continue
        m = it.get("metrics_all") or {}
        r = it.get("raw") or {}
        plays = num(m.get("播放") or r.get("播放"))
        d_items.append({
            "title": (it.get("title") or "").split("#")[0].strip(),
            "full_title": it.get("title") or "",
            "date": dstr(it.get("date")),
            "plays": plays,
            "likes": num(m.get("点赞") or r.get("点赞")),
            "comments": num(m.get("评论") or r.get("评论")),
            "shares": num(m.get("分享") or r.get("分享")),
            "collects": num(m.get("收藏") or r.get("收藏")),
            "follows": num(m.get("吸粉量") or r.get("吸粉量")),
            "skip": pct(m.get("划走率")),
            "expand": pct(m.get("文案展开率")),
            "avg_images": num(m.get("平均浏览图片数")),
            "dur": dur_sec(it.get("duration")),
            "is_image": not it.get("images"),
            "topic": topic_of(it.get("title") or ""),
            "pinned": bool(it.get("pinned")),
        })
    d_items = [x for x in d_items if x["date"] and x["date"] <= TODAY]
    d_items.sort(key=lambda x: x["date"])

    # ---------- 小红书 ----------
    x_items = []
    for it in xhs:
        title = (it.get("title") or "").strip()
        card = it.get("card_text") or ""
        date = dstr(card)
        v = num(it.get("views"))
        x_items.append({
            "title": title,
            "date": date,
            "views": v,
            "likes": num(it.get("likes")),
            "comments": num(it.get("comments")),
            "collects": num(it.get("collects")),
            "shares": num(it.get("shares")),
            "topic": topic_of(title),
        })
    x_items = [x for x in x_items if x["date"] and x["date"] <= TODAY]
    x_items.sort(key=lambda x: x["date"])

    def agg(items, key):
        return sum(i[key] for i in items)

    def summary(items, play_key):
        n = len(items)
        plays = [i[play_key] for i in items]
        out = {
            "count": n,
            "views": sum(plays),
            "likes": agg(items, "likes"),
            "comments": agg(items, "comments"),
            "collects": agg(items, "collects"),
            "shares": agg(items, "shares"),
            "median_views": int(st.median(plays)) if plays else 0,
            "mean_views": int(sum(plays) / n) if n else 0,
            "max_views": max(plays) if plays else 0,
            "min_views": min(plays) if plays else 0,
            "like_rate": round(agg(items, "likes") / sum(plays), 4) if sum(plays) else 0,
            "collect_rate": round(agg(items, "collects") / sum(plays), 4) if sum(plays) else 0,
            "comment_rate": round(agg(items, "comments") / sum(plays), 4) if sum(plays) else 0,
            "share_rate": round(agg(items, "shares") / sum(plays), 4) if sum(plays) else 0,
            "first": items[0]["date"].strftime("%Y-%m-%d"),
            "last": items[-1]["date"].strftime("%Y-%m-%d"),
            "span_days": (items[-1]["date"] - items[0]["date"]).days + 1,
        }
        gaps = [(items[i + 1]["date"] - items[i]["date"]).days for i in range(len(items) - 1)]
        out["cadence_median"] = int(st.median(gaps)) if gaps else None
        out["cadence_mean"] = round(sum(gaps) / len(gaps), 1) if gaps else None
        return out

    d_sum = summary(d_items, "plays")
    x_sum = summary(x_items, "views")
    d_sum["follows"] = agg(d_items, "follows")
    d_sum["follow_per_10k"] = round(d_sum["follows"] / (d_sum["views"] or 1) * 10000, 1)
    d_sum["interactions"] = d_sum["likes"] + d_sum["comments"] + d_sum["shares"] + d_sum["collects"]

    # 时长分档（仅抖音视频）
    buckets = [("≤2 分钟", 0, 120), ("2–3.5 分钟", 120, 210), ("3.5–5 分钟", 210, 300), (">5 分钟", 300, 99999)]
    dur_stats = []
    for name, lo, hi in buckets:
        sub = [i for i in d_items if i["dur"] is not None and lo <= i["dur"] < hi]
        if not sub:
            dur_stats.append({"bucket": name, "n": 0})
            continue
        dur_stats.append({
            "bucket": name,
            "n": len(sub),
            "mean_plays": int(sum(i["plays"] for i in sub) / len(sub)),
            "median_plays": int(st.median([i["plays"] for i in sub])),
            "mean_follows": round(sum(i["follows"] for i in sub) / len(sub), 1),
            "mean_like_rate": round(sum(i["likes"] for i in sub) / max(1, sum(i["plays"] for i in sub)), 4),
        })

    # 题材聚合
    def by_topic(items, play_key, follow_key=None):
        rows = []
        for name, _ in TOPICS + [("其他", [])]:
            sub = [i for i in items if i["topic"] == name]
            if not sub:
                continue
            row = {
                "topic": name,
                "n": len(sub),
                "views": sum(i[play_key] for i in sub),
                "mean_views": int(sum(i[play_key] for i in sub) / len(sub)),
            }
            if follow_key:
                row["follows"] = sum(i[follow_key] for i in sub)
                row["per_10k"] = round(row["follows"] / max(1, row["views"]) * 10000, 1)
            rows.append(row)
        rows.sort(key=lambda r: -r["views"])
        return rows

    d_topic = by_topic(d_items, "plays", "follows")
    x_topic = by_topic(x_items, "views")

    # 同题材跨平台对比（按题材名 join）
    cross = []
    for dt in d_topic:
        xt = next((t for t in x_topic if t["topic"] == dt["topic"]), None)
        if not xt:
            continue
        cross.append({
            "topic": dt["topic"],
            "douyin_n": dt["n"], "douyin_mean": dt["mean_views"],
            "xhs_n": xt["n"], "xhs_mean": xt["mean_views"],
            "ratio": round(xt["mean_views"] / dt["mean_views"], 2) if dt["mean_views"] else None,
        })

    # 最近一条（各平台）
    latest = {"douyin": None, "xiaohongshu": None}
    if d_items:
        li = d_items[-1]
        peers = [i for i in d_items if i["duration_peer"]] if False else [i for i in d_items if abs((i["dur"] or 0) - (li["dur"] or 0)) <= 60 and i is not li]
        latest["douyin"] = {
            **{k: (v.strftime("%Y-%m-%d") if isinstance(v, datetime) else v) for k, v in li.items()},
            "days_since": (TODAY - li["date"]).days,
            "vs_platform_mean": round(li["plays"] / d_sum["mean_views"], 2) if d_sum["mean_views"] else None,
            "vs_topic_mean": next((round(li["plays"] / t["mean_views"], 2) for t in d_topic if t["topic"] == li["topic"]), None),
            "peers_same_duration": len(peers),
        }
    if x_items:
        li = x_items[-1]
        latest["xiaohongshu"] = {
            **{k: (v.strftime("%Y-%m-%d") if isinstance(v, datetime) else v) for k, v in li.items()},
            "days_since": (TODAY - li["date"]).days,
            "vs_platform_mean": round(li["views"] / x_sum["mean_views"], 2) if x_sum["mean_views"] else None,
            "vs_topic_mean": next((round(li["views"] / t["mean_views"], 2) for t in x_topic if t["topic"] == li["topic"]), None),
        }

    # 榜单
    d_rank = sorted(d_items, key=lambda x: -x["plays"])
    x_rank = sorted(x_items, key=lambda x: -x["views"])

    # 图文 vs 视频（抖音）
    imgs = [i for i in d_items if i["is_image"]]
    vids = [i for i in d_items if not i["is_image"]]
    fmt_stats = {
        "image": {"n": len(imgs), "mean_plays": int(sum(i["plays"] for i in imgs) / len(imgs)) if imgs else 0,
                  "mean_follows": round(sum(i["follows"] for i in imgs) / len(imgs), 1) if imgs else 0},
        "video": {"n": len(vids), "mean_plays": int(sum(i["plays"] for i in vids) / len(vids)) if vids else 0,
                  "mean_follows": round(sum(i["follows"] for i in vids) / len(vids), 1) if vids else 0},
    }

    # 周趋势（抖音，按 ISO 周）
    weekly = {}
    for i in d_items:
        key = i["date"].strftime("%G-W%V")
        weekly.setdefault(key, {"week": key, "n": 0, "plays": 0, "follows": 0, "likes": 0})
        weekly[key]["n"] += 1
        weekly[key]["plays"] += i["plays"]
        weekly[key]["follows"] += i["follows"]
        weekly[key]["likes"] += i["likes"]
    weekly = sorted(weekly.values(), key=lambda x: x["week"])
    for w in weekly:
        w["mean_plays"] = int(w["plays"] / w["n"]) if w["n"] else 0

    # 老号（骄峰个人号）参考
    old_ref = None
    if os.path.exists(XHS_OLD):
        old = json.load(open(XHS_OLD, encoding="utf-8"))
        ov = [num(x.get("views")) for x in old]
        old_ref = {
            "count": len(old), "views": sum(ov),
            "likes": sum(num(x.get("likes")) for x in old),
            "collects": sum(num(x.get("collects")) for x in old),
            "comments": sum(num(x.get("comments")) for x in old),
            "shares": sum(num(x.get("shares")) for x in old),
            "mean_views": int(sum(ov) / len(ov)) if ov else 0,
            "median_views": int(st.median(ov)) if ov else 0,
            "account": "骄峰（个人号，旧）",
        }

    data = {
        "format_stats": fmt_stats,
        "weekly": weekly,
        "xhs_old_account": old_ref,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "today": TODAY.strftime("%Y-%m-%d"),
        "douyin": {"summary": d_sum, "fans": fans, "duration_buckets": dur_stats, "topics": d_topic},
        "xiaohongshu": {"summary": x_sum, "topics": x_topic},
        "cross_platform": cross,
        "latest": latest,
        "rank": {"douyin": d_rank, "xiaohongshu": x_rank},
        "items": {"douyin": d_items, "xiaohongshu": x_items},
    }
    json.dump(data, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)

    # ---------- 打印 ----------
    print("=" * 70)
    print(f"抖音 {d_sum['count']} 条 | {d_sum['first']} ~ {d_sum['last']} | 播放 {d_sum['views']:,} | 赞 {d_sum['likes']:,} | 藏 {d_sum['collects']:,} | 吸粉 {d_sum['follows']:,}")
    print(f"   均值 {d_sum['mean_views']:,} / 中位 {d_sum['median_views']:,} | 赞播比 {d_sum['like_rate']*100:.2f}% | 收藏率 {d_sum['collect_rate']*100:.2f}% | 每万播放吸粉 {d_sum['follow_per_10k']}")
    print(f"   发布节奏：中位 {d_sum['cadence_median']} 天 / 均值 {d_sum['cadence_mean']} 天")
    print(f"小红书 {x_sum['count']} 篇 | {x_sum['first']} ~ {x_sum['last']} | 观看 {x_sum['views']:,} | 赞 {x_sum['likes']:,} | 藏 {x_sum['collects']:,}")
    print(f"   均值 {x_sum['mean_views']:,} / 中位 {x_sum['median_views']:,} | 赞看比 {x_sum['like_rate']*100:.2f}% | 藏看比 {x_sum['collect_rate']*100:.2f}%")
    print(f"   发布节奏：中位 {x_sum['cadence_median']} 天 / 均值 {x_sum['cadence_mean']} 天")

    print("\n--- 抖音时长分档 ---")
    for b in dur_stats:
        if b["n"]:
            print(f"  {b['bucket']:<12} n={b['n']:<2} 均播 {b['mean_plays']:>7,} 中位 {b['median_plays']:>7,} 均吸粉 {b['mean_follows']:>5}")
        else:
            print(f"  {b['bucket']:<12} n=0")

    print("\n--- 抖音题材 ---")
    for t in d_topic:
        print(f"  {t['topic']:<8} n={t['n']:<2} 总播 {t['views']:>8,} 均播 {t['mean_views']:>7,} 吸粉 {t.get('follows',0):>4} 每万 {t.get('per_10k','-')}")

    print("\n--- 小红书题材 ---")
    for t in x_topic:
        print(f"  {t['topic']:<8} n={t['n']:<2} 总看 {t['views']:>8,} 均 {t['mean_views']:>7,}")

    print("\n--- 同题材跨平台（小红书均观看 / 抖音均播放） ---")
    for c in cross:
        print(f"  {c['topic']:<8} 抖 {c['douyin_n']} 条均 {c['douyin_mean']:>7,} | 红 {c['xhs_n']} 条均 {c['xhs_mean']:>7,} | 比值 {c['ratio']}")

    print("\n--- 抖音 TOP8 ---")
    for i in d_rank[:8]:
        print(f"  {i['date'].strftime('%m-%d')} {i['topic']:<8} {i['plays']:>7,}播 赞{i['likes']:>4} 藏{i['collects']:>3} 粉{i['follows']:>3} | {i['title'][:26]}")

    print("\n--- 小红书 TOP8 ---")
    for i in x_rank[:8]:
        print(f"  {i['date'].strftime('%m-%d')} {i['topic']:<8} {i['views']:>7,}看 赞{i['likes']:>4} 藏{i['collects']:>3} | {i['title'][:26]}")

    print("\n--- 图文 vs 视频（抖音） ---")
    print(f"  图文 n={fmt_stats['image']['n']} 均播 {fmt_stats['image']['mean_plays']:,} 均吸粉 {fmt_stats['image']['mean_follows']}")
    print(f"  视频 n={fmt_stats['video']['n']} 均播 {fmt_stats['video']['mean_plays']:,} 均吸粉 {fmt_stats['video']['mean_follows']}")

    print("\n--- 周趋势（抖音） ---")
    for w in weekly:
        print(f"  {w['week']} n={w['n']} 总播 {w['plays']:>7,} 均播 {w['mean_plays']:>7,} 吸粉 {w['follows']:>4}")

    if old_ref:
        print("\n--- 老号参考（骄峰个人号 / 10-13 快照） ---")
        print(f"  {old_ref['count']} 篇 观看 {old_ref['views']:,} 均 {old_ref['mean_views']:,} 中位 {old_ref['median_views']:,} 赞 {old_ref['likes']:,} 藏 {old_ref['collects']:,}")

    print("\n--- 最近一条 ---")
    for k, v in latest.items():
        print(f"  [{k}] {v['date']} {v['title'][:30]} | 视/播 {v.get('plays', v.get('views')):,} | 距今天 {v['days_since']} 天 | 平台均值倍数 {v['vs_platform_mean']} | 同题材倍数 {v['vs_topic_mean']}")

    print(f"\n底稿：{OUT_JSON}")


if __name__ == "__main__":
    main()
