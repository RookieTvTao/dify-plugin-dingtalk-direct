from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _utils.dingtalk_client import (
    DingTalkError,
    get_access_token,
    list_dept_users,
    list_sub_departments,
)

MAX_USERS = 5000
MAX_DEPARTMENTS = 100


class GetDepartmentUsersTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        dept_id_raw = (tool_parameters.get("dept_id") or "").strip()
        if not dept_id_raw.isdigit():
            yield self.create_text_message("错误：dept_id 为空或不是数字（根部门为 1，可用「获取部门列表」工具查询）。")
            return
        dept_id = int(dept_id_raw)
        include_sub = bool(tool_parameters.get("include_sub_departments"))
        name_filter = (tool_parameters.get("name_filter") or "").strip()

        try:
            token = get_access_token(self.runtime.credentials["app_key"], self.runtime.credentials["app_secret"])

            departments = [dept_id]
            if include_sub:
                queue = [dept_id]
                while queue:
                    for sub in list_sub_departments(token, queue.pop(0)):
                        sub_id = sub.get("dept_id")
                        if sub_id is None:
                            continue
                        if len(departments) >= MAX_DEPARTMENTS:
                            yield self.create_text_message(
                                f"错误：子部门数量超过上限 {MAX_DEPARTMENTS}，请缩小范围后分部门查询。"
                            )
                            return
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
            yield self.create_text_message(f"共扫描 {len(users)} 名成员，没有姓名包含「{name_filter}」的成员。")
        else:
            yield self.create_text_message(f"部门 {dept_id} 没有成员。")
