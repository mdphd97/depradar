"""Graph builder for DepRadar."""

from pathlib import Path
from datetime import datetime
from .models import GraphData, Node, Link
from .scanners.node_scanner import scan_node
from .scanners.python_scanner import scan_python
from .scanners.system_scanner import scan_system
from .scanners.project_scanner import scan_projects
from .scanners.build_scanner import scan_build_artifacts
from .scanners.code_scanner import scan_code_imports

def build_graph(home: Path = None) -> GraphData:
    if home is None:
        home = Path.home()

    all_nodes = []
    all_links = []
    seen_node_ids = set()

    # Collect from standard scanners
    scanners = [scan_node, scan_python, scan_system, scan_projects, scan_build_artifacts]
    for scan_fn in scanners:
        nodes, links = scan_fn(home)
        for n in nodes:
            if n.id not in seen_node_ids:
                all_nodes.append(n)
                seen_node_ids.add(n.id)
        all_links.extend(links)

    # Deep AST Code Analysis on all detected projects
    projects_to_analyze = [
        (n.id, n.category, Path(n.path))
        for n in all_nodes
        if n.type == "project" and Path(n.path).exists()
    ]
    code_nodes, code_links = scan_code_imports(home, projects_to_analyze)
    for cn in code_nodes:
        if cn.id not in seen_node_ids:
            all_nodes.append(cn)
            seen_node_ids.add(cn.id)
    all_links.extend(code_links)

    # Filter links whose source or target does not exist in nodes
    valid_links = []
    for l in all_links:
        if l.source in seen_node_ids and l.target in seen_node_ids:
            valid_links.append(l)

    metadata = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_nodes": len(all_nodes),
        "total_links": len(valid_links),
        "total_stale": sum(1 for n in all_nodes if n.status == "stale"),
        "categories": sorted(list(set(n.category for n in all_nodes)))
    }

    return GraphData(nodes=all_nodes, links=valid_links, metadata=metadata)
