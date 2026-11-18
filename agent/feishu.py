# -*- coding: utf-8 -*-
"""飞书多维表格最小客户端（纯标准库）

- tenant_access_token 获取与缓存
- 批量写入记录（batch_create，单批 ≤ 500 条，自动分批）
- 上传附件（封面图，可选）
- 429 限流自动退避重试
- dry_run=True 时只把 payload 落盘到 dryrun/，不真的调接口
"""
import json
import os
import time
import urllib.error
import urllib.request

RETRYABLE = {429, 500, 502, 503, 504}


class FeishuError(RuntimeError):
    pass


class Feishu:
    def __init__(self, cfg, dry_run=False, base_dir=None, log=print):
        f = cfg.get("feishu", {})
        self.app_id = f.get("app_id", "")
        self.app_secret = f.get("app_secret", "")
        self.app_token = f.get("app_token", "")
        self.table_material = f.get("table_material", "")
        self.table_daily = f.get("table_daily", "")
        self.base_url = (f.get("base_url") or "https://open.feishu.cn").rstrip("/")
        self.dry_run = dry_run
        self.base_dir = base_dir or os.getcwd()
        self.log = log
        self._token = None
        self._token_exp = 0

    # ------------------------------------------------------------ HTTP
    def _request(self, method, path, body=None, headers=None, raw=False, retries=3):
        url = path if path.startswith("http") else self.base_url + path
        data = None
        hdrs = {"Content-Type": "application/json; charset=utf-8"}
        if headers:
            hdrs.update(headers)
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        last = None
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
                with urllib.request.urlopen(req, timeout=30) as r:
                    payload = r.read()
                    return payload if raw else json.loads(payload.decode("utf-8"))
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")
                last = f"HTTP {e.code}: {detail[:300]}"
                if e.code in RETRYABLE and attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise FeishuError(last)
            except Exception as e:  # noqa: BLE001
                last = repr(e)
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise FeishuError(last)
        raise FeishuError(last or "unknown")

    # ------------------------------------------------------------ token
    def token(self):
        if self._token and time.time() < self._token_exp:
            return self._token
        if self.dry_run:
            self._token = "dry-run-token"
            self._token_exp = time.time() + 600
            return self._token
        resp = self._request(
            "POST", "/open-apis/auth/v3/tenant_access_token/internal",
            {"app_id": self.app_id, "app_secret": self.app_secret},
        )
        if resp.get("code") != 0:
            raise FeishuError(f"取 token 失败: {resp}")
        self._token = resp["tenant_access_token"]
        self._token_exp = time.time() + max(60, resp.get("expire", 7200) - 120)
        return self._token

    def _api(self, method, path, body=None):
        return self._request(method, path, body, {"Authorization": f"Bearer {self.token()}"})

    # ------------------------------------------------------------ 写入
    def batch_create(self, table_id, records, batch=200):
        """records: [{'fields': {...}}]；返回写入成功的 record_id 列表"""
        if self.dry_run:
            self._dump(f"dryrun_{table_id}_records.json", records)
            return [f"dry_{i}" for i in range(len(records))]
        ids = []
        for i in range(0, len(records), batch):
            chunk = records[i:i + batch]
            resp = self._api(
                "POST",
                f"/open-apis/bitable/v1/apps/{self.app_token}/tables/{table_id}/records/batch_create",
                {"records": chunk},
            )
            if resp.get("code") != 0:
                raise FeishuError(f"批量写入失败: {resp}")
            ids += [r.get("record_id") for r in resp.get("data", {}).get("records", [])]
            self.log(f"  写入 {len(chunk)} 条 → {table_id}")
        return ids

    def list_fields(self, table_id):
        if self.dry_run:
            return []
        resp = self._api(
            "GET",
            f"/open-apis/bitable/v1/apps/{self.app_token}/tables/{table_id}/fields?page_size=100",
        )
        if resp.get("code") != 0:
            raise FeishuError(f"读字段失败: {resp}")
        return resp.get("data", {}).get("items", [])

    def upload_media(self, file_path, parent_type="bitable_file"):
        """上传本地图片，返回 file_token（写入附件字段用）"""
        if self.dry_run or not file_path or not os.path.exists(file_path):
            return None
        boundary = "----feishu" + str(int(time.time() * 1000))
        with open(file_path, "rb") as f:
            content = f.read()
        name = os.path.basename(file_path)
        parts = []
        for k, v in (("file_name", name), ("parent_type", parent_type),
                     ("size", str(len(content)))):
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n")
        head = "".join(parts).encode("utf-8")
        head += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
                 f"filename=\"{name}\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode("utf-8")
        body = head + content + f"\r\n--{boundary}--\r\n".encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/open-apis/drive/v1/medias/upload_all",
            data=body,
            headers={
                "Authorization": f"Bearer {self.token()}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read().decode("utf-8"))
        if resp.get("code") != 0:
            raise FeishuError(f"上传附件失败: {resp}")
        return resp["data"]["file_token"]

    # ------------------------------------------------------------ 工具
    def _dump(self, name, payload):
        d = os.path.join(self.base_dir, "dryrun")
        os.makedirs(d, exist_ok=True)
        self._dump_seq = getattr(self, "_dump_seq", 0) + 1
        stem, ext = os.path.splitext(name)
        path = os.path.join(d, f"{stem}_{self._dump_seq}{ext}")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        self.log(f"  [dry-run] 落盘 {path}")
