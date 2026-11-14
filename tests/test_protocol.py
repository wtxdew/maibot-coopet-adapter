import json

import pytest

from coopet_adapter import protocol as p


def hello(**over):
    base = {"type": "hello", "protocol": 0, "token": "t", "device_id": "d1", "device_name": "Mac", "client": {"name": "coopet", "version": "0.0.0"}}
    base.update(over)
    return base


class TestParseFrame:
    def test_ok(self):
        assert p.parse_frame('{"type":"chat","id":"a"}') == {"type": "chat", "id": "a"}

    @pytest.mark.parametrize("raw", ["not json", "[1,2]", '"x"', '{"id":"a"}', '{"type":""}', '{"type":3}'])
    def test_invalid(self, raw):
        with pytest.raises(p.ProtocolError) as e:
            p.parse_frame(raw)
        assert e.value.code == p.ERR_INVALID


class TestParseHello:
    def test_ok(self):
        h = p.parse_hello(hello())
        assert h == p.Hello(protocol=0, token="t", device_id="d1", device_name="Mac", client_name="coopet", client_version="0.0.0")

    def test_client_is_optional(self):
        h = p.parse_hello({k: v for k, v in hello().items() if k != "client"})
        assert (h.client_name, h.client_version) == ("", "")

    @pytest.mark.parametrize("obj", [
        {"type": "chat", "id": "a", "text": "hi"},
        hello(protocol="0"),
        hello(protocol=True),
        hello(token=None),
        hello(device_id=1),
        {k: v for k, v in hello().items() if k != "device_name"},
    ])
    def test_rejects(self, obj):
        with pytest.raises(p.ProtocolError) as e:
            p.parse_hello(obj)
        assert e.value.code == p.ERR_HANDSHAKE


class TestParseChat:
    def test_ok_and_trims(self):
        assert p.parse_chat({"type": "chat", "id": "a", "text": "  你好 "}) == p.Chat(id="a", text="你好")

    def test_missing_id_has_no_ack(self):
        with pytest.raises(p.ProtocolError) as e:
            p.parse_chat({"type": "chat", "text": "hi"})
        assert e.value.code == p.ERR_INVALID and e.value.ack_id is None

    @pytest.mark.parametrize("text", [None, "", "   ", 5])
    def test_bad_text_acks(self, text):
        with pytest.raises(p.ProtocolError) as e:
            p.parse_chat({"type": "chat", "id": "a", "text": text})
        assert e.value.code == p.ERR_INVALID and e.value.ack_id == "a"


class TestNotice:
    def test_parses_and_trims(self):
        n = p.parse_notice({"type": "notice", "id": "n1", "source": " ntfy · build ", "title": " CI ", "text": " 构建完成 "})
        assert n == p.Notice(id="n1", source="ntfy · build", text="构建完成", title="CI")

    def test_title_is_optional(self):
        assert p.parse_notice({"type": "notice", "id": "n1", "source": "s", "text": "t"}).title is None
        assert p.parse_notice({"type": "notice", "id": "n1", "source": "s", "text": "t", "title": "  "}).title is None

    @pytest.mark.parametrize("nid", [None, "", 3])
    def test_bad_id_is_an_error_frame(self, nid):
        with pytest.raises(p.ProtocolError) as e:
            p.parse_notice({"type": "notice", "id": nid, "source": "s", "text": "t"})
        assert e.value.code == p.ERR_INVALID and e.value.ack_id is None

    @pytest.mark.parametrize("over", [
        {"source": None}, {"source": "  "}, {"source": "x" * (p.MAX_NOTICE_SOURCE + 1)},
        {"text": None}, {"text": ""}, {"text": "x" * (p.MAX_NOTICE_TEXT + 1)},
        {"title": 5}, {"title": "x" * (p.MAX_NOTICE_TITLE + 1)},
    ])
    def test_bad_fields_ack(self, over):
        frame = {"type": "notice", "id": "n1", "source": "s", "text": "t", **over}
        with pytest.raises(p.ProtocolError) as e:
            p.parse_notice(frame)
        assert e.value.code == p.ERR_INVALID and e.value.ack_id == "n1"


class TestFrames:
    def test_welcome(self):
        assert p.welcome(bot_name="麦麦", bot_account_id="coopet-maibot", user_id="owner", user_nickname="主人") == {
            "type": "welcome", "protocol": 0,
            "bot": {"name": "麦麦", "account_id": "coopet-maibot"},
            "user": {"id": "owner", "nickname": "主人"},
            "features": [],
        }
        assert p.welcome(bot_name="麦麦", bot_account_id="a", user_id="o", user_nickname="n", features=[p.FEATURE_NOTICE])["features"] == ["notice"]

    def test_ack_reply_thinking_error(self):
        assert p.ack_ok("a") == {"type": "ack", "id": "a", "ok": True}
        assert p.ack_error("a", p.ERR_REJECTED, "x") == {"type": "ack", "id": "a", "ok": False, "error": {"code": "rejected", "message": "x"}}
        assert p.reply("m1", [{"kind": "text", "text": "hi"}]) == {"type": "reply", "id": "m1", "parts": [{"kind": "text", "text": "hi"}]}
        assert p.thinking(True) == {"type": "thinking", "on": True}
        assert p.error(p.ERR_UNAUTHORIZED, "x") == {"type": "error", "code": "unauthorized", "message": "x"}

    def test_encode_keeps_chinese(self):
        text = p.encode(p.thinking(False) | {"note": "你好"})
        assert "你好" in text and json.loads(text)["on"] is False
