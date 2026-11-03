from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _utils.dingtalk_client import (
    DingTalkError,
    build_job_index,
    collect_users_parallel,
    get_access_token,
    get_authorized_scope_dept_ids,
    get_cached_job_index,
    put_job_index,
    to_bool,
    walk_departments,
)

MAX_USERS = 20000
MAX_DEPARTMENTS = 5000


class GetUseridByJobNumberTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        job_number = (tool_parameters.get("job_number") or "").strip()
        if not job_number:
            yield self.create_text_message("错误：job_number 为空，请提供员工工号。")
            return
        dept_id_raw = (tool_parameters.get("dept_id") or "1").strip() or "1"
        if not dept_id_raw.isdigit():
            yield self.create_text_message("错误：dept_id 不是数字（根部门为 1）。")
            return
        recursive = to_bool(tool_parameters.get("recursive"))
        app_key = self.runtime.credentials["app_key"]

        cached_index = None
        from_cache = False
        departments: list[int] = []
        scope_fallback = False
        total_users = 0

        try:
            # Whole-scope searches ride a process-wide job-number index: the first call
            # walks the tree once, later calls (within the TTL) answer instantly.
            if dept_id_raw == "1" and recursive:
                cached_index = get_cached_job_index(app_key)
                if cached_index is not None:
                    from_cache = True
                if cached_index is None:
                    token = get_access_token(app_key, self.runtime.credentials["app_secret"])
                    try:
                        departments = walk_departments(token, [1], True, MAX_DEPARTMENTS)
                    except DingTalkError as e:
                        if e.code != 50004:
                            raise
                        scope_roots = get_authorized_scope_dept_ids(token)
                        if not scope_roots:
                            raise
                        departments = walk_departments(token, scope_roots, True, MAX_DEPARTMENTS)
                        scope_fallback = True
                    users = collect_users_parallel(token, departments, MAX_USERS)
                    total_users = len(users)
                    cached_index = build_job_index(users)
                    put_job_index(app_key, cached_index)
            else:
                token = get_access_token(app_key, self.runtime.credentials["app_secret"])
                try:
                    departments = walk_departments(token, [int(dept_id_raw)], recursive, MAX_DEPARTMENTS)
                except DingTalkError as e:
                    if e.code != 50004:
                        raise
                    scope_roots = get_authorized_scope_dept_ids(token)
                    if not scope_roots:
                        raise
                    departments = walk_departments(token, scope_roots, recursive, MAX_DEPARTMENTS)
                    scope_fallback = True
                users = collect_users_parallel(token, departments, MAX_USERS)
                total_users = len(users)
                cached_index = build_job_index(users)

            if cached_index is None:
                yield self.create_text_message("错误：未能建立工号索引，请稍后重试。")
                return
            found = cached_index.get(job_number, [])
        except DingTalkError as e:
            yield self.create_text_message(f"按工号查询失败：{e}")
            return
        except Exception as e:
            yield self.create_text_message(f"按工号查询失败：{e}")
            return

        user_ids = [u["userid"] for u in found if u.get("userid")]
        joined = ",".join(user_ids)
        yield self.create_variable_message("user_ids", joined)
        yield self.create_variable_message("count", len(user_ids))
        yield self.create_json_message(
            {
                "count": len(found),
                "cached": from_cache,
                "scope_fallback": scope_fallback,
                "departments_scanned": departments,
                "users_indexed": total_users or sum(len(v) for v in cached_index.values()),
                "users": [
                    {
                        "userid": u.get("userid"),
                        "name": u.get("name"),
                        "job_number": u.get("job_number") or "",
                        "mobile": u.get("mobile") or "",
                    }
                    for u in found
                ],
            }
        )
        if joined:
            notes = []
            if from_cache:
                notes.append("命中工号索引缓存")
            if scope_fallback:
                notes.append("根部门不在授权范围，已自动改从应用授权部门搜索")
            suffix = f"（{'；'.join(notes)}）" if notes else ""
            yield self.create_text_message(joined + suffix)
        else:
            yield self.create_text_message(
                f"未找到工号为「{job_number}」的员工（工号以企业通讯录登记的为准；"
                "若确认无误，可能是该员工不在应用通讯录权限范围内）。"
            )
