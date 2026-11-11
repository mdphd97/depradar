"""Data models for DepRadar graph nodes and edges."""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
import platform
from pathlib import Path

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

@dataclass
class Node:
    id: str
    name: str
    category: str  # 'AI & Agents', 'Data Science & ML', 'Automation & Scraping', 'Fullstack Web', 'Desktop & System'
    type: str      # 'python-venv', 'npm-global', 'snap-app', 'snap-runtime', 'apt-pkg', 'git-repo', 'runtime'
    path: str
    size_bytes: int
    size_human: str
    last_used: str
    days_inactive: int
    status: str    # 'active', 'inactive', 'stale'
    uninstall_cmd: str = ""
    notes: str = ""
    val: float = 1.0  # Visual radius multiplier calculated from size
    installed_packages: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class Link:
    source: str
    target: str
    relationship: str = "depends_on"  # e.g. 'Imports', 'Runtime Host', 'Typesetting Engine'
    description: str = ""             # Detailed explanation of why & how it is used

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class GraphData:
    nodes: List[Node] = field(default_factory=list)
    links: List[Link] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "links": [l.to_dict() for l in self.links],
            "metadata": self.metadata
        }
