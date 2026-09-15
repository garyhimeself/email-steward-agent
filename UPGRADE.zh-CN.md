# 升级指南

## 旧 Skill 名称

`business-email-managerment` 是历史拼写错误。它会保留为兼容入口，已有引用可以继续工作；所有新指令请使用 `business-email-management`。

## 安全升级

1. 下载并解压新版发布包到原工作区以外的位置；不要把密码或 `.email-steward` 数据复制到发布包文件夹。
2. 在新版发布包文件夹中运行：`installer\install_agent.bat --upgrade-workspace --workspace "C:\你的\原工作区路径"`。它只更新公开 Agent 文件，保留本地配置、系统凭据和操作者的其他文件。
3. 在原工作区重新打开 Codex 项目。第一次邮件操作会运行 `python installer/mail_runtime.py credential-status --workspace .`；看到 `credential_ready` 后，不要再次输入安全码。
4. 若状态为 `credential_missing`，请在工作区运行：`installer\install_agent.bat --secure-window --repair-credential --workspace "."`。只有独立隐藏安全窗口接收第三方客户端安全码，原工作区不会被覆盖。
5. 读取使用 Luna、低推理；撰写使用 Terra、低推理加 `humanizer`。完成一次只读邮件查询和一次不发送的草稿；不要发送测试邮件。
