# Privacy Policy

This plugin runs inside your own Dify instance and calls the DingTalk Open Platform APIs
directly from the plugin runtime:

- `https://api.dingtalk.com/v1.0/oauth2/accessToken` - exchange AppKey/AppSecret for an access token
- `https://oapi.dingtalk.com/topapi/message/corpconversation/asyncsend_v2` - send work notifications
- `https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend` - send robot one-on-one messages
- `https://oapi.dingtalk.com/topapi/v2/user/getbymobile` - look up userid by mobile number

What the plugin processes:

- Credentials (AppKey, AppSecret, AgentId, RobotCode) are stored encrypted by Dify and used
  only to authenticate against the DingTalk APIs above. They are never sent anywhere else.
- Message content, recipient userids and mobile numbers are passed through to DingTalk as
  request payloads and are not stored, logged or shared with any third party.

The plugin does not collect analytics, does not write persistent storage, and only talks to
the official DingTalk API domains listed above.
