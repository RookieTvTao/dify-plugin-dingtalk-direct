from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _utils.dingtalk_client import (
    DingTalkError,
    get_access_token,
    list_dept_users,
    to_bool,
    walk_departments,
)

MAX_USERS = 5000


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

        try:
            token = get_access_token(self.runtime.credentials["app_key"], self.runtime.credentials["app_secret"])
            departments = walk_departments(token, [int(dept_id_raw)], recursive)
            found: list[dict] = []
            scanned = 0
            for d in departments:
                for u in list_dept_users(token, d):
                    scanned += 1
                    if str(u.get("job_number") or "") == job_number:
                        found.append(u)
                if scanned > MAX_USERS:
                    yield self.create_text_message(f"错误：扫描成员超过上限 {MAX_USERS}，请改用更小的部门范围。")
                    return
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
            yield self.create_text_message(joined)
        else:
            yield self.create_text_message(
                f"在 {len(departments)} 个部门共 {scanned} 名成员中未找到工号为「{job_number}」的员工"
                "（工号以企业通讯录登记的为准）。"
            )
