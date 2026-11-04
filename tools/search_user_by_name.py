from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from _utils.dingtalk_client import DingTalkError, get_access_token, post_new_api, to_bool

PAGE_SIZE = 100


class SearchUserByNameTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        query_word = (tool_parameters.get("query_word") or "").strip()
        if not query_word:
            yield self.create_text_message("错误：query_word 为空，请提供姓名/拼音关键词。")
            return
        full_match = to_bool(tool_parameters.get("full_match"))
        body: dict[str, Any] = {"queryWord": query_word, "offset": 0, "size": PAGE_SIZE}
        if full_match:
            body["fullMatchField"] = 1

        try:
            token = get_access_token(self.runtime.credentials["app_key"], self.runtime.credentials["app_secret"])
            data = post_new_api("/v1.0/contact/users/search", token, body)
        except DingTalkError as e:
            msg = str(e)
            if "60011" in msg or "权限" in msg or "Forbidden" in msg:
                msg += "。请到 开发者后台→权限管理 开通「搜索企业通讯录 qyapi_addresslist_search」权限"
            yield self.create_text_message(f"按姓名搜索失败：{msg}")
            return
        except Exception as e:
            yield self.create_text_message(f"按姓名搜索失败：{e}")
            return

        users = data.get("users") or (data.get("result") or {}).get("users") or []
        matched = [
            {"userid": u.get("userid") or u.get("userId") or "", "name": u.get("name") or ""}
            for u in users
            if (u.get("userid") or u.get("userId"))
        ]
        joined = ",".join(u["userid"] for u in matched)
        has_more = bool(data.get("hasMore") or (data.get("result") or {}).get("hasMore"))
        yield self.create_variable_message("user_ids", joined)
        yield self.create_variable_message("count", len(matched))
        yield self.create_json_message({"count": len(matched), "has_more": has_more, "users": matched})
        if joined:
            note = f"（共 {len(matched)} 人，均按匹配度排序）" if len(matched) > 1 else ""
            yield self.create_text_message(joined + note)
        else:
            yield self.create_text_message(
                f"未搜索到匹配「{query_word}」的成员（搜索范围=应用通讯录权限范围；关键词需为姓名/拼音/英文名）"
            )
