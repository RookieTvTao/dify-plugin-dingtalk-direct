from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _utils.dingtalk_client import DingTalkError, get_access_token, post_old_api, split_ids


class GetUseridByMobileTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        mobiles = split_ids(tool_parameters.get("mobiles", ""))
        if not mobiles:
            yield self.create_text_message("错误：mobiles 为空，请提供至少一个手机号。")
            return

        try:
            token = get_access_token(self.runtime.credentials["app_key"], self.runtime.credentials["app_secret"])
        except DingTalkError as e:
            yield self.create_text_message(f"获取 accessToken 失败：{e}")
            return
        except Exception as e:
            yield self.create_text_message(f"获取 accessToken 失败：{e}")
            return

        userids: dict[str, str] = {}
        failed: dict[str, str] = {}
        for mobile in mobiles:
            try:
                data = post_old_api("/topapi/v2/user/getbymobile", token, {"mobile": mobile})
                userid = (data.get("result") or {}).get("userid")
                if userid:
                    userids[mobile] = userid
                else:
                    failed[mobile] = "返回中没有 userid"
            except DingTalkError as e:
                # 60121 etc.: not found in the address book or number mismatch.
                failed[mobile] = str(e)
            except Exception as e:
                failed[mobile] = str(e)

        # Keep text/variable outputs as pure comma-separated userids so they can be wired
        # straight into the user_ids parameter of the send tools; the mobile->userid
        # mapping and failure reasons live in the json output.
        joined = ",".join(userids.values())
        yield self.create_variable_message("user_ids", joined)
        yield self.create_variable_message("failed", ",".join(failed.keys()))
        yield self.create_json_message({"userids": userids, "failed": failed})
        if joined:
            yield self.create_text_message(joined)
        else:
            yield self.create_text_message("查询失败：未取得任何 userid，原因见 json 输出的 failed 字段。")
