from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _utils.dingtalk_client import (
    DingTalkError,
    get_access_token,
    get_user_detail,
    post_old_api,
)


class GetUserDepartmentsTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        mobile = (tool_parameters.get("mobile") or "").strip()
        user_id = (tool_parameters.get("user_id") or "").strip()
        if not mobile and not user_id:
            yield self.create_text_message("错误：mobile 与 user_id 至少填一个。")
            return

        try:
            token = get_access_token(self.runtime.credentials["app_key"], self.runtime.credentials["app_secret"])
            if not user_id:
                data = post_old_api("/topapi/v2/user/getbymobile", token, {"mobile": mobile})
                user_id = ((data.get("result") or {}).get("userid") or "").strip()
                if not user_id:
                    yield self.create_text_message(f"错误：手机号 {mobile} 未查到 userid（需与通讯录登记一致）。")
                    return
            detail = get_user_detail(token, user_id)
        except DingTalkError as e:
            yield self.create_text_message(f"查询用户部门失败：{e}")
            return
        except Exception as e:
            yield self.create_text_message(f"查询用户部门失败：{e}")
            return

        dept_ids = [str(d) for d in (detail.get("dept_id_list") or [])]
        joined = ",".join(dept_ids)
        yield self.create_variable_message("dept_ids", joined)
        yield self.create_variable_message("user_id", user_id)
        yield self.create_json_message(
            {
                "userid": user_id,
                "name": detail.get("name") or "",
                "job_number": detail.get("job_number") or "",
                "title": detail.get("title") or "",
                "mobile": detail.get("mobile") or "",
                "dept_id_list": detail.get("dept_id_list") or [],
            }
        )
        yield self.create_text_message(joined or f"用户 {user_id} 没有部门信息。")
