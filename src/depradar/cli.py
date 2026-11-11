"""Command-line interface for DepRadar.
Supports interactive visualization, cross-platform execution (Linux, macOS, Windows),
AI Agent integrations (JSON output, query engine, stale package cleanup, and MCP server),
Time-machine snapshots, environment diffs, and security audits.
"""

import sys
import json
import argparse
import platform
import webbrowser
from pathlib import Path
from .models import get_default_output_dir
from .graph import build_graph
from .generator import generate_html
from .agent import generate_agent_context, query_dependencies, get_stale_items
from .mcp import run_mcp_server
from .diff import save_snapshot, list_snapshots, load_snapshot, compute_diff, format_diff_cli
from .audit import audit_packages, format_audit_cli
from .server import run_server

DEFAULT_OUTPUT_DIR = get_default_output_dir()
DEFAULT_HTML_PATH = DEFAULT_OUTPUT_DIR / "depradar_graph.html"

def main():
    parser = argparse.ArgumentParser(
        prog="depradar",
        description="DepRadar: Cross-Platform System & Package Dependency Radar for Developers and AI Agents"
    )
    subparsers = parser.add_subparsers(dest="command")

    # scan
    p_scan = subparsers.add_parser("scan", help="Scan system and generate interactive network graph")
    p_scan.add_argument("-o", "--output", help="Output HTML file path")
    p_scan.add_argument("--open", action="store_true", help="Automatically open graph in default browser")
    p_scan.add_argument("--json", action="store_true", help="Print structured graph JSON to stdout (for AI agents)")

    # query
    p_query = subparsers.add_parser("query", help="Query a package, library, or tool to inspect dependencies and usage")
    p_query.add_argument("term", help="Name or keyword to search (e.g. 'selenium', 'zarr', 'docker')")
    p_query.add_argument("--json", action="store_true", help="Output machine-readable JSON for AI agents")

    # stale
    p_stale = subparsers.add_parser("stale", help="List stale, orphaned, and unused packages with cleanup commands")
    p_stale.add_argument("--json", action="store_true", help="Output machine-readable JSON for AI agents")

    # snapshot
    p_snap = subparsers.add_parser("snapshot", help="Save or list environment baseline snapshots")
    p_snap.add_argument("--save", action="store_true", help="Save a new snapshot of current state")
    p_snap.add_argument("--label", help="Optional human-readable label for the snapshot")
    p_snap.add_argument("--list", action="store_true", help="List all saved snapshots")
    p_snap.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    # diff
    p_diff = subparsers.add_parser("diff", help="Calculate environment drift, package upgrades, and storage deltas")
    p_diff.add_argument("--since", default="latest", help="Compare with snapshot ('latest', 'prev', or filename)")
    p_diff.add_argument("--json", action="store_true", help="Output machine-readable JSON for AI agents")

    # audit
    p_audit = subparsers.add_parser("audit", help="Audit installed packages for security vulnerabilities and CVEs")
    p_audit.add_argument("--online", action="store_true", help="Query online OSV database in addition to offline advisories")
    p_audit.add_argument("--json", action="store_true", help="Output machine-readable JSON for AI agents")

    # serve
    p_serve = subparsers.add_parser("serve", help="Run local interactive web server with real-time pruning API")
    p_serve.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    p_serve.add_argument("--no-open", action="store_true", help="Do not automatically open browser")

    # agent-context
    p_ctx = subparsers.add_parser("agent-context", help="Export compact Markdown system context for AI agents")
    p_ctx.add_argument("-o", "--output", help="Output Markdown file path (prints to stdout if omitted)")

    # mcp
    p_mcp = subparsers.add_parser("mcp", help="Run Model Context Protocol (MCP) server over stdio for AI agents")

    # export
    p_exp = subparsers.add_parser("export", help="Export dependency graph as JSON")
    p_exp.add_argument("-o", "--output", help="Output JSON file path")

    args = parser.parse_args()

    # Default action: run scan and print quick summary
    if args.command is None:
        cmd_args = sys.argv[1:]
        if not cmd_args:
            print(f"🚀 DepRadar: Scanning your system ({platform.system()} {platform.machine()})...")
            graph = build_graph()
            out_file = generate_html(graph, DEFAULT_HTML_PATH)
            print(f"✅ Generated interactive graph: {out_file}")
            print(f"📊 Discovered {len(graph.nodes)} nodes and {len(graph.links)} connections ({graph.metadata['total_stale']} stale).")
            print("💡 Tip: AI agents can run `depradar scan --json`, `depradar query <name>`, or `depradar mcp`")
            webbrowser.open(f"file://{out_file.resolve()}")
            return
        else:
            parser.print_help()
            return

    if args.command == "scan":
        graph = build_graph()
        if getattr(args, "json", False):
            print(json.dumps(graph.to_dict(), indent=2))
            return

        out_path = Path(args.output) if args.output else DEFAULT_HTML_PATH
        out_file = generate_html(graph, out_path)
        print(f"✅ Interactive graph generated at: {out_file}")
        print(f"📊 Summary: {len(graph.nodes)} nodes, {len(graph.links)} links, {graph.metadata['total_stale']} stale items.")

        if getattr(args, "open", False):
            print("🌐 Opening in your web browser...")
            webbrowser.open(f"file://{out_file.resolve()}")

    elif args.command == "snapshot":
        if getattr(args, "list", False) or (not getattr(args, "save", False) and not getattr(args, "label", None)):
            snaps = list_snapshots()
            if getattr(args, "json", False):
                print(json.dumps(snaps, indent=2))
            else:
                if not snaps:
                    print("📸 No snapshots found yet. Run `depradar snapshot --save` to create your first baseline!")
                    return
                print(f"📸 Saved Environment Snapshots ({len(snaps)} total):\n")
                for s in snaps:
                    label_str = f" [{s['label']}]" if s['label'] else ""
                    print(f"• {s['filename']}{label_str}")
                    print(f"  Saved: {s['saved_at']} | Nodes: {s['total_nodes']} | Links: {s['total_links']} | Size: {s['file_size']}")
                print("\nTip: Run `depradar diff --since latest` to compare current state.")
        else:
            graph = build_graph()
            snap_path = save_snapshot(graph, label=args.label)
            if getattr(args, "json", False):
                print(json.dumps({"success": True, "path": str(snap_path)}, indent=2))
            else:
                print(f"✅ Saved snapshot baseline: {snap_path.name}")
                print(f"   Stored at: {snap_path}")
                print(f"   Total components tracked: {len(graph.nodes)} nodes, {len(graph.links)} links")

    elif args.command == "diff":
        old_snap = load_snapshot(args.since)
        if not old_snap:
            print(f"❌ Snapshot '{args.since}' not found. Run `depradar snapshot --save` to create a baseline.")
            return

        current_graph = build_graph().to_dict()
        diff_res = compute_diff(old_snap, current_graph)

        if getattr(args, "json", False):
            print(json.dumps(diff_res, indent=2))
        else:
            print(format_diff_cli(diff_res))

    elif args.command == "audit":
        graph = build_graph()
        audit_res = audit_packages(graph, online=getattr(args, "online", False))
        if getattr(args, "json", False):
            print(json.dumps(audit_res, indent=2))
        else:
            print(format_audit_cli(audit_res))

    elif args.command == "serve":
        run_server(port=args.port, open_browser=not getattr(args, "no_open", False))

    elif args.command == "query":
        graph = build_graph()
        results = query_dependencies(graph, args.term)
        if getattr(args, "json", False):
            print(json.dumps(results, indent=2))
        else:
            if not results:
                print(f"❌ No package or tool matching '{args.term}' found.")
                return
            print(f"🔍 Found {len(results)} matching component(s) for '{args.term}':\n")
            for r in results:
                print(f"📦 {r['name']} [{r['category']} • {r['type']}]")
                print(f"   Status: {r['status'].upper()} | Size: {r['size']} | Path: {r['path']}")
                if r['notes']:
                    print(f"   Notes: {r['notes']}")
                if r['requires']:
                    print(f"   ──► Required by: {', '.join([d['target'] for d in r['requires']])}")
                if r['required_by']:
                    print(f"   ◄── Required by upstream: {', '.join([u['source'] for u in r['required_by']])}")
                print()

    elif args.command == "stale":
        graph = build_graph()
        stale_items = get_stale_items(graph)
        if getattr(args, "json", False):
            print(json.dumps(stale_items, indent=2))
        else:
            if not stale_items:
                print("✨ No stale or orphaned items detected! System is clean.")
                return
            print(f"🔴 Found {len(stale_items)} Stale / Orphaned Item(s):\n")
            for item in stale_items:
                print(f"• {item['name']} ({item['size']}, {item['days_inactive']} days inactive)")
                print(f"  Path: {item['path']}")
                print(f"  Recommended Cleanup: {item['cleanup_cmd']}")
                print()

    elif args.command == "agent-context":
        graph = build_graph()
        ctx_md = generate_agent_context(graph)
        if args.output:
            out_p = Path(args.output)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(ctx_md, encoding="utf-8")
            print(f"✅ Exported AI agent system context to: {out_p}")
        else:
            print(ctx_md)

    elif args.command == "mcp":
        run_mcp_server()

    elif args.command == "export":
        graph = build_graph()
        data = json.dumps(graph.to_dict(), indent=2)
        if args.output:
            out_p = Path(args.output)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(data, encoding="utf-8")
            print(f"✅ Exported graph JSON to: {args.output}")
        else:
            print(data)

if __name__ == "__main__":
    main()
