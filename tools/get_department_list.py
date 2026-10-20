from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _utils.dingtalk_client import DingTalkError, get_access_token, list_sub_departments

MAX_DEPARTMENTS = 200


class GetDepartmentListTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        dept_id_raw = (tool_parameters.get("dept_id") or "1").strip() or "1"
        if not dept_id_raw.isdigit():
            yield self.create_text_message("错误：dept_id 不是数字（根部门为 1）。")
            return
        dept_id = int(dept_id_raw)
        recursive = bool(tool_parameters.get("recursive"))

        try:
            token = get_access_token(self.runtime.credentials["app_key"], self.runtime.credentials["app_secret"])
            departments = list_sub_departments(token, dept_id)
            if recursive:
                queue = [d["dept_id"] for d in departments if d.get("dept_id") is not None]
                while queue:
                    for sub in list_sub_departments(token, queue.pop(0)):
                        sub_id = sub.get("dept_id")
                        if sub_id is None:
                            continue
                        if len(departments) >= MAX_DEPARTMENTS:
                            yield self.create_text_message(f"错误：部门数量超过上限 {MAX_DEPARTMENTS}，请缩小范围。")
                            return
                        departments.append(sub)
                        queue.append(sub_id)
        except DingTalkError as e:
            yield self.create_text_message(f"获取部门列表失败：{e}")
            return
        except Exception as e:
            yield self.create_text_message(f"获取部门列表失败：{e}")
            return

        dept_ids = [str(d["dept_id"]) for d in departments if d.get("dept_id") is not None]
        joined = ",".join(dept_ids)
        yield self.create_variable_message("dept_ids", joined)
        yield self.create_variable_message("count", len(dept_ids))
        yield self.create_json_message(
            {
                "count": len(departments),
                "departments": [
                    {"dept_id": d.get("dept_id"), "name": d.get("name"), "parent_id": d.get("parent_id")}
                    for d in departments
                ],
            }
        )
        if joined:
            yield self.create_text_message(joined)
        else:
            yield self.create_text_message(f"部门 {dept_id} 下没有子部门。")
