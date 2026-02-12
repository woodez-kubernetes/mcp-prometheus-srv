#!/usr/bin/env python
"""MCP client test script.

Connects to the MCP server at http://localhost:8000/mcp and exercises
all registered tools, resources, and prompts.

Usage:
    1. Start the Django server:  uvicorn mcp_prometheus.asgi:application --port 8000
    2. Run this script:          python scripts/mcp_client_test.py

Requires a running Prometheus at localhost:9090 for tool calls to succeed.
"""

import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_URL = "http://localhost:8000/mcp"


async def main():
    print(f"Connecting to MCP server at {MCP_URL}...")

    async with streamablehttp_client(MCP_URL) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            print("Session initialized.\n")

            # ---------------------------------------------------------- #
            # List tools
            # ---------------------------------------------------------- #
            tools_resp = await session.list_tools()
            tools = tools_resp.tools
            print(f"Tools ({len(tools)}):")
            for t in tools:
                print(f"  - {t.name}: {(t.description or '')[:60]}")
            print()

            # ---------------------------------------------------------- #
            # List resources
            # ---------------------------------------------------------- #
            resources_resp = await session.list_resources()
            resources = resources_resp.resources
            print(f"Resources ({len(resources)}):")
            for r in resources:
                print(f"  - {r.uri}: {r.description or ''}")
            print()

            # ---------------------------------------------------------- #
            # List prompts
            # ---------------------------------------------------------- #
            prompts_resp = await session.list_prompts()
            prompts = prompts_resp.prompts
            print(f"Prompts ({len(prompts)}):")
            for p in prompts:
                print(f"  - {p.name}: {p.description or ''}")
            print()

            # ---------------------------------------------------------- #
            # Call tools
            # ---------------------------------------------------------- #
            print("=" * 60)
            print("Testing tool calls...")
            print("=" * 60)

            test_calls = [
                ("get_server_instructions", {}),
                ("query_instant", {"query": "up"}),
                ("list_metrics", {}),
                ("list_labels", {}),
                ("get_label_values", {"label_name": "job"}),
                ("get_targets", {}),
                ("get_alerts", {}),
                ("get_rules", {}),
            ]

            all_passed = True
            for tool_name, args in test_calls:
                try:
                    result = await session.call_tool(tool_name, args)
                    content = result.content[0].text if result.content else "<empty>"
                    # Truncate for display
                    preview = content[:200] + "..." if len(content) > 200 else content
                    print(f"\n  [PASS] {tool_name}({args})")
                    print(f"         {preview}")
                except Exception as e:
                    print(f"\n  [FAIL] {tool_name}({args})")
                    print(f"         Error: {e}")
                    all_passed = False

            # ---------------------------------------------------------- #
            # Read resources
            # ---------------------------------------------------------- #
            print("\n" + "=" * 60)
            print("Testing resource reads...")
            print("=" * 60)

            for r in resources:
                try:
                    result = await session.read_resource(r.uri)
                    content = result.contents[0].text if result.contents else "<empty>"
                    preview = content[:200] + "..." if len(content) > 200 else content
                    print(f"\n  [PASS] {r.uri}")
                    print(f"         {preview}")
                except Exception as e:
                    print(f"\n  [FAIL] {r.uri}")
                    print(f"         Error: {e}")
                    all_passed = False

            # ---------------------------------------------------------- #
            # Summary
            # ---------------------------------------------------------- #
            print("\n" + "=" * 60)
            if all_passed:
                print("All tests passed!")
            else:
                print("Some tests FAILED. See above for details.")
                sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
