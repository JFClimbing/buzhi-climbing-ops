# -*- coding: utf-8 -*-
"""每天跑一次：采集 → 汇总 → 日报小结 → 写飞书多维表格

用法：
  python daily_job.py --dry-run                 # 不连飞书，只打印+落盘 dryrun/
  python daily_job.py                           # 真写飞书（需要 config.json 填好）
  python daily_job.py --date 2026-11-17         # 指定汇总哪一天
  python daily_job.py --inbox other/inbox       # 临时换导出目录

退出码：0 全部成功；2 部分成功；1 全失败
"""
import argparse
import json
import os
import sys
import traceback
from datetime import date, datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "sources"))

from feishu import Feishu, FeishuError
from sources._util import short  # noqa: E402

FORBIDDEN_EMPTY = (None, "")


# ----------------------------------------------------------------- 配置
def load_config():
    path = os.path.join(BASE, "config.json")
    if not os.path.exists(path):
        print("⚠️  没有 config.json，先用 config.example.json（飞书那步会失败，只适合 --dry-run 测试）")
        print("   要真正写入飞书：复制 config.example.json 为 config.json，填 app_id/app_secret/app_token/table_*")
        path = os.path.join(BASE, "config.example.json")
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["_path"] = path
    return cfg


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line)
    logs_dir = os.path.join(BASE, "data", "logs")
    os.makedirs(logs_dir, exist_ok=True)
    with open(os.path.join(logs_dir, datetime.now().strftime("%Y-%m-%d") + ".log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def clean_fields(d):
    """去掉 None / 空串，飞书不喜欢空值"""
    out = {}
    for k, v in d.items():
        if v in FORBIDDEN_EMPTY or (isinstance(v, str) and not v.strip()):
            continue
        out[k] = v
    return out


def load_manual(day):
    path = os.path.join(BASE, "data", "manual", f"{day}.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_state():
    path = os.path.join(BASE, "data", "state", "seen.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"material_ids": []}


def save_state(st):
    d = os.path.join(BASE, "data", "state")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "seen.json"), "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)


# ----------------------------------------------------------------- 日报小结
def build_summary(items, manual, accounts):
    """规则模板生成「每日小结」，不依赖任何外部 AI 服务"""
    n = len(items)
    if n == 0:
        return (
            "今天没有新发布素材。"
            "建议：保持每周 2–3 条节奏，下一条优先做「新手第一次来怎么爬」这类低门槛选题，"
            "结尾挂体验课（3 小时 ¥368 / 全天 ¥718）。"
        )

    dy = [i for i in items if i["平台"] == "抖音"]
    xhs = [i for i in items if i["平台"] == "小红书"]
    views = sum(i.get("播放/浏览量") or 0 for i in items)
    likes = sum(i.get("点赞") or 0 for i in items)
    collects = sum(i.get("收藏") or 0 for i in items)
    comments = sum(i.get("评论") or 0 for i in items)
    shares = sum(i.get("分享/转发") or 0 for i in items)
    fans = sum(i.get("新增粉丝") or 0 for i in items)
    interact = likes + comments + collects + shares

    best = max(items, key=lambda x: (x.get("播放/浏览量") or 0))
    best_views = best.get("播放/浏览量") or 0

    parts = [
        f"今日发布 {n} 条素材（抖音 {len(dy)}、小红书 {len(xhs)}）。",
        f"表现最好的是《{short(best.get('标题/文案') or '未命名', 18)}》，"
        f"曝光 {best_views:,}、赞 {best.get('点赞') or 0}、藏 {best.get('收藏') or 0}。",
        f"两平台合计曝光 {views:,}、互动 {interact}、新增粉丝 {fans if fans else '—'}。",
    ]

    pm = manual.get("私信咨询数")
    src = manual.get("咨询来源") or []
    intent = manual.get("报名意向人数")
    if pm is not None or intent is not None:
        parts.append(
            f"咨询线索：私信 {pm if pm is not None else '—'} 条"
            f"（来源 {'/'.join(src) if src else '未填'}），报名意向 {intent if intent is not None else '—'} 人。"
        )
    else:
        parts.append("咨询线索：今天还没填（私信数/报名意向需人工补录）。")

    tips = []
    if views and likes / max(views, 1) < 0.01:
        tips.append("赞播比低于 1%，优先改封面和开头 3 秒（结论前置）")
    if views and collects / max(views, 1) > 0.015:
        tips.append("收藏率不错，说明是「可存档」的干货，可以做成系列")
    if views > 5000 and (pm in (None, 0)):
        tips.append(f"曝光 {views:,} 但没咨询记录，置顶评论挂「体验课 ¥368」并引导私信")
    if dy and xhs:
        dv = sum(i.get("播放/浏览量") or 0 for i in dy)
        xv = sum(i.get("播放/浏览量") or 0 for i in xhs)
        if dv > xv * 3:
            tips.append("抖音曝光远高于小红书，小红书那条可换更吸引人的首图再发一次")
        elif xv > dv * 3:
            tips.append("小红书跑得比抖音好，把小红书那篇改成口播版再发抖音")
    if not tips:
        tips.append("保持当前选题方向，下一条继续做「装备怎么选」类教程，结尾引导体验课")
    parts.append("建议：" + "；".join(tips[:3]) + "。")
    return "".join(parts)


# ----------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="汇总哪一天，默认按 config 的 report_date_offset")
    ap.add_argument("--dry-run", action="store_true", help="不连飞书，只落盘")
    ap.add_argument("--inbox", help="导出文件目录，默认 data/inbox")
    args = ap.parse_args()

    cfg = load_config()
    offset = int(cfg.get("job", {}).get("report_date_offset", 1))
    day = args.date or (date.today() - timedelta(days=offset)).isoformat()
    inbox = args.inbox or os.path.join(BASE, cfg["source"].get("inbox_dir", "data/inbox"))
    if not os.path.isabs(inbox):
        inbox = os.path.join(BASE, inbox)

    log("=" * 60)
    log(f"开始跑：{day}（dry_run={args.dry_run}，inbox={inbox}）")

    import collect_douyin
    import collect_xhs

    feishu = Feishu(cfg, dry_run=args.dry_run, base_dir=BASE, log=log)
    st = load_state()
    manual = load_manual(day)

    errors, items, sources = [], [], []
    for name, mod in (("抖音", collect_douyin), ("小红书", collect_xhs)):
        try:
            recs, skipped, path = mod.collect(inbox, date_str=day)
            log(f"  {name}：解析 {len(recs)} 条（{os.path.basename(path)}），跳过 {len(skipped)}")
            for s in skipped[:5]:
                log(f"    · 跳过：{s}")
            for r in recs:
                if r["素材ID"] in st["material_ids"]:
                    continue
                items.append(r)
            sources.append(f"{name}:{os.path.basename(path)}")
        except FileNotFoundError as e:
            errors.append(f"{name} 无导出文件（{e}）")
            log(f"  ⚠ {name}：没有导出文件，跳过")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name} 解析失败：{e}")
            log(f"  ✗ {name} 解析失败：{e}")
            log(traceback.format_exc(limit=2))

    # ---- 写素材明细
    material_ok = 0
    if items:
        records = [{"fields": clean_fields(r)} for r in items]
        try:
            feishu.batch_create(cfg["feishu"]["table_material"], records)
            material_ok = len(records)
            st["material_ids"] = sorted(set(st["material_ids"]) | {r["素材ID"] for r in items})
            save_state(st)
            log(f"  素材写入成功 {material_ok} 条")
        except FeishuError as e:
            errors.append(f"飞书写素材明细失败：{e}")
            log(f"  ✗ 飞书写素材明细失败：{str(e)[:200]}")
    else:
        log("  今天没有新素材要写")

    # ---- 汇总
    views = sum(i.get("播放/浏览量") or 0 for i in items)
    likes = sum(i.get("点赞") or 0 for i in items)
    comments = sum(i.get("评论") or 0 for i in items)
    collects = sum(i.get("收藏") or 0 for i in items)
    shares = sum(i.get("分享/转发") or 0 for i in items)
    dy_items = [i for i in items if i["平台"] == "抖音"]
    xhs_items = [i for i in items if i["平台"] == "小红书"]
    best = max(items, key=lambda x: x.get("播放/浏览量") or 0) if items else None

    if not errors:
        run_status = "正常"
    elif len(errors) >= 2:
        run_status = "失败"
    else:
        run_status = "部分异常"

    summary = build_summary(items, manual, cfg.get("accounts", {}))
    day_ts = int(datetime.strptime(day, "%Y-%m-%d").timestamp() * 1000)

    daily_fields = clean_fields({
        "日期": day_ts,
        "平台范围": "抖音+小红书",
        "内容条数": len(items),
        "总曝光": views,
        "总互动": likes + comments + collects + shares,
        "新增粉丝": (sum(i.get("新增粉丝") or 0 for i in items) or None),
        "私信咨询数": manual.get("私信咨询数"),
        "咨询来源": manual.get("咨询来源") or None,
        "报名意向人数": manual.get("报名意向人数"),
        "抖音条数": len(dy_items),
        "抖音曝光": sum(i.get("播放/浏览量") or 0 for i in dy_items),
        "小红书条数": len(xhs_items),
        "小红书曝光": sum(i.get("播放/浏览量") or 0 for i in xhs_items),
        "最佳素材": short((best or {}).get("标题/文案"), 26),
        "每日小结": summary,
        "运行状态": run_status,
        "异常原因": "；".join(errors) if errors else None,
        "采集时间": int(datetime.now().timestamp() * 1000),
        "数据来源": "后台导出",
    })

    try:
        feishu.batch_create(cfg["feishu"]["table_daily"], [{"fields": daily_fields}])
        log(f"  汇总行写入成功（{day}：{len(items)} 条 / 曝光 {views} / {run_status}）")
    except FeishuError as e:
        errors.append(f"飞书写汇总失败：{e}")
        log(f"  ✗ 飞书写汇总失败：{str(e)[:200]}")
        run_status = "失败"

    # ---- 本地留档（无论如何都存一份，方便对账）
    out_dir = os.path.join(BASE, "data", "output")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"{day}.json"), "w", encoding="utf-8") as f:
        json.dump({
            "date": day, "dry_run": args.dry_run, "run_status": run_status,
            "sources": sources, "errors": errors,
            "items": items, "summary": summary, "daily_fields": daily_fields,
        }, f, ensure_ascii=False, indent=2)
    log(f"  本地留档 data/output/{day}.json")

    log("=" * 60)
    log(f"结束：{run_status}；素材 {len(items)} 条；错误 {len(errors)} 个")
    for e in errors:
        log(f"  ! {e}")

    if run_status == "失败":
        return 1
    if errors:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
