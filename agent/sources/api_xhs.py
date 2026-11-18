# -*- coding: utf-8 -*-
"""小红书适配器（骨架，大概率用不上）

小红书几乎没有对第三方开放内容数据 API 的通道（个人/小工作室拿不到）。
本文件保留位置：如果将来拿到服务商权限，把 collect() 实现掉即可，daily_job.py 不用改。

## 现状
- `source.mode = "export"` 时：走 `collect_xhs.py` 读后台导出 CSV（默认，合规、够用）
- `source.mode = "api"` 且配了 `api.xhs.access_token` 时：调本文件

## 返回格式（和 collect_xhs.py 一致）
[
  {
    "素材ID": "xhs_<note_id>", "内容ID": "<note_id>", "平台": "小红书",
    "发布日期": 1745000000000, "标题/文案": "...",
    "素材链接": "https://www.xiaohongshu.com/explore/<id>",
    "内容类型": "图文",
    "播放/浏览量": 1234, "点赞": 12, "评论": 3, "收藏": 4, "分享/转发": 1,
    "新增粉丝": 0, "互动合计": 20,
  }
]
"""

import json


class XhsApiError(RuntimeError):
    pass


def collect(cfg, date_str, inbox_dir=None):
    token = (cfg or {}).get("access_token", "")
    if not token:
        raise XhsApiError(
            "未配置 api.xhs.access_token。小红书建议继续用后台导出（source.mode=export）。"
        )
    raise XhsApiError("小红书官方数据接口未开放给第三方；请使用后台导出 CSV 方案")


def health(cfg):
    return {
        "enabled": bool((cfg or {}).get("access_token")),
        "implemented": False,
        "note": "小红书内容数据无第三方 API；本方案使用后台导出（完全合规）",
    }


if __name__ == "__main__":
    print(json.dumps(health({}), ensure_ascii=False, indent=2))
