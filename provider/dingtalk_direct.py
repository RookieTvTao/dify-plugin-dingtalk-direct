from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from _utils.dingtalk_client import DingTalkError, get_access_token


class DingTalkDirectProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict) -> None:
        # Fetching a token is a cheap, side-effect-free way to prove AppKey/AppSecret.
        try:
            get_access_token(credentials["app_key"], credentials["app_secret"])
        except DingTalkError as e:
            raise ToolProviderCredentialValidationError(f"获取 accessToken 失败，请检查 AppKey/AppSecret：{e}")
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e))
