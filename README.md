# Coopet 桌宠适配器（MaiBot 插件）

让麦麦住到你的电脑桌面上。

这个插件是 [Coopet](https://github.com/wtxdew/coopet-maibot) 桌宠和 MaiBot 之间的桥：在 MaiBot 里自起一个 WebSocket 服务，
桌宠连上来后，你在桌宠里说的话作为"主人在 coopet 平台的私聊"交给 MaiBot，麦麦的回复和思考状态推回桌宠，
在气泡、表情和动作里显示出来。

> 状态：可用（v0.1）。在 MaiBot 1.4.3 上实际运行：聊天往返、思考状态、Bot 名字。

## Coopet 是什么

Coopet 是一个 Mac / Windows 的桌宠客户端。它基于 [Coopanion](https://github.com/Pal-AI-Lab/Coopanion)
（Pal-AI-Lab 的 AI 桌宠）：把 Coopanion 的桌宠形象、换装、互动、音效和设置界面单独拆出来，
去掉它自带的模型，改成连 MaiBot，**由麦麦当桌宠的大脑**。

- **麦麦还是那个麦麦**：名字、人设、记忆、回复风格都按 MaiBot 自己的设置，桌宠只是麦麦在桌面上的一个新"平台"。
  在 QQ 上和在桌面上，是同一个麦麦。
- **桌宠有自己的身体**：麦麦思考时桌宠做思考动作，回复按语气配上表情；戳、摸、甩这类互动桌宠在本地直接反应。
- **可以扩展**：桌宠端能加载 [Cortico](https://github.com/Pal-AI-Lab/Cortico) 格式的 **World 扩展**，
  给桌宠接上新的本地能力。内置一个 Coding Agent 完成通知（来自
  [ThermalEng/coopanion-agent-notify-world](https://github.com/ThermalEng/coopanion-agent-notify-world)）：
  Claude Code、Codex 等跑完一轮任务后，桌宠会告诉你。World 扩展就是一个 npm 包，可以自己写，
  Coopet 用 Cortico 的契约加载和托管它。
- **以后**：本地 Agent（对麦麦说"帮我打开某某"，由电脑上的 Agent 执行）、外部通知、电脑操作等，
  见 Coopet 的 [ROADMAP](https://github.com/wtxdew/coopet-maibot/blob/master/docs/ROADMAP.md)。

```
┌────────── 你的电脑 ──────────┐                 ┌──────── MaiBot 所在主机 ────────┐
│  Coopet 桌宠                  │   WebSocket     │  本插件  ⇄  消息网关  ⇄  MaiBot  │
│  （形象、气泡、World 扩展）   │ ◀────────────▶ │  （协议 v0）                     │
└───────────────────────────────┘   局域网 / VPN  └──────────────────────────────────┘
```

桌宠客户端的下载、安装和使用见 [Coopet](https://github.com/wtxdew/coopet-maibot)。

## 要求

- MaiBot 1.4.x（≥ 1.4.3），插件 SDK ≥ 2.22.0
- 桌宠所在的电脑能访问到 MaiBot 所在主机的插件端口（同一局域网，或 Tailscale 这类私有网络）
- 同一时间只连一台桌宠设备：新设备连上时会顶替旧的

## 安装

1. 安装插件：在 MaiBot WebUI 的插件市场安装；或者把本仓库克隆到 MaiBot 的插件目录（`<MaiBot>/plugins/` 下）。
2. **Docker 部署才需要**：在 docker-compose 的 MaiBot 服务里映射插件端口（默认 18100），然后重建容器
   （`docker compose up -d <服务名>`；只 `docker restart` 不会让新的端口映射生效）：
   ```yaml
   ports:
     - "18100:18100"
   ```
   Windows / macOS 直接部署不用做这一步。
3. 在 MaiBot WebUI 的插件页打开本插件设置：
   - 「连接」：填一个 token（桌宠客户端要填同一个）；端口按需修改；
   - 「身份」：主人的 user_id 和称呼（麦麦怎么称呼你）；
   - 「插件」：打开启用。
4. 在 Coopet 的设置窗「开始 → 连接 MaiBot」里填地址 `ws://<MaiBot 所在主机>:18100/ws` 和同一个 token，点「保存并连接」。

**安全**：只在局域网或 Tailscale 这类私有网络里使用，不要把端口暴露到公网（v0 协议不加密，只靠 token 认证）。

## 协议

客户端和插件之间的协议见 [PROTOCOL.md](PROTOCOL.md)：JSON 文本帧，握手（token、协议版本）、发消息、收回复、思考状态。
协议不绑定 Coopet，想给别的客户端（其他桌宠、命令行、小工具）接 MaiBot，照它实现客户端即可。

## 开发

```bash
uv sync --python 3.13
uv run pytest
```

`pyproject.toml` 只用于本地开发和测试，MaiBot 装插件时只读 `_manifest.json`。

## 来源与许可

AGPL-3.0-or-later，见 [LICENSE](LICENSE)。本插件是 [Coopet](https://github.com/wtxdew/coopet-maibot) 项目的一部分，
从它的仓库拆出来单独发布（保留了提交历史）。
