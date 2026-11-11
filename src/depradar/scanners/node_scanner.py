"""Scanner for Node.js runtimes, global packages, and dependencies."""

import json
import subprocess
from pathlib import Path
from typing import List, Tuple
from ..models import Node, Link
from .base import get_dir_size_and_mtime, format_size, calculate_age_and_status, size_to_radius

def scan_node(home: Path) -> Tuple[List[Node], List[Link]]:
    nodes: List[Node] = []
    links: List[Link] = []

    # Node.js Root Runtime Node
    node_rt_id = "runtime:node"
    node_version = "v20"
    try:
        ver = subprocess.check_output(["node", "-v"], text=True, stderr=subprocess.DEVNULL).strip()
        if ver:
            node_version = ver
    except Exception:
        pass

    nodes.append(Node(
        id=node_rt_id,
        name=f"Node.js Runtime ({node_version})",
        category="Desktop & System",
        type="runtime",
        path=str(home / ".nvm"),
        size_bytes=180 * 1024 * 1024,
        size_human="~180 MB",
        last_used="Active",
        days_inactive=0,
        status="active",
        notes="Primary JavaScript/TypeScript runtime via NVM",
        val=16.0
    ))

    # Global NPM packages
    try:
        res = subprocess.run(["npm", "list", "-g", "--depth=0", "--json"], capture_output=True, text=True)
        if res.returncode == 0:
            npm_data = json.loads(res.stdout)
            deps = npm_data.get("dependencies", {})
            prefix = ""
            try:
                prefix = subprocess.check_output(["npm", "root", "-g"], text=True).strip()
            except Exception:
                pass

            for pkg, info in deps.items():
                if pkg in ["npm", "corepack"]:
                    continue

                pkg_dir = Path(prefix) / pkg if prefix else Path()
                size_bytes, mtime = get_dir_size_and_mtime(pkg_dir) if pkg_dir.exists() else (1024*1024*5, 0)
                date_str, days, status = calculate_age_and_status(mtime)

                category = "AI & Agents" if "agent" in pkg or "firecrawl" in pkg or "antigravity" in pkg else "Automation & Scraping"
                if pkg == "yarn":
                    category = "Desktop & System"

                node_id = f"npm:{pkg}"
                ver_str = info.get("version", "")
                display_name = f"{pkg}@{ver_str}" if ver_str else pkg

                nodes.append(Node(
                    id=node_id,
                    name=display_name,
                    category=category,
                    type="npm-global",
                    path=str(pkg_dir),
                    size_bytes=size_bytes,
                    size_human=format_size(size_bytes),
                    last_used=date_str,
                    days_inactive=days,
                    status=status,
                    uninstall_cmd=f"npm uninstall -g {pkg}",
                    notes=f"Global Node.js CLI tool ({category})",
                    val=size_to_radius(size_bytes)
                ))

                # Link from Node Runtime to this package
                links.append(Link(
                    source=node_rt_id,
                    target=node_id,
                    relationship="Global CLI Tool",
                    description=f"Node.js runtime hosts and executes {display_name} globally"
                ))
    except Exception:
        pass

    return nodes, links
