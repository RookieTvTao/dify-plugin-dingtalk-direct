"""Thin client for the DingTalk Open Platform server APIs used by this plugin.

DingTalk has two API styles:
- oapi.dingtalk.com: errors come back as errcode/errmsg inside an HTTP 200 body.
- api.dingtalk.com: errors use HTTP status codes plus a body code/message.
"""

from __future__ import annotations

import concurrent.futures
import json
import re
import threading
import time
from collections import deque
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


_ERRCODE_HINTS = {
    50004: "多为应用「通讯录权限范围」未覆盖该部门：请管理员到 开发者后台→应用→权限管理→页面顶部「通讯录权限范围」添加该部门或改为全部员工",
}


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
        msg = f"{data.get('errmsg', '未知错误')}（errcode {errcode}）"
        hint = _ERRCODE_HINTS.get(errcode)
        if hint:
            msg = f"{msg}。{hint}"
        raise DingTalkError(msg, code=errcode)
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


def to_bool(value: Any) -> bool:
    """Tolerate booleans arriving as strings ("True"/"false"/"1") when wired from variables."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ("1", "true", "yes", "on")


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


def walk_departments(token: str, roots: list[int], include_sub: bool, max_departments: int = 1000) -> list[int]:
    """Root departments plus (optionally) their whole sub-tree, BFS with dedupe."""
    departments = list(roots)
    if not include_sub:
        return departments
    visited = set(roots)
    queue = deque(roots)
    while queue:
        for sub in list_sub_departments(token, queue.popleft()):
            sub_id = sub.get("dept_id")
            if sub_id is None or sub_id in visited:
                continue
            if len(departments) >= max_departments:
                raise DingTalkError(f"子部门数量超过上限 {max_departments}，请缩小范围后分部门查询")
            visited.add(sub_id)
            departments.append(sub_id)
            queue.append(sub_id)
    return departments


def get_user_detail(token: str, userid: str) -> dict:
    """User detail via /topapi/v2/user/get (needs qyapi_get_member)."""
    data = post_old_api("/topapi/v2/user/get", token, {"userid": userid, "language": "zh_CN"})
    return data.get("result") or {}


def get_authorized_scope_dept_ids(token: str) -> list[int]:
    """Departments the app's address-book permission scope covers, via /topapi/auth/scopes.

    Returns [] when the scope is empty or the API gives nothing usable.
    """
    try:
        data = post_old_api("/topapi/auth/scopes", token, {})
    except DingTalkError:
        return []
    result = data.get("result") or {}
    dept_ids: list[int] = []
    for cond in result.get("conditions") or []:
        for d in cond.get("dept_ids") or []:
            if isinstance(d, int) and d not in dept_ids:
                dept_ids.append(d)
    return dept_ids


def collect_users_parallel(token: str, departments: list[int], max_users: int = 20000, workers: int = 6) -> dict[str, dict]:
    """Fetch user/list for many departments concurrently; dedupes by userid.

    Retries once on errcode 90018 (per-app rate limit) with a short backoff.
    """
    users: dict[str, dict] = {}

    def fetch(dept_id: int):
        for attempt in (1, 2):
            try:
                return list_dept_users(token, dept_id)
            except DingTalkError as e:
                if e.code == 90018 and attempt == 1:
                    time.sleep(1.0)
                    continue
                raise

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for members in pool.map(fetch, departments):
            for u in members:
                uid = u.get("userid")
                if uid and uid not in users:
                    users[uid] = u
            if len(users) > max_users:
                raise DingTalkError(f"成员数量超过上限 {max_users}，请改用更小的部门范围。")
    return users


JOB_INDEX_TTL = 6 * 3600
_job_index_cache: dict[str, tuple[float, dict[str, list[dict]]]] = {}
_job_index_lock = threading.Lock()


def build_job_index(users: dict[str, dict]) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for u in users.values():
        job = str(u.get("job_number") or "")
        if job:
            index.setdefault(job, []).append(u)
    return index


def get_cached_job_index(app_key: str) -> dict[str, list[dict]] | None:
    with _job_index_lock:
        cached = _job_index_cache.get(app_key)
        if cached and cached[0] > time.monotonic():
            return cached[1]
    return None


def put_job_index(app_key: str, index: dict[str, list[dict]]) -> None:
    with _job_index_lock:
        _job_index_cache[app_key] = (time.monotonic() + JOB_INDEX_TTL, index)


def matches_user(user: dict, keyword: str) -> bool:
    """Keyword matches by name substring or exact job number."""
    if not keyword:
        return True
    if keyword in (user.get("name") or ""):
        return True
    job = str(user.get("job_number") or "")
    return bool(job) and job == keyword


def match_department_by_name(children: list[dict], segment: str) -> tuple[int | None, list[str]]:
    """Match one path segment against direct children.

    Returns (matched dept_id, candidate_names). Exact name match wins; otherwise a unique
    substring match is accepted; ambiguity or no match returns None plus candidate names
    (empty list means nothing matched at all).
    """
    seg = segment.strip()
    exact = [c for c in children if (c.get("name") or "").strip() == seg]
    if len(exact) == 1:
        return exact[0]["dept_id"], []
    pool = exact if exact else [c for c in children if seg in (c.get("name") or "")]
    names = [c.get("name") or "" for c in pool]
    if len(pool) == 1:
        return pool[0]["dept_id"], []
    return None, names


def resolve_dept_path(token: str, path: str, root: int = 1) -> int:
    """Resolve a '公司/部门/子部门' name path into a department id, one level per segment."""
    segments = [s for s in (seg.strip() for seg in re.split(r"[/、]", path or "")) if seg]
    if not segments:
        raise DingTalkError("dept_name_path 为空")
    current = root
    current_name = "根部门"
    for i, seg in enumerate(segments):
        children = list_sub_departments(token, current)
        dept_id, candidates = match_department_by_name(children, seg)
        if dept_id is None:
            if candidates:
                shown = "、".join(candidates[:5]) + ("等" if len(candidates) > 5 else "")
                raise DingTalkError(
                    f"第 {i + 1} 级「{seg}」匹配到 {len(candidates)} 个部门：{shown}；请使用完整名称或继续补充下一级"
                )
            preview = "、".join((c.get("name") or "") for c in children[:8]) + ("…" if len(children) > 8 else "")
            raise DingTalkError(
                f"第 {i + 1} 级：在「{current_name}」的下一级（共 {len(children)} 个部门）中没有匹配「{seg}」的子部门，"
                f"其下一级包括：{preview}。提示：集团总部与各子公司常为平级节点（都挂在根部门下），"
                "若目标在子公司内，请从子公司名称开始填路径。"
            )
        current = dept_id
        current_name = next((c.get("name") or "" for c in children if c.get("dept_id") == dept_id), current_name)
    return current
