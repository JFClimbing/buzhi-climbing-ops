# -*- coding: utf-8 -*-
"""在飞书多维表格里建好两张表 + 全部字段（幂等，已存在就跳过）

用法：
    python setup_tables.py            # 只打印计划（默认，安全）
    python setup_tables.py --yes      # 真的去飞书创建（需要 config.json 里配好凭证）

前提：
- config.json 里 feishu.app_token / app_id / app_secret 已填
- 应用已开权限 bitable:app 并发布版本
"""
import json
import os
import sys

from feishu import Feishu, FeishuError

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(BASE, "config.json")

TEXT, NUM, SINGLE, DATE, ATTACH, URL = 1, 2, 3, 5, 17, 15

MATERIAL = "新媒体-素材明细"
DAILY = "新媒体-每日汇总"

MATERIAL_FIELDS = [
    ("素材ID", TEXT, None),
    ("内容ID", TEXT, None),
    ("平台", SINGLE, ["抖音", "小红书"]),
    ("发布日期", DATE, None),
    ("标题/文案", TEXT, None),
    ("素材链接", URL, None),
    ("封面", ATTACH, None),
    ("内容类型", SINGLE, ["视频", "图文", "合集"]),
    ("播放/浏览量", NUM, None),
    ("点赞", NUM, None),
    ("评论", NUM, None),
    ("收藏", NUM, None),
    ("分享/转发", NUM, None),
    ("新增粉丝", NUM, None),
    ("互动合计", NUM, None),
    ("私信咨询数", NUM, None),
    ("咨询来源", SINGLE, ["抖音", "小红书", "朋友介绍", "其他"]),
    ("报名意向", NUM, None),
    ("数据来源", SINGLE, ["后台导出", "官方API", "人工"]),
]

DAILY_FIELDS = [
    ("日期", DATE, None),
    ("平台范围", SINGLE, ["抖音+小红书", "抖音", "小红书"]),
    ("内容条数", NUM, None),
    ("总曝光", NUM, None),
    ("总互动", NUM, None),
    ("抖音条数", NUM, None),
    ("抖音曝光", NUM, None),
    ("小红书条数", NUM, None),
    ("小红书曝光", NUM, None),
    ("最佳素材", TEXT, None),
    ("每日小结", TEXT, None),
    ("新增粉丝", NUM, None),
    ("私信咨询数", NUM, None),
    ("报名意向", NUM, None),
    ("成交定金", NUM, None),
    ("询单转化率", NUM, None),
    ("运行状态", SINGLE, ["正常", "部分异常", "异常"]),
    ("异常原因", TEXT, None),
    ("采集时间", DATE, None),
    ("数据来源", SINGLE, ["后台导出", "官方API", "人工"]),
]


def field_payload(name, ftype, options=None):
    body = {"field_name": name, "type": ftype}
    if ftype == SINGLE and options:
        body["property"] = {"options": [{"name": o} for o in options]}
    if ftype == NUM:
        body["property"] = {"formatter": "0"}
    if ftype == DATE:
        body["property"] = {"date_formatter": "yyyy/MM/dd HH:mm", "auto_fill": False}
    return body


def load_config():
    path = CONFIG if os.path.exists(CONFIG) else os.path.join(BASE, "config.example.json")
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg, path


def is_placeholder(cfg):
    f = cfg.get("feishu", {})
    ids = [f.get("app_id", ""), f.get("app_secret", ""), f.get("app_token", "")]
    return any((not v) or "xxx" in v or v.startswith("cli_xxx") for v in ids)


def list_tables(fs):
    tables, page_token = [], ""
    while True:
        q = "?page_size=100" + (f"&page_token={page_token}" if page_token else "")
        resp = fs._api("GET", f"/open-apis/bitable/v1/apps/{fs.app_token}/tables{q}")
        if resp.get("code") != 0:
            raise FeishuError(f"读表失败: {resp}")
        data = resp.get("data", {})
        tables += data.get("items", [])
        page_token = data.get("page_token") or ""
        if not data.get("has_more"):
            break
    return tables


def ensure_table(fs, tables, name):
    for t in tables:
        if t.get("name") == name:
            return t.get("table_id"), False
    resp = fs._api(
        "POST",
        f"/open-apis/bitable/v1/apps/{fs.app_token}/tables",
        {"table": {"name": name, "default_view_name": "全部"}},
    )
    if resp.get("code") != 0:
        raise FeishuError(f"建表 {name} 失败: {resp}")
    return resp["data"]["table_id"], True


def ensure_fields(fs, table_id, specs, dry):
    existing = {} if dry else {x["field_name"]: x for x in fs.list_fields(table_id)}
    plan = []
    for name, ftype, options in specs:
        if name in existing:
            continue
        plan.append((name, field_payload(name, ftype, options)))
    return plan


def main():
    do_it = "--yes" in sys.argv
    cfg, path = load_config()
    print(f"配置：{path}")
    fs = Feishu(cfg, dry_run=True, base_dir=BASE, log=print)
    fs.app_token = cfg.get("feishu", {}).get("app_token", "")

    placeholder = is_placeholder(cfg)
    print("凭证：" + ("❌ 还是占位符（cli_xxx）" if placeholder else "✅ 已填"))
    print("模式：" + ("真写飞书" if (do_it and not placeholder) else "只打印计划（不写）"))
    print()

    if do_it and placeholder:
        print("❌ config.json 里 app_id/app_secret/app_token/app 地址还没填真实值，先填再跑 --yes。")
        return 1

    if do_it:
        fs = Feishu(cfg, dry_run=False, base_dir=BASE, log=print)

    tables = [] if placeholder else list_tables(fs)
    for name, specs in ((MATERIAL, MATERIAL_FIELDS), (DAILY, DAILY_FIELDS)):
        if placeholder:
            print(f"【{name}】将新建表 + {len(specs)} 个字段：")
            for n, t, o in specs:
                print(f"   - {n}（type={t}{'，选项=' + '/'.join(o) if o else ''}）")
            print()
            continue
        tid, created = ensure_table(fs, tables, name)
        print(f"【{name}】table_id={tid} " + ("（新建）" if created else "（已存在）"))
        plan = ensure_fields(fs, tid, specs, dry=not do_it)
        if not plan:
            print("   字段齐全，无需新增")
        for n, body in plan:
            if do_it:
                resp = fs._api(
                    "POST",
                    f"/open-apis/bitable/v1/apps/{fs.app_token}/tables/{tid}/fields",
                    body,
                )
                ok = resp.get("code") == 0
                print(f"   {'✅' if ok else '❌'} 建字段 {n}" + ("" if ok else f" → {resp}"))
            else:
                print(f"   [计划] 建字段 {n}")
        print()
        if created:
            tables.append({"name": name, "table_id": tid})

    print("完成。把上面的 table_id 填到 config.json 的 table_material / table_daily。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
