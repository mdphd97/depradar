"""Snapshot and Diff Engine for DepRadar.
Enables time-machine environment tracking:
- Save timestamped system snapshots
- Calculate environment drift, package upgrades, additions, and deletions
- Quantify net storage footprint changes over time
"""

import os
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from .models import GraphData, get_default_output_dir
from .scanners.base import format_size

def get_snapshots_dir() -> Path:
    snap_dir = get_default_output_dir() / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    return snap_dir

def save_snapshot(graph: GraphData, label: Optional[str] = None) -> Path:
    """Saves a timestamped snapshot of the current dependency graph."""
    snap_dir = get_snapshots_dir()
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_label = f"_{label.strip().replace(' ', '_')}" if label else ""
    filename = f"snapshot_{ts_str}{clean_label}.json"
    file_path = snap_dir / filename

    data = graph.to_dict()
    data["snapshot_metadata"] = {
        "saved_at": datetime.now().isoformat(),
        "timestamp": time.time(),
        "label": label or "manual",
        "total_nodes": len(graph.nodes),
        "total_links": len(graph.links)
    }

    file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return file_path

def list_snapshots() -> List[Dict[str, Any]]:
    """Returns a chronological list of saved snapshots."""
    snap_dir = get_snapshots_dir()
    snapshots = []
    for f in sorted(snap_dir.glob("snapshot_*.json")):
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
            meta = raw.get("snapshot_metadata", {})
            snapshots.append({
                "path": str(f),
                "filename": f.name,
                "saved_at": meta.get("saved_at", datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")),
                "timestamp": meta.get("timestamp", f.stat().st_mtime),
                "label": meta.get("label", ""),
                "total_nodes": meta.get("total_nodes", len(raw.get("nodes", []))),
                "total_links": meta.get("total_links", len(raw.get("links", []))),
                "file_size": format_size(f.stat().st_size)
            })
        except Exception:
            pass
    return snapshots

def load_snapshot(identifier: str = "latest") -> Optional[Dict[str, Any]]:
    """Loads a snapshot by 'latest', filename, or index."""
    snaps = list_snapshots()
    if not snaps:
        return None

    if identifier in ("latest", "last"):
        target_path = Path(snaps[-1]["path"])
    elif identifier in ("prev", "previous"):
        target_path = Path(snaps[-2]["path"]) if len(snaps) >= 2 else Path(snaps[-1]["path"])
    else:
        # Match by filename or substring
        match = [s for s in snaps if identifier in s["filename"] or identifier in s["path"]]
        if match:
            target_path = Path(match[-1]["path"])
        else:
            return None

    try:
        return json.loads(target_path.read_text(encoding="utf-8"))
    except Exception:
        return None

def compute_diff(old_graph: Dict[str, Any], new_graph: Dict[str, Any]) -> Dict[str, Any]:
    """Computes structural and package-level delta between two environment states."""
    old_nodes = {n["id"]: n for n in old_graph.get("nodes", [])}
    new_nodes = {n["id"]: n for n in new_graph.get("nodes", [])}

    added = []
    removed = []
    modified = []

    net_bytes = 0

    # Discover added and modified
    for n_id, n_new in new_nodes.items():
        if n_id not in old_nodes:
            added.append(n_new)
            net_bytes += n_new.get("size_bytes", 0)
        else:
            n_old = old_nodes[n_id]
            size_diff = n_new.get("size_bytes", 0) - n_old.get("size_bytes", 0)
            net_bytes += size_diff

            # Check for package-level differences in venvs
            old_pkgs = {p.get("name"): p.get("version") for p in n_old.get("installed_packages", [])}
            new_pkgs = {p.get("name"): p.get("version") for p in n_new.get("installed_packages", [])}

            pkgs_added = [f"{k} v{v}" for k, v in new_pkgs.items() if k not in old_pkgs]
            pkgs_removed = [f"{k} v{v}" for k, v in old_pkgs.items() if k not in new_pkgs]
            pkgs_changed = [
                f"{k} ({old_pkgs[k]} -> {new_pkgs[k]})"
                for k in new_pkgs if k in old_pkgs and old_pkgs[k] != new_pkgs[k]
            ]

            status_changed = n_new.get("status") != n_old.get("status")

            if abs(size_diff) > 1024 * 1024 or pkgs_added or pkgs_removed or pkgs_changed or status_changed:
                modified.append({
                    "id": n_id,
                    "name": n_new.get("name"),
                    "category": n_new.get("category"),
                    "type": n_new.get("type"),
                    "old_size": n_old.get("size_human"),
                    "new_size": n_new.get("size_human"),
                    "size_diff_bytes": size_diff,
                    "size_diff_human": f"{'+' if size_diff > 0 else ''}{format_size(abs(size_diff))}",
                    "old_status": n_old.get("status"),
                    "new_status": n_new.get("status"),
                    "packages_added": pkgs_added,
                    "packages_removed": pkgs_removed,
                    "packages_upgraded": pkgs_changed
                })

    # Discover removed
    for o_id, n_old in old_nodes.items():
        if o_id not in new_nodes:
            removed.append(n_old)
            net_bytes -= n_old.get("size_bytes", 0)

    return {
        "summary": {
            "added_count": len(added),
            "removed_count": len(removed),
            "modified_count": len(modified),
            "net_storage_bytes": net_bytes,
            "net_storage_human": f"{'+' if net_bytes > 0 else '-'}{format_size(abs(net_bytes))}"
        },
        "added": added,
        "removed": removed,
        "modified": modified
    }

def format_diff_cli(diff_res: Dict[str, Any]) -> str:
    """Renders human-readable formatted CLI output of the diff."""
    summary = diff_res["summary"]
    lines = [
        "══════════════════════════════════════════════════════════════",
        " 📡 DepRadar Environment Time-Machine Diff",
        "══════════════════════════════════════════════════════════════",
        f" Net Storage Impact: {summary['net_storage_human']} ({summary['added_count']} added, {summary['removed_count']} removed, {summary['modified_count']} modified)",
        ""
    ]

    if diff_res["added"]:
        lines.append("🟢 ADDED COMPONENTS:")
        for a in diff_res["added"]:
            lines.append(f"  + [{a.get('category')}] {a.get('name')} ({a.get('size_human')})")
        lines.append("")

    if diff_res["removed"]:
        lines.append("🔴 REMOVED / PRUNED COMPONENTS:")
        for r in diff_res["removed"]:
            lines.append(f"  - [{r.get('category')}] {r.get('name')} ({r.get('size_human')})")
        lines.append("")

    if diff_res["modified"]:
        lines.append("🟡 MODIFIED / DRIFTED COMPONENTS:")
        for m in diff_res["modified"]:
            lines.append(f"  ~ {m['name']} ({m['old_size']} -> {m['new_size']}, diff: {m['size_diff_human']})")
            if m["packages_added"]:
                lines.append(f"    Installed: {', '.join(m['packages_added'][:5])}")
            if m["packages_removed"]:
                lines.append(f"    Removed:   {', '.join(m['packages_removed'][:5])}")
            if m["packages_upgraded"]:
                lines.append(f"    Upgraded:  {', '.join(m['packages_upgraded'][:5])}")
            if m["old_status"] != m["new_status"]:
                lines.append(f"    Status:    {m['old_status']} -> {m['new_status']}")
        lines.append("")

    if not diff_res["added"] and not diff_res["removed"] and not diff_res["modified"]:
        lines.append("✨ No environment drift detected. System state is identical to snapshot.")

    return "\n".join(lines)
