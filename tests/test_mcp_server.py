import json
import mcp_server


def test_tools_list_returns_all_tools():
    tools = mcp_server.TOOLS
    names = {t["name"] for t in tools}
    for expected in ["capture", "redact", "embed", "check", "guard",
                     "verify", "suggest", "annotate", "health"]:
        assert expected in names, "tool '{}' missing from TOOLS".format(expected)


def test_tool_has_required_fields():
    for tool in mcp_server.TOOLS:
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool
        assert tool["inputSchema"]["type"] == "object"


def test_handle_initialize_returns_capabilities():
    req = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
           "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                      "clientInfo": {"name": "test", "version": "1.0"}}}
    resp = mcp_server._handle_request(req)
    assert resp["id"] == 1
    assert "result" in resp
    assert "capabilities" in resp["result"]
    assert "tools" in resp["result"]["capabilities"]
    assert "serverInfo" in resp["result"]


def test_handle_tools_list():
    req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    resp = mcp_server._handle_request(req)
    assert resp["id"] == 2
    assert "result" in resp
    assert "tools" in resp["result"]
    assert len(resp["result"]["tools"]) > 0


def test_handle_unknown_method_returns_error():
    req = {"jsonrpc": "2.0", "id": 3, "method": "unknown/method", "params": {}}
    resp = mcp_server._handle_request(req)
    assert "error" in resp
    assert resp["error"]["code"] == -32601


def test_notification_returns_none():
    notif = {"jsonrpc": "2.0", "method": "initialized", "params": {}}
    resp = mcp_server._handle_request(notif)
    assert resp is None


def test_tools_call_guard_dispatches(monkeypatch):
    import subprocess as sp

    fake_result = {"ok": True, "step": "guard", "outputs": {"safe": True},
                   "warnings": [], "elapsed_s": 0.0}

    class FakeProc:
        stdout = json.dumps(fake_result)
        stderr = ""
        returncode = 0

    monkeypatch.setattr(sp, "run", lambda *a, **kw: FakeProc())

    req = {
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {"name": "guard", "arguments": {"command": "echo hello"}}
    }
    resp = mcp_server._handle_request(req)
    assert resp["id"] == 4
    assert "result" in resp
    content = resp["result"]["content"]
    assert len(content) > 0
    parsed = json.loads(content[0]["text"])
    assert parsed["ok"] is True


def test_tools_call_unknown_tool():
    req = {
        "jsonrpc": "2.0", "id": 5, "method": "tools/call",
        "params": {"name": "nonexistent_tool", "arguments": {}}
    }
    resp = mcp_server._handle_request(req)
    assert "error" in resp
    assert resp["error"]["code"] == -32602
