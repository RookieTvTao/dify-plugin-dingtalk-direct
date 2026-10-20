from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _utils.dingtalk_client import (
    DingTalkError,
    get_access_token,
    list_dept_users,
    list_sub_departments,
    split_ids,
    to_bool,
)

MAX_USERS = 5000
MAX_DEPARTMENTS = 100


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
        name_filter = (tool_parameters.get("name_filter") or "").strip()

        try:
            token = get_access_token(self.runtime.credentials["app_key"], self.runtime.credentials["app_secret"])

            departments = list(roots)
            if include_sub:
                visited = set(roots)
                queue = list(roots)
                while queue:
                    for sub in list_sub_departments(token, queue.pop(0)):
                        sub_id = sub.get("dept_id")
                        if sub_id is None or sub_id in visited:
                            continue
                        if len(departments) >= MAX_DEPARTMENTS:
                            yield self.create_text_message(
                                f"错误：子部门数量超过上限 {MAX_DEPARTMENTS}，请缩小范围后分部门查询。"
                            )
                            return
                        visited.add(sub_id)
                        departments.append(sub_id)
                        queue.append(sub_id)

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

        matched = [u for u in users.values() if not name_filter or name_filter in (u.get("name") or "")]
        user_ids = [u["userid"] for u in matched]
        joined = ",".join(user_ids)
        yield self.create_variable_message("user_ids", joined)
        yield self.create_variable_message("count", len(user_ids))
        yield self.create_json_message(
            {
                "count": len(matched),
                "departments_scanned": departments,
                "users": [
                    {"userid": u.get("userid"), "name": u.get("name"), "mobile": u.get("mobile") or ""}
                    for u in matched
                ],
            }
        )
        if joined:
            yield self.create_text_message(joined)
        elif name_filter:
            yield self.create_text_message(
                f"共扫描 {len(departments)} 个部门的 {len(users)} 名成员，没有姓名包含「{name_filter}」的成员。"
            )
        else:
            yield self.create_text_message(f"所查 {len(departments)} 个部门均没有直属成员（成员可能在子部门，试试开启递归）。")
