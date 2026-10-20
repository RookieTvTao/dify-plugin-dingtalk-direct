from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _utils.dingtalk_client import (
    DingTalkError,
    build_robot_msg,
    get_access_token,
    post_new_api,
    split_ids,
)

MAX_USER_IDS = 20


class SendRobotMessageTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        robot_code = (self.runtime.credentials.get("robot_code") or "").strip()
        if not robot_code:
            yield self.create_text_message(
                "错误：未配置 RobotCode。请在「钉钉个人消息」插件授权中填写应用所配机器人的 AppKey（企业内部开发-机器人）。"
            )
            return
        user_ids = split_ids(tool_parameters.get("user_ids", ""))
        if not user_ids:
            yield self.create_text_message("错误：user_ids 为空，请提供至少一个接收者 userid。")
            return
        if len(user_ids) > MAX_USER_IDS:
            yield self.create_text_message(f"错误：接收者数量 {len(user_ids)} 超过单次上限 {MAX_USER_IDS}。")
            return
        content = tool_parameters.get("content") or ""
        if not content.strip():
            yield self.create_text_message("错误：content 为空。")
            return
        message_type = tool_parameters.get("message_type") or "text"

        msg_key, msg_param = build_robot_msg(message_type, tool_parameters.get("title") or "", content)
        try:
            token = get_access_token(self.runtime.credentials["app_key"], self.runtime.credentials["app_secret"])
            data = post_new_api(
                "/v1.0/robot/oToMessages/batchSend",
                token,
                {"robotCode": robot_code, "userIds": user_ids, "msgKey": msg_key, "msgParam": msg_param},
            )
        except DingTalkError as e:
            yield self.create_text_message(f"机器人单聊发送失败：{e}")
            return
        except Exception as e:
            yield self.create_text_message(f"机器人单聊发送失败：{e}")
            return

        invalid = data.get("invalidStaffIdList") or []
        flow_limited = data.get("flowControlledStaffIdList") or []
        yield self.create_json_message(
            {
                "process_query_key": data.get("processQueryKey"),
                "invalid_staff_ids": invalid,
                "flow_controlled_staff_ids": flow_limited,
                "user_ids": user_ids,
                "message_type": message_type,
            }
        )
        summary = f"机器人单聊已发送，接收 {len(user_ids) - len(invalid)} 人。"
        if invalid:
            summary += (
                f"以下 userid 未送达（可能未开启与机器人的单聊、不在应用可见范围或 userid 无效）：{','.join(invalid)}。"
            )
        if flow_limited:
            summary += f"以下 userid 被限流，稍后重试：{','.join(flow_limited)}。"
        yield self.create_text_message(summary)
