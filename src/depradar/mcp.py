"""Model Context Protocol (MCP) Server for DepRadar.
Enables AI Agents (Claude Desktop, Cursor, Antigravity, Windsurf) to inspect system dependencies via stdio.
"""

import sys
import json
import platform
from pathlib import Path
from typing import Dict, Any, List
from .graph import build_graph

def run_mcp_server():
    """Runs a zero-dependency JSON-RPC 2.0 stdio MCP server."""
    # Build or cache graph data
    cached_graph = None

    def get_graph():
        nonlocal cached_graph
        if cached_graph is None:
            cached_graph = build_graph()
        return cached_graph

    tools_definitions = [
        {
            "name": "depradar_get_system_overview",
            "description": "Returns a high-level overview of installed developer runtimes, total package counts, disk footprints, and stale items on this machine.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "depradar_query_dependency",
            "description": "Look up any package, library, tool, or runtime to see who imports it, where it is installed on disk, its status, and what it is used for.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Name or keyword of the library, package, or tool (e.g. 'selenium', 'zarr', 'docker', 'uv')"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "depradar_list_stale_dependencies",
            "description": "Lists all stale, orphaned, or unreferenced packages and virtual environments with recommended cleanup commands.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "depradar_get_full_graph",
            "description": "Returns the complete node and edge dependency graph of the host system.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "depradar_audit_vulnerabilities",
            "description": "Audits all installed Python and Node packages for security advisories and known CVEs.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "online": {
                        "type": "boolean",
                        "description": "Whether to query OSV API online in addition to offline advisories (default: false)"
                    }
                },
                "required": []
            }
        },
        {
            "name": "depradar_save_snapshot",
            "description": "Saves an environment snapshot baseline before running risky tasks or builds.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "Optional label (e.g. 'pre-experiment-build')"
                    }
                },
                "required": []
            }
        },
        {
            "name": "depradar_get_environment_diff",
            "description": "Calculates package additions, removals, upgrades, and storage deltas since a previous snapshot.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "since": {
                        "type": "string",
                        "description": "Snapshot identifier ('latest', 'prev', or filename, default: 'latest')"
                    }
                },
                "required": []
            }
        }
    ]

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            request = json.loads(line)
            req_id = request.get("id")
            method = request.get("method")
            params = request.get("params", {})

            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "depradar",
                            "version": "0.1.0"
                        }
                    }
                }
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

            elif method == "notifications/initialized":
                pass  # Notification, no response needed

            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": tools_definitions
                    }
                }
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

            elif method == "tools/call":
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})
                graph = get_graph()

                if tool_name == "depradar_get_system_overview":
                    overview = {
                        "os": platform.system(),
                        "os_release": platform.release(),
                        "total_nodes": len(graph.nodes),
                        "total_links": len(graph.links),
                        "total_stale_items": graph.metadata.get("total_stale", 0),
                        "categories": graph.metadata.get("categories", []),
                        "key_runtimes": [n.name for n in graph.nodes if n.type == "runtime"],
                        "heavy_disk_consumers": [
                            {"name": n.name, "size": n.size_human, "path": n.path}
                            for n in sorted(graph.nodes, key=lambda x: x.size_bytes, reverse=True)[:5]
                        ]
                    }
                    result_text = json.dumps(overview, indent=2)

                elif tool_name == "depradar_query_dependency":
                    q = tool_args.get("query", "").lower()
                    matched_nodes = []
                    for n in graph.nodes:
                        if q in n.name.lower() or q in n.id.lower() or q in n.notes.lower():
                            upstream = [
                                {"source": (l.source if isinstance(l.source, str) else l.source.id), "relationship": l.relationship, "description": l.description}
                                for l in graph.links if (l.target == n.id or (isinstance(l.target, dict) and l.target.get("id") == n.id))
                            ]
                            downstream = [
                                {"target": (l.target if isinstance(l.target, str) else l.target.id), "relationship": l.relationship, "description": l.description}
                                for l in graph.links if (l.source == n.id or (isinstance(l.source, dict) and l.source.get("id") == n.id))
                            ]
                            matched_nodes.append({
                                "id": n.id,
                                "name": n.name,
                                "category": n.category,
                                "type": n.type,
                                "status": n.status,
                                "size": n.size_human,
                                "path": n.path,
                                "notes": n.notes,
                                "installed_packages_count": len(n.installed_packages) if n.installed_packages else 0,
                                "required_by": upstream,
                                "requires": downstream
                            })
                    result_text = json.dumps(matched_nodes, indent=2) if matched_nodes else f"No package or dependency matched query: '{q}'"

                elif tool_name == "depradar_list_stale_dependencies":
                    stale_nodes = [
                        {
                            "name": n.name,
                            "category": n.category,
                            "type": n.type,
                            "size": n.size_human,
                            "path": n.path,
                            "days_inactive": n.days_inactive,
                            "cleanup_command": n.uninstall_cmd or f"rm -rf '{n.path}'"
                        }
                        for n in graph.nodes if n.status == "stale"
                    ]
                    result_text = json.dumps(stale_nodes, indent=2)

                elif tool_name == "depradar_get_full_graph":
                    result_text = json.dumps(graph.to_dict(), indent=2)

                elif tool_name == "depradar_audit_vulnerabilities":
                    from .audit import audit_packages
                    online_check = bool(args.get("online", False))
                    audit_res = audit_packages(graph, online=online_check)
                    result_text = json.dumps(audit_res, indent=2)

                elif tool_name == "depradar_save_snapshot":
                    from .diff import save_snapshot
                    label = args.get("label", "mcp-agent-task")
                    snap_p = save_snapshot(graph, label=label)
                    result_text = json.dumps({"success": True, "snapshot": str(snap_p), "label": label}, indent=2)

                elif tool_name == "depradar_get_environment_diff":
                    from .diff import load_snapshot, compute_diff
                    since = args.get("since", "latest")
                    old_s = load_snapshot(since)
                    if not old_s:
                        result_text = f"Snapshot '{since}' not found. Run depradar_save_snapshot first."
                    else:
                        d_res = compute_diff(old_s, graph.to_dict())
                        result_text = json.dumps(d_res, indent=2)

                else:
                    result_text = f"Unknown tool: {tool_name}"

                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": result_text
                            }
                        ]
                    }
                }
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

        except Exception as e:
            if req_id is not None:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    }
                }
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()
