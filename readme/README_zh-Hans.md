# 钉钉个人消息（Dify 插件）

给钉钉**个人**发消息的 Dify 插件。官方钉钉插件只封装了群机器人 Webhook，而 Webhook 只能发群，
本插件补上"发给个人"的能力，适合审批提醒、报告推送、告警私发等场景。

## 三个工具

| 工具 | 通道 | 前置条件 |
|---|---|---|
| 发送工作通知 | 接收者的「工作通知」会话 | 企业内部应用 AppKey/AppSecret + AgentId（消息通知权限默认已开通） |
| 机器人单聊私发 | 机器人与个人的单聊 | 应用配置机器人并开启单聊，凭据填 RobotCode（机器人的 AppKey） |
| 手机号换 userid | 查询工具 | 应用开通「根据手机号获取成员基本信息」权限（qyapi_get_member_by_mobile），手机号须与通讯录一致 |

查询工具的 `user_ids` / `text` 输出是**纯净的逗号分隔 userid**，直接连到发送节点的
`user_ids` 即可；手机号与 userid 的对应关系、失败原因在 `json` 输出里。

## 授权配置

在钉钉开发者后台（open-dev.dingtalk.com）创建**企业内部应用**，在「凭证与基础信息」页拿到：

- `AppKey` / `AppSecret` —— 必填，所有工具都用
- `AgentId` —— 工作通知必填
- `RobotCode` —— 机器人单聊必填，即应用所配机器人的 AppKey（不是群机器人的 webhook）

## 钉钉侧限制（重要）

- 工作通知：单次最多 5000 人；同一员工一天只能收到一条**内容相同**的通知；每个应用每天
  给每个员工最多 500 条；企业每分钟最多 5000 人接收。**超限后接口仍返回成功，但对方收不到。**
- 机器人单聊：单次最多 20 个 userid；返回的 `invalidStaffIdList` 表示未送达
  （常见原因：用户未开启与机器人的单聊、不在应用可见范围、userid 无效）。
- accessToken 进程内缓存，到期前 5 分钟自动刷新。

## 在工作流中使用

1. 「手机号换 userid」节点（可选）：把手机号变量转成 userid；
2. 「发送工作通知」或「机器人单聊私发」节点：userid 列表 + 内容（支持文本 / Markdown），
   直接引用上游 LLM 节点的输出作为消息内容。

社区版 1.16.1+ 与企业版通用（已在企业版 3.12.1 实测三工具通过）。

## 本地开发

```bash
pip install -r requirements.txt
python -m unittest discover tests
# 打包生成 dingtalk-direct.difypkg
dify plugin package ./dify-plugin-dingtalk-direct
```

MIT License。English documentation: [README.md](../README.md)
