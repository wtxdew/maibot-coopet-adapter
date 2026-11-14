"""协议 v0 的常量、解析与组帧（PROTOCOL.md）。不依赖网络和 SDK，纯函数。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

PROTOCOL_VERSION = 0

# 单帧上限，与 MaiBot 插件网关的帧上限一致（PROTOCOL.md §1）
MAX_FRAME_BYTES = 16 * 1024 * 1024
# 连接后多久没收到 hello 就关闭（§3）
HELLO_TIMEOUT_SEC = 10.0
# 思考状态的兜底超时（§4）
THINKING_TIMEOUT_SEC = 120.0

# 服务端支持的可选消息，写在 welcome.features 里（§3）；客户端看到才发
FEATURE_NOTICE = "notice"
# notice 各字段的长度上限（§4）
MAX_NOTICE_SOURCE = 64
MAX_NOTICE_TITLE = 200
MAX_NOTICE_TEXT = 2000

# 关闭码（§5）
CLOSE_NORMAL = 1000
CLOSE_UNSUPPORTED_DATA = 1003
CLOSE_TOO_BIG = 1009
CLOSE_HANDSHAKE = 4000
CLOSE_UNAUTHORIZED = 4001
CLOSE_PROTOCOL_UNSUPPORTED = 4002
CLOSE_REPLACED = 4003

# 错误码（§6）
ERR_HANDSHAKE = "handshake"
ERR_UNAUTHORIZED = "unauthorized"
ERR_PROTOCOL_UNSUPPORTED = "protocol_unsupported"
ERR_REPLACED = "replaced"
ERR_INVALID = "invalid"
ERR_NOT_READY = "not_ready"
ERR_REJECTED = "rejected"


class ProtocolError(Exception):
    """收到的帧不合协议。`ack_id` 不为空时应回 ack 失败，否则回 error 帧。"""

    def __init__(self, code: str, message: str, ack_id: Optional[str] = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.ack_id = ack_id


@dataclass(frozen=True)
class Hello:
    protocol: int
    token: str
    device_id: str
    device_name: str
    client_name: str
    client_version: str


@dataclass(frozen=True)
class Chat:
    id: str
    text: str


@dataclass(frozen=True)
class Notice:
    """桌宠转来的一条通知（例如 ntfy、Coding Agent 跑完了），交给 MaiBot 由她决定要不要说。"""
    id: str
    source: str
    text: str
    title: Optional[str] = None


def parse_frame(raw: str) -> Dict[str, Any]:
    """把一个文本帧解析成带 `type` 的对象；不合格时抛 ProtocolError(invalid)。"""
    try:
        obj = json.loads(raw)
    except ValueError as exc:
        raise ProtocolError(ERR_INVALID, f"不是合法的 JSON：{exc}") from exc
    if not isinstance(obj, dict):
        raise ProtocolError(ERR_INVALID, "帧必须是 JSON 对象")
    if not isinstance(obj.get("type"), str) or not obj["type"]:
        raise ProtocolError(ERR_INVALID, "缺少 type")
    return obj


def parse_hello(obj: Dict[str, Any]) -> Hello:
    """第一帧必须是 hello；不是 hello 或字段不对时抛 ProtocolError(handshake)。

    这里只检查格式；token 与协议版本由服务端比对。
    """
    if obj.get("type") != "hello":
        raise ProtocolError(ERR_HANDSHAKE, "第一帧必须是 hello")
    protocol = obj.get("protocol")
    if not isinstance(protocol, int) or isinstance(protocol, bool):
        raise ProtocolError(ERR_HANDSHAKE, "hello.protocol 必须是整数")
    for key in ("token", "device_id", "device_name"):
        if not isinstance(obj.get(key), str):
            raise ProtocolError(ERR_HANDSHAKE, f"hello.{key} 必须是字符串")
    client = obj.get("client") if isinstance(obj.get("client"), dict) else {}
    return Hello(
        protocol=protocol,
        token=obj["token"],
        device_id=obj["device_id"],
        device_name=obj["device_name"],
        client_name=str(client.get("name", "")),
        client_version=str(client.get("version", "")),
    )


def parse_chat(obj: Dict[str, Any]) -> Chat:
    """解析 chat。id 合格但 text 不合格时，异常带 ack_id，好回 ack 失败。"""
    chat_id = obj.get("id")
    if not isinstance(chat_id, str) or not chat_id:
        raise ProtocolError(ERR_INVALID, "chat.id 必须是非空字符串")
    text = obj.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ProtocolError(ERR_INVALID, "chat.text 必须是非空字符串", ack_id=chat_id)
    return Chat(id=chat_id, text=text.strip())


def parse_notice(obj: Dict[str, Any]) -> Notice:
    """解析 notice。id 合格但其他字段不合格时，异常带 ack_id，好回 ack 失败。"""
    notice_id = obj.get("id")
    if not isinstance(notice_id, str) or not notice_id:
        raise ProtocolError(ERR_INVALID, "notice.id 必须是非空字符串")

    def text_field(key: str, limit: int, required: bool) -> Optional[str]:
        value = obj.get(key)
        if value is None and not required:
            return None
        if not isinstance(value, str) or (required and not value.strip()):
            raise ProtocolError(ERR_INVALID, f"notice.{key} 必须是非空字符串", ack_id=notice_id)
        value = value.strip()
        if len(value) > limit:
            raise ProtocolError(ERR_INVALID, f"notice.{key} 最多 {limit} 个字", ack_id=notice_id)
        return value or None

    source = text_field("source", MAX_NOTICE_SOURCE, True)
    text = text_field("text", MAX_NOTICE_TEXT, True)
    title = text_field("title", MAX_NOTICE_TITLE, False)
    assert source is not None and text is not None
    return Notice(id=notice_id, source=source, text=text, title=title)


# ---------- 组帧（服务端 → 客户端） ----------

def welcome(
    *, bot_name: str, bot_account_id: str, user_id: str, user_nickname: str, features: Sequence[str] = (),
) -> Dict[str, Any]:
    return {
        "type": "welcome",
        "protocol": PROTOCOL_VERSION,
        "bot": {"name": bot_name, "account_id": bot_account_id},
        "user": {"id": user_id, "nickname": user_nickname},
        "features": list(features),
    }


def ack_ok(chat_id: str) -> Dict[str, Any]:
    return {"type": "ack", "id": chat_id, "ok": True}


def ack_error(chat_id: str, code: str, message: str) -> Dict[str, Any]:
    return {"type": "ack", "id": chat_id, "ok": False, "error": {"code": code, "message": message}}


def reply(message_id: str, parts: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"type": "reply", "id": message_id, "parts": parts}


def thinking(on: bool) -> Dict[str, Any]:
    return {"type": "thinking", "on": on}


def error(code: str, message: str) -> Dict[str, Any]:
    return {"type": "error", "code": code, "message": message}


def encode(frame: Dict[str, Any]) -> str:
    """组好的帧转成文本帧；保留中文原样，不转义成 \\uXXXX。"""
    return json.dumps(frame, ensure_ascii=False, separators=(",", ":"))
