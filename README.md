# DingTalk Direct Message | 钉钉个人消息

A Dify plugin that sends DingTalk messages **to individuals** — something the official
DingTalk group-robot plugin cannot do, because a group robot webhook can only post into a group.

- [English](#english)
- [中文说明](README_CN.md)

## English

### Tools

| Tool | Channel | Requirements |
|---|---|---|
| Send Work Notification | Work notification conversation ("工作通知") | Enterprise internal app: AppKey/AppSecret + AgentId |
| Send Robot Message | Robot one-on-one chat | The app's robot (RobotCode) with one-on-one enabled |
| Get Userid by Mobile | - (lookup) | Address-book read permission |

### Setup

1. On [DingTalk Open Platform](https://open-dev.dingtalk.com) create an **enterprise internal app**
   (企业内部应用 / H5 micro-app). Copy its `AppKey`, `AppSecret` and `AgentId` from the
   credentials page.
2. For **work notifications**: the message-notification permission is granted to internal apps by
   default — no extra application needed.
3. For **robot one-on-one messages**: add the robot capability to the same app, enable
   one-on-one chat (单聊), and grant the "企业内机器人发送消息" permission. The `RobotCode` is
   simply the robot's AppKey.
4. For **mobile → userid lookup**: grant the address-book personal-info read permission
   (通讯录个人信息读权限) to the app. The mobile number must match the enterprise address book.
5. In Dify: install the plugin, then authorize with AppKey/AppSecret (AgentId and RobotCode
   optional, required by the respective tools).

### Rate limits (DingTalk side)

- Work notification: ≤ 5000 recipients per call; one identical message per employee per day;
  ≤ 500 messages per employee per app per day; 5000 recipients per minute enterprise-wide.
  **When a limit is exceeded the API still returns success but the user receives nothing.**
- Robot direct message: ≤ 20 userIds per call.
- Access tokens are cached in-process until 5 minutes before expiry.

### Development

```bash
pip install -r requirements.txt
python -m unittest discover tests
# package (produces dingtalk-direct.difypkg)
dify plugin package ./dify-plugin-dingtalk-direct
```

## Related

- Group-robot sending is covered by the official `langgenius/dingtalk` plugin; this plugin
  complements it for direct, person-to-person delivery.
- MIT License.
