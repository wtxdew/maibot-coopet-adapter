"""客户端消息与 MaiBot 网关消息之间的格式转换。纯函数，不依赖网络和 SDK。

- 入站：协议的 `chat`、`notice` → `ctx.gateway.route_message` 要的消息字典
  （必填字段见 MaiBot src/plugin_runtime/host/message_utils.py `_build_session_message_from_dict`）。
- 出站：网关交给插件的消息字典（`raw_message` 是段的列表）→ 协议的 `reply`。
  图片、表情包段的字节在 `binary_data_base64`，`data` 是描述文字。
"""

from __future__ import annotations

import base64
import binascii
from typing import Any, Dict, List, Mapping, Optional

from .protocol import Chat, Notice, reply

PLATFORM = "coopet"


def chat_to_inbound(chat: Chat, *, account_id: str, user_id: str, user_nickname: str, now: float) -> Dict[str, Any]:
    """主人在 coopet 平台的一条私聊文字消息。message_id 用客户端给的 chat.id。"""
    return _private_text(chat.id, chat.text, account_id=account_id, user_id=user_id, user_nickname=user_nickname, now=now)


def notice_intent(notice: Notice, owner: str) -> str:
    """交给 Maisaka 主动任务的意图：写明这是电脑上收到的外部通知、不是主人说的话；转告时要说清从哪来、发生了什么，
    不然通知就没用了。`owner` 是麦麦对主人的称呼（插件设置）。"""
    title = f"，标题「{notice.title}」" if notice.title else ""
    return (
        f"{owner}电脑上的 Coopet 收到一条外部通知（不是{owner}发来的消息）：来源「{notice.source}」{title}，内容「{notice.text}」。"
        f"如果{owner}可能需要知道，就转告他：一定要说清这是哪里来的通知、发生了什么（保留原文里的名称、项目、"
        "结果这些关键词，不要只说个大概），说清之后可以加一句你自己的看法；不重要就不用说。"
    )


def notice_text(notice: Notice, owner: str) -> str:
    """退回成通知消息时的正文：照 MaiBot 通知消息的写法以「[事件-…]」开头（自带的 Telegram 适配器也这样写），
    用第三人称写明这是外部推送。消息的发送者只能是主人，planner 会在前面加上主人的名字，所以要说清不是主人说的。"""
    head = f"{notice.source}：{notice.title}" if notice.title else notice.source
    return f"[事件-通知] {owner}电脑上的 Coopet 收到一条外部推送（不是{owner}说的）—— {head}：{notice.text}"


def notice_to_inbound(notice: Notice, *, account_id: str, user_id: str, user_nickname: str, now: float) -> Dict[str, Any]:
    """桌宠转来的通知：主人私聊里的一条**通知消息**（is_notify）。MaiBot 照常交给 planner，由她决定要不要回；
    恢复上下文时会跳过通知消息，所以不会占着聊天记录。message_id 用客户端给的 notice.id。"""
    message = _private_text(notice.id, notice_text(notice, user_nickname), account_id=account_id, user_id=user_id, user_nickname=user_nickname, now=now)
    message["is_notify"] = True
    return message


def _private_text(message_id: str, text: str, *, account_id: str, user_id: str, user_nickname: str, now: float) -> Dict[str, Any]:
    return {
        "platform": PLATFORM,
        "account_id": account_id,
        "scope": None,
        "message_id": message_id,
        "timestamp": str(now),
        "message_info": {
            "user_info": {"user_id": user_id, "user_nickname": user_nickname},
            "additional_config": {},
        },
        "raw_message": [{"type": "text", "data": text}],
        "is_at": False,
        "is_mentioned": False,
        "is_picture": False,
        "is_emoji": False,
        "is_command": False,
    }


def outbound_to_reply(message: Mapping[str, Any]) -> Dict[str, Any]:
    """网关出站消息 → reply 帧。raw_message 不是列表时抛 ValueError。"""
    segments = message.get("raw_message")
    if not isinstance(segments, list):
        raise ValueError("出站消息的 raw_message 必须是列表")
    message_id = message.get("message_id")
    return reply(message_id if isinstance(message_id, str) else "", segments_to_parts(segments))


def segments_to_parts(segments: List[Any]) -> List[Dict[str, Any]]:
    parts: List[Dict[str, Any]] = []
    for seg in segments:
        if not isinstance(seg, Mapping):
            continue
        kind = seg.get("type")
        if kind == "text" and isinstance(seg.get("data"), str):
            parts.append({"kind": "text", "text": seg["data"]})
        elif kind in ("image", "emoji") and isinstance(seg.get("binary_data_base64"), str) and seg["binary_data_base64"]:
            part: Dict[str, Any] = {"kind": kind, "base64": seg["binary_data_base64"]}
            mime = sniff_image_mime(seg["binary_data_base64"])
            if mime:
                part["mime"] = mime
            parts.append(part)
        else:
            parts.append({"kind": "other", "type": str(kind)})
    return parts


def outbound_target_user(message: Mapping[str, Any]) -> Optional[str]:
    """私聊出站消息的目标用户（MaiBot 写在 additional_config.platform_io_target_user_id）。"""
    info = message.get("message_info")
    config = info.get("additional_config") if isinstance(info, Mapping) else None
    target = config.get("platform_io_target_user_id") if isinstance(config, Mapping) else None
    return str(target) if target is not None else None


_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def sniff_image_mime(b64: str) -> Optional[str]:
    """按文件头猜图片类型；认不出时返回 None。只解码开头一小段。"""
    try:
        head = base64.b64decode(b64[:24] + "=" * (-len(b64[:24]) % 4), validate=False)
    except (binascii.Error, ValueError):
        return None
    for sig, mime in _SIGNATURES:
        if head.startswith(sig):
            return mime
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None
