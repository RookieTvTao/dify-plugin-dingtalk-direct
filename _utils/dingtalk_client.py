"""Thin client for the DingTalk Open Platform server APIs used by this plugin.

DingTalk has two API styles:
- oapi.dingtalk.com: errors come back as errcode/errmsg inside an HTTP 200 body.
- api.dingtalk.com: errors use HTTP status codes plus a body code/message.
"""

import json
import re
import threading
import time
from typing import Any

import requests

OLD_BASE = "https://oapi.dingtalk.com"
NEW_BASE = "https://api.dingtalk.com"
REQUEST_TIMEOUT = 15
CONTENT_LIMIT_BYTES = 2048


class DingTalkError(Exception):
    def __init__(self, message: str, code: Any = None):
        super().__init__(message)
        self.code = code


_token_cache: dict[str, tuple[str, float]] = {}
_token_lock = threading.Lock()


def get_access_token(app_key: str, app_secret: str) -> str:
    """Fetch an enterprise-internal-app accessToken, cached until shortly before expiry."""
    with _token_lock:
        cached = _token_cache.get(app_key)
        if cached and cached[1] > time.monotonic():
            return cached[0]

    try:
        resp = requests.post(
            f"{NEW_BASE}/v1.0/oauth2/accessToken",
            json={"appKey": app_key, "appSecret": app_secret},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        raise DingTalkError(f"获取 accessToken 时网络异常：{e}") from e

    if resp.status_code != 200:
        raise DingTalkError(f"获取 accessToken 失败（HTTP {resp.status_code}）：{resp.text[:300]}")
    data = resp.json()
    token = data.get("accessToken")
    if not token:
        raise DingTalkError(f"获取 accessToken 失败：{resp.text[:300]}")

    # Refresh 5 minutes early to avoid sending with a token that expires mid-flight.
    ttl = max(300, int(data.get("expireIn", 7200)) - 300)
    with _token_lock:
        _token_cache[app_key] = (token, time.monotonic() + ttl)
    return token


def post_old_api(path: str, token: str, payload: dict) -> dict:
    """POST to oapi.dingtalk.com; non-zero errcode raises DingTalkError."""
    try:
        resp = requests.post(
            f"{OLD_BASE}{path}",
            params={"access_token": token},
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        raise DingTalkError(f"调用钉钉接口时网络异常：{e}") from e
    try:
        data = resp.json()
    except ValueError:
        raise DingTalkError(f"钉钉返回非 JSON 响应（HTTP {resp.status_code}）：{resp.text[:300]}")
    errcode = data.get("errcode", 0)
    if errcode != 0:
        raise DingTalkError(f"{data.get('errmsg', '未知错误')}（errcode {errcode}）", code=errcode)
    return data


def post_new_api(path: str, token: str, payload: dict) -> dict:
    """POST to api.dingtalk.com with the x-acs-dingtalk-access-token header."""
    try:
        resp = requests.post(
            f"{NEW_BASE}{path}",
            headers={"x-acs-dingtalk-access-token": token},
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        raise DingTalkError(f"调用钉钉接口时网络异常：{e}") from e
    if resp.status_code >= 400:
        try:
            err = resp.json()
            detail = f"{err.get('code', '')} {err.get('message', '')}".strip() or resp.text[:300]
        except ValueError:
            detail = resp.text[:300]
        raise DingTalkError(f"HTTP {resp.status_code}：{detail}")
    try:
        return resp.json()
    except ValueError:
        return {}


def split_ids(value: str) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def _default_title(title: str, content: str) -> str:
    if title and title.strip():
        return title.strip()
    first_line = next((ln.strip() for ln in content.splitlines() if ln.strip()), "通知")
    return re.sub(r"^[#*\s]+", "", first_line) or "通知"


def build_work_msg(message_type: str, title: str, content: str) -> dict:
    """msg payload for /topapi/message/corpconversation/asyncsend_v2."""
    if message_type == "markdown":
        return {"msgtype": "markdown", "markdown": {"title": _default_title(title, content), "text": content}}
    return {"msgtype": "text", "text": {"content": content}}


def build_robot_msg(message_type: str, title: str, content: str) -> tuple[str, str]:
    """(msgKey, msgParam JSON string) for /v1.0/robot/oToMessages/batchSend."""
    if message_type == "markdown":
        return "sampleMarkdown", json.dumps(
            {"title": _default_title(title, content), "text": content}, ensure_ascii=False
        )
    return "sampleText", json.dumps({"content": content}, ensure_ascii=False)


def check_content_size(content: str) -> None:
    size = len(content.encode("utf-8"))
    if size > CONTENT_LIMIT_BYTES:
        raise DingTalkError(f"消息内容 {size} 字节，超过工作通知 {CONTENT_LIMIT_BYTES} 字节上限")


USER_LIST_PAGE_SIZE = 100


def list_dept_users(token: str, dept_id: int) -> list[dict]:
    """All members of one department via /topapi/v2/user/list (cursor-paginated)."""
    users: list[dict] = []
    cursor = 0
    while True:
        data = post_old_api(
            "/topapi/v2/user/list",
            token,
            {
                "dept_id": dept_id,
                "cursor": cursor,
                "size": USER_LIST_PAGE_SIZE,
                "contain_access_limit": False,
                "language": "zh_CN",
            },
        )
        result = data.get("result") or {}
        users.extend(result.get("list") or [])
        if not result.get("has_more"):
            break
        cursor = result.get("next_cursor")
        if cursor is None:
            break
    return users


def list_sub_departments(token: str, dept_id: int) -> list[dict]:
    """Direct child departments via /topapi/v2/department/listsub."""
    data = post_old_api(
        "/topapi/v2/department/listsub", token, {"dept_id": dept_id, "language": "zh_CN"}
    )
    return data.get("result") or []
