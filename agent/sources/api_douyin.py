# -*- coding: utf-8 -*-
"""抖音官方开放平台适配器（骨架，等资质/权限下来后填这里）

现状：**未启用**。daily_job.py 在 source.mode != "api" 时不会调用本文件。

## 申请路径
https://developer.open-douyin.com → 创建应用 → 申请 `video.list` / `video.data` → 绑定「不止攀岩」抖音号

## 需要的凭证（放 config.json 的 api.douyin 里）
    api.douyin.client_key
    api.douyin.client_secret
    api.douyin.access_token      # 或由 client_credentials / 授权码换

## 接口（以官方文档为准，这里只写调用位置）
- 作品列表：GET /video/list/  ?open_id=...&cursor=...&count=20
- 作品数据：GET /video/data/  ?item_ids=...
- 粉丝数：  GET /data/user/fans/  （部分能力开放）

## 返回后要转成的格式（和 collect_douyin.py 一致）
[
  {
    "素材ID": "douyin_<item_id>", "内容ID": "<item_id>", "平台": "抖音",
    "发布日期": 1745000000000,            # 毫秒时间戳
    "标题/文案": "...", "素材链接": "https://www.douyin.com/video/<id>",
    "内容类型": "视频",
    "播放/浏览量": 1234, "点赞": 12, "评论": 3, "收藏": 4, "分享/转发": 1,
    "新增粉丝": 0, "互动合计": 20,
  }, ...
]
"""

import json
import os
import urllib.parse
import urllib.request

API_BASE = "https://open.douyin.com"


class DouyinApiError(RuntimeError):
    pass


def _get(path, params, token):
    url = f"{API_BASE}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={
        "access-token": token,
        "User-Agent": "buzhi-ops-agent/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise DouyinApiError(f"抖音接口请求失败：{exc}") from exc
    if data.get("data", {}).get("error_code"):
        raise DouyinApiError(f"抖音接口返回错误：{data['data']}")
    return data


def collect(cfg, date_str, inbox_dir=None):
    """采集指定日期的抖音素材。

    :param cfg: config.json 里 api.douyin 那段
    :param date_str: "2026-11-18"
    :returns: 标准记录列表（同 collect_douyin.py）
    """
    token = (cfg or {}).get("access_token", "")
    if not token:
        raise DouyinApiError(
            "未配置 api.douyin.access_token。"
            "要么去开放平台拿 token，要么把 config.json 的 source.mode 改回 export。"
        )

    # TODO(二期)：拿 open_id → 拉作品列表 → 拉作品数据 → 转标准记录
    # 下面这一行现在会直接抛错，是故意的：避免有人以为已经接通了。
    raise DouyinApiError("抖音官方接口适配器尚未实现（等应用审核通过后填这里）")

    # 参考实现（权限下来后照这个补）：
    # open_id = cfg["open_id"]
    # items = []
    # cursor = 0
    # while True:
    #     page = _get("/video/list/", {"open_id": open_id, "cursor": cursor, "count": 20}, token)
    #     items.extend(page["data"]["list"] or [])
    #     if not page["data"].get("has_more"):
    #         break
    #     cursor = page["data"]["cursor"]
    # records = []
    # for it in items:
    #     ...转格式，按 date_str 过滤...
    # return records


def health(cfg):
    return {
        "enabled": bool((cfg or {}).get("access_token")),
        "implemented": False,
        "note": "抖音官方数据接口需资质审核；未通过前请用后台导出 CSV",
    }


if __name__ == "__main__":
    print(json.dumps(health({}), ensure_ascii=False, indent=2))
