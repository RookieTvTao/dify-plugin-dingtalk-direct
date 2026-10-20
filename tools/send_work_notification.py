from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _utils.dingtalk_client import (
    DingTalkError,
    build_work_msg,
    check_content_size,
    get_access_token,
    post_old_api,
    split_ids,
)

MAX_USER_IDS = 100


class SendWorkNotificationTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        agent_id = (self.runtime.credentials.get("agent_id") or "").strip()
        if not agent_id:
            yield self.create_text_message(
                "错误：未配置 AgentId。请在「钉钉个人消息」插件授权中填写企业内部应用的 AgentId。"
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

        try:
            if not agent_id.isdigit():
                raise ValueError("AgentId 必须是纯数字")
            check_content_size(content)
            msg = build_work_msg(message_type, tool_parameters.get("title") or "", content)
            token = get_access_token(self.runtime.credentials["app_key"], self.runtime.credentials["app_secret"])
            data = post_old_api(
                "/topapi/message/corpconversation/asyncsend_v2",
                token,
                {
                    "agent_id": int(agent_id),
                    "userid_list": ",".join(user_ids),
                    "to_all_user": False,
                    "msg": msg,
                },
            )
        except DingTalkError as e:
            yield self.create_text_message(f"发送工作通知失败：{e}")
            return
        except ValueError as e:
            yield self.create_text_message(f"发送工作通知失败：{e}")
            return
        except Exception as e:
            yield self.create_text_message(f"发送工作通知失败：{e}")
            return

        yield self.create_json_message(
            {"task_id": data.get("task_id"), "user_ids": user_ids, "message_type": message_type}
        )
        yield self.create_text_message(
            f"工作通知已提交（task_id={data.get('task_id')}），接收 {len(user_ids)} 人。"
            "注意：同一员工一天内只能收到一条内容相同的通知；超频时钉钉仍返回成功但对方收不到。"
        )
