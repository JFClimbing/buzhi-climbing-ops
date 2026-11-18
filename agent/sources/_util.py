# -*- coding: utf-8 -*-
"""采集层公用工具：读 CSV/JSON 导出、字段别名匹配、数字/日期清洗"""
import csv
import json
import os
import re
from datetime import datetime

TIME_FMTS = [
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
    "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d",
    "%Y年%m月%d日 %H:%M", "%Y年%m月%d日",
]


def to_int(v):
    """'1.8万' / '19,300' / '134' / '-' → int | None"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip().replace(",", "").replace(" ", "")
    if not s or s in {"-", "—", "--", "暂无", "无"}:
        return None
    mult = 1
    if s.endswith("万"):
        mult, s = 10000, s[:-1]
    elif s.endswith("w") or s.endswith("W"):
        mult, s = 10000, s[:-1]
    elif s.endswith("亿"):
        mult, s = 100000000, s[:-1]
    s = re.sub(r"[^\d.]", "", s)
    if not s:
        return None
    try:
        return int(round(float(s) * mult))
    except ValueError:
        return None


def to_ts_ms(v):
    """日期字符串 → 毫秒时间戳（飞书日期字段）；失败返回 None"""
    if v is None:
        return None
    if isinstance(v, (int, float)) and v > 10_000_000_000:
        return int(v)
    s = str(v).strip()
    if not s:
        return None
    for fmt in TIME_FMTS:
        try:
            return int(datetime.strptime(s, fmt).timestamp() * 1000)
        except ValueError:
            continue
    # 2026-10-23T20:39:00+08:00
    try:
        return int(datetime.fromisoformat(s).timestamp() * 1000)
    except ValueError:
        return None


def pick(row, *aliases, default=None):
    """按别名顺序取第一个非空值"""
    for a in aliases:
        if a in row and str(row[a]).strip() not in ("", "None"):
            return row[a]
    # 模糊匹配：去掉空格和括号再比
    norm = {re.sub(r"[\s()（）]", "", str(k)): v for k, v in row.items()}
    for a in aliases:
        k2 = re.sub(r"[\s()（）]", "", a)
        for nk, nv in norm.items():
            if nk == k2 and str(nv).strip() not in ("", "None"):
                return nv
    return default


def read_table(path):
    """读 .csv（自动试 utf-8-sig / gbk）或 .json（list[dict]）→ list[dict]"""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for k in ("data", "items", "list", "notes", "works"):
                if isinstance(data.get(k), list):
                    return data[k]
            return [data]
        return data if isinstance(data, list) else []
    rows = None
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                rows = list(csv.DictReader(f))
            break
        except UnicodeDecodeError:
            continue
    if rows is None:
        raise ValueError(f"无法解码 CSV：{path}")
    return [r for r in rows if any(str(v).strip() for v in r.values())]


def find_files(inbox_dir, prefix):
    """inbox 下以 prefix 开头的导出文件（取文件名排序最后一个=最新）"""
    if not os.path.isdir(inbox_dir):
        return []
    names = [
        os.path.join(inbox_dir, n)
        for n in sorted(os.listdir(inbox_dir))
        if n.lower().startswith(prefix) and os.path.splitext(n)[1].lower() in (".csv", ".json", ".xlsx")
    ]
    return names


def short(text, limit=2000):
    s = "" if text is None else str(text)
    return s[:limit]
