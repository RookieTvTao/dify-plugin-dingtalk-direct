from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _utils.dingtalk_client import DingTalkError, get_access_token, post_old_api


class QuerySendResultTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        agent_id = (self.runtime.credentials.get("agent_id") or "").strip()
        if not agent_id or not agent_id.isdigit():
            yield self.create_text_message("错误：未配置数字型 AgentId（发送工作通知同款凭据），无法查询发送结果。")
            return
        task_id = (tool_parameters.get("task_id") or "").strip()
        if not task_id.isdigit():
            yield self.create_text_message("错误：task_id 为空或不是数字（取发送时返回的 task_id）。")
            return

        try:
            token = get_access_token(self.runtime.credentials["app_key"], self.runtime.credentials["app_secret"])
            body = {"agent_id": int(agent_id), "task_id": int(task_id)}
            progress = post_old_api("/topapi/message/corpconversation/getsendprogress", token, body)
            result = post_old_api("/topapi/message/corpconversation/getsendresult", token, body)
        except DingTalkError as e:
            yield self.create_text_message(f"查询发送结果失败：{e}")
            return
        except Exception as e:
            yield self.create_text_message(f"查询发送结果失败：{e}")
            return

        progress_result = progress.get("result") or {}
        send_result = result.get("result") or {}
        # Field presence/types vary by server version; surface what exists, defensively.
        raw_invalid = send_result.get("invalid_user_id_list") or send_result.get("invalidUseridList") or []
        if isinstance(raw_invalid, str):
            invalid = [v.strip() for v in raw_invalid.split(",") if v.strip()]
        else:
            invalid = [str(u) for u in raw_invalid]
        invalid_str = ",".join(str(u) for u in invalid)
        yield self.create_variable_message("invalid_user_ids", invalid_str)
        yield self.create_json_message({"task_id": int(task_id), "progress": progress_result, "result": send_result})

        lines = [f"task_id={task_id}"]
        for key in ("totalCount", "total_count", "sentCount", "sent_count", "progressIn1000", "progress_in_1000"):
            if key in progress_result:
                lines.append(f"{key}={progress_result[key]}")
        if invalid:
            lines.append(f"未送达/无效 userid：{invalid_str}")
        lines.append("逐人状态等明细见 json 输出。")
        yield self.create_text_message("；".join(lines))
