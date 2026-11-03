from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _utils.dingtalk_client import (
    DingTalkError,
    get_access_token,
    get_authorized_scope_dept_ids,
    list_dept_users,
    matches_user,
    split_ids,
    to_bool,
    walk_departments,
)

MAX_USERS = 5000


class GetDepartmentUsersTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        dept_ids_in = split_ids(tool_parameters.get("dept_id", ""))
        if not dept_ids_in or not all(d.isdigit() for d in dept_ids_in):
            yield self.create_text_message(
                "错误：dept_id 为空或含非数字项。支持单个部门 id 或半角逗号分隔多个"
                "（根部门为 1；可直接连「获取部门列表」的 dept_ids 输出）。"
            )
            return
        roots = [int(d) for d in dept_ids_in]
        include_sub = to_bool(tool_parameters.get("include_sub_departments"))
        keyword = (tool_parameters.get("name_filter") or "").strip()

        try:
            token = get_access_token(self.runtime.credentials["app_key"], self.runtime.credentials["app_secret"])
            try:
                departments = walk_departments(token, roots, include_sub)
                scope_fallback = False
            except DingTalkError as e:
                # Roots outside the app's address-book scope: retry from the authorized scope.
                if e.code != 50004:
                    raise
                scope_roots = get_authorized_scope_dept_ids(token)
                if not scope_roots:
                    raise
                departments = walk_departments(token, scope_roots, include_sub)
                scope_fallback = True
            users: dict[str, dict] = {}
            for d in departments:
                for u in list_dept_users(token, d):
                    uid = u.get("userid")
                    if uid and uid not in users:
                        users[uid] = u
                if len(users) > MAX_USERS:
                    yield self.create_text_message(f"错误：成员数量超过上限 {MAX_USERS}，请改用更小的部门范围。")
                    return
        except DingTalkError as e:
            yield self.create_text_message(f"获取部门成员失败：{e}")
            return
        except Exception as e:
            yield self.create_text_message(f"获取部门成员失败：{e}")
            return

        matched = [u for u in users.values() if matches_user(u, keyword)]
        user_ids = [u["userid"] for u in matched]
        joined = ",".join(user_ids)
        yield self.create_variable_message("user_ids", joined)
        yield self.create_variable_message("count", len(user_ids))
        yield self.create_json_message(
            {
                "count": len(matched),
                "scope_fallback": scope_fallback,
                "departments_scanned": departments,
                "users": [
                    {
                        "userid": u.get("userid"),
                        "name": u.get("name"),
                        "job_number": u.get("job_number") or "",
                        "mobile": u.get("mobile") or "",
                    }
                    for u in matched
                ],
            }
        )
        if joined:
            yield self.create_text_message(joined)
        elif keyword:
            yield self.create_text_message(
                f"共扫描 {len(departments)} 个部门的 {len(users)} 名成员，没有姓名包含或工号等于「{keyword}」的成员。"
            )
        else:
            yield self.create_text_message(f"所查 {len(departments)} 个部门均没有直属成员（成员可能在子部门，试试开启递归）。")
