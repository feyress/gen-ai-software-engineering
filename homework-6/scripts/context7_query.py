"""Throwaway probe: talk to the context7 MCP server over stdio via raw JSON-RPC.

Usage:
    python scripts/context7_query.py list
    python scripts/context7_query.py resolve "<library name>" "<query>"
    python scripts/context7_query.py docs "<library id>" "<query>"
"""

import json
import subprocess
import sys

CMD = ["npx", "-y", "@upstash/context7-mcp@latest"]


def rpc(proc, payload):
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()
    while True:
        line = proc.stdout.readline()
        if not line:
            raise SystemExit("server closed the connection")
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("id") == payload.get("id"):
            return msg


def main():
    mode = sys.argv[1]
    proc = subprocess.Popen(
        CMD, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, bufsize=1,
    )
    rpc(proc, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "probe", "version": "1.0"},
        },
    })
    proc.stdin.write(json.dumps(
        {"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    proc.stdin.flush()

    if mode == "list":
        out = rpc(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        for tool in out["result"]["tools"]:
            print("TOOL:", tool["name"])
            print("  desc:", (tool.get("description") or "")[:400])
            print("  schema:", json.dumps(tool.get("inputSchema", {}))[:600])
    elif mode == "resolve":
        args = {"libraryName": sys.argv[2]}
        if len(sys.argv) > 3:
            args["query"] = sys.argv[3]
        out = rpc(proc, {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "resolve-library-id", "arguments": args},
        })
        for block in out.get("result", {}).get("content", []):
            print(block.get("text", "")[:6000])
        if "error" in out:
            print("ERROR:", json.dumps(out["error"]))
    elif mode == "docs":
        args = {"libraryId": sys.argv[2], "query": sys.argv[3]}
        out = rpc(proc, {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "query-docs", "arguments": args},
        })
        for block in out.get("result", {}).get("content", []):
            print(block.get("text", ""))
        if "error" in out:
            print("ERROR:", json.dumps(out["error"]))
    proc.terminate()


if __name__ == "__main__":
    main()
