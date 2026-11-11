"""Command-line interface for DepRadar.
Supports interactive visualization, cross-platform execution (Linux, macOS, Windows),
and AI Agent integrations (JSON output, query engine, stale package cleanup, and MCP server).
"""

import sys
import json
import argparse
import platform
import webbrowser
from pathlib import Path
from .graph import build_graph
from .generator import generate_html
from .agent import generate_agent_context, query_dependencies, get_stale_items
from .mcp import run_mcp_server

def get_default_output_dir() -> Path:
    """Returns cross-platform configuration and output directory."""
    home = Path.home()
    if platform.system() == "Windows":
        appdata = Path(home / "AppData" / "Roaming")
        return appdata / "depradar" if appdata.exists() else home / ".depradar"
    elif platform.system() == "Darwin":
        app_sup = home / "Library" / "Application Support"
        return app_sup / "depradar" if app_sup.exists() else home / ".config" / "depradar"
    else:
        return home / ".config" / "depradar"

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
