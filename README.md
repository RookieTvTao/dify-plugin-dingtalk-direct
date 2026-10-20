# DingTalk Direct Message

A Dify plugin that sends DingTalk messages **to individuals** — something the official
DingTalk group-robot plugin cannot do, because a group robot webhook can only post into a group.

- Source repository: <https://github.com/RookieTvTao/dify-plugin-dingtalk-direct>
- Chinese documentation: [readme/README_zh-Hans.md](readme/README_zh-Hans.md)

## Tools

| Tool | Channel | Requirements |
|---|---|---|
| Send Work Notification | Work notification conversation | Enterprise internal app: AppKey/AppSecret + AgentId |
| Send Robot Message | Robot one-on-one chat | The app's robot (RobotCode) with one-on-one chat enabled |
| Get Userid by Mobile | - (lookup) | Address-book read permission `qyapi_get_member_by_mobile` |
| Get Department Users | - (lookup) | Address-book read permission `qyapi_get_department_member` |
| List Departments | - (lookup) | Address-book read permission `qyapi_get_department_list` |

## Setup

1. On the DingTalk Open Platform (open-dev.dingtalk.com) create an **enterprise internal app**.
   Copy its `AppKey`, `AppSecret` and `AgentId` from the credentials page.
2. For **work notifications**: the message-notification permission is granted to internal apps by
   default — no extra application needed.
3. For **robot one-on-one messages**: add the robot capability to the same app, enable
   one-on-one chat, and grant the "robot sends messages inside the enterprise" permission.
   The `RobotCode` is simply the robot's AppKey.
4. For **mobile → userid lookup**: grant the address-book permission above. The mobile number
   must match the enterprise address book.

### Connection requirements

Authorize the plugin once with `AppKey` / `AppSecret`; `AgentId` (work notifications) and
`RobotCode` (robot direct messages) are optional provider-level fields required by the
respective tools. All outbound traffic goes to `api.dingtalk.com` and `oapi.dingtalk.com`
only (declared in `manifest.yaml` → `network.domains`).

### Rate limits (DingTalk side)

- Work notification: ≤ 5000 recipients per call; one identical message per employee per day;
  ≤ 500 messages per employee per app per day; 5000 recipients per minute enterprise-wide.
  **When a limit is exceeded the API still returns success but the user receives nothing.**
- Robot direct message: ≤ 20 userIds per call.
- Access tokens are cached in-process until 5 minutes before expiry.

### Output wiring

All lookup tools share the same convention: `text` and the `user_ids` (or `dept_ids`)
output variables are pure comma-separated ids, ready to be wired straight into the send
tools' `user_ids` parameter; names, mobiles and failure reasons live in the `json` output.
`Get Department Users` accepts comma-separated dept ids (wire the `dept_ids` output of
`List Departments` straight in), can walk sub-departments recursively (capped at 100
departments / 5000 users) and filter members by name substring.

## Field-tested

Dify Enterprise 3.12.1 (= Community 1.16.1): all three tools verified end-to-end with real
enterprise credentials.

## Development

```bash
pip install -r requirements.txt
python -m unittest discover tests
# package (produces a .difypkg)
dify plugin package ./dify-plugin-dingtalk-direct
```

Group-robot sending is covered by the official `langgenius/dingtalk` plugin; this plugin
complements it for direct, person-to-person delivery. MIT License — see [LICENSE](LICENSE).
