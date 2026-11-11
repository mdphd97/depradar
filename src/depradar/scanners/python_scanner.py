"""Scanner for Python environments, UV tools, and virtualenvs across Windows, macOS, and Linux."""

import os
import shutil
import platform
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from ..models import Node, Link
from .base import get_dir_size_and_mtime, format_size, calculate_age_and_status, size_to_radius

IS_WIN = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"

def find_uv_binary(home: Path) -> Optional[Path]:
    """Cross-platform search for uv executable."""
    which_uv = shutil.which("uv")
    if which_uv:
        return Path(which_uv)
    
    candidates = [
        home / ".local" / "bin" / "uv",
        home / ".cargo" / "bin" / "uv",
        home / ".cargo" / "bin" / "uv.exe",
        home / "AppData" / "Local" / "bin" / "uv.exe",
        home / "AppData" / "Local" / "uv" / "uv.exe",
        Path("/opt/homebrew/bin/uv"),
        Path("/usr/local/bin/uv")
    ]
    for c in candidates:
        if c.exists():
            return c
    return None

def find_python_in_venv(vpath: Path) -> Optional[Path]:
    """Cross-platform search for python executable inside a virtual environment."""
    candidates = [
        vpath / "bin" / "python",
        vpath / "bin" / "python3",
        vpath / "Scripts" / "python.exe",
        vpath / "Scripts" / "python"
    ]
    for c in candidates:
        if c.exists():
            return c
    return None

def get_installed_packages(uv_bin: Optional[Path], py_bin: Optional[Path]) -> List[Dict[str, str]]:
    """Extracts package names and versions from python environment via uv pip list or pip list."""
    pkgs = []
    try:
        if py_bin and py_bin.exists():
            cmd = [str(uv_bin), "pip", "list", "--python", str(py_bin)] if (uv_bin and uv_bin.exists()) else [str(py_bin), "-m", "pip", "list"]
            res = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
            for l in res.splitlines():
                parts = l.split()
                if len(parts) >= 2 and parts[0] not in ("Package", "Using") and not parts[0].startswith("-"):
                    pkgs.append({"name": parts[0], "version": parts[1]})
    except Exception:
        pass
    return pkgs

def scan_python(home: Path) -> Tuple[List[Node], List[Link]]:
    nodes: List[Node] = []
    links: List[Link] = []

    uv_bin = find_uv_binary(home)
    py_rt_id = "runtime:python"
    nodes.append(Node(
        id=py_rt_id,
        name="Python Runtime & UV",
        category="Desktop & System",
        type="runtime",
        path=str(uv_bin) if uv_bin else "python",
        size_bytes=60 * 1024 * 1024,
        size_human="~60 MB",
        last_used="Active",
        days_inactive=0,
        status="active",
        notes=f"Python interpreter & UV package manager ({platform.system()})",
        val=16.0
    ))

    # 1. UV Tools (like kaggle CLI) across Linux, macOS, and Windows
    uv_tools_dirs = [
        home / ".local" / "share" / "uv" / "tools",
        home / "Library" / "Application Support" / "uv" / "tools",
        home / "AppData" / "Local" / "uv" / "tools"
    ]
    for uv_tools_dir in uv_tools_dirs:
        if uv_tools_dir.exists():
            for tool_dir in uv_tools_dir.iterdir():
                if tool_dir.is_dir() and not tool_dir.name.startswith("."):
                    size_bytes, mtime = get_dir_size_and_mtime(tool_dir)
                    date_str, days, status = calculate_age_and_status(mtime)
                    tool_id = f"uv-tool:{tool_dir.name}"
                    py_bin = find_python_in_venv(tool_dir)
                    tool_pkgs = get_installed_packages(uv_bin, py_bin)
                    pkg_note = f" ({len(tool_pkgs)} packages)" if tool_pkgs else ""

                    nodes.append(Node(
                        id=tool_id,
                        name=f"{tool_dir.name} (uv tool)",
                        category="Data Science & ML" if "kaggle" in tool_dir.name else "Automation & Scraping",
                        type="uv-tool",
                        path=str(tool_dir),
                        size_bytes=size_bytes,
                        size_human=format_size(size_bytes),
                        last_used=date_str,
                        days_inactive=days,
                        status=status,
                        uninstall_cmd=f"uv tool uninstall {tool_dir.name}",
                        notes=f"Isolated CLI tool installed via UV{pkg_note}",
                        val=size_to_radius(size_bytes),
                        installed_packages=tool_pkgs
                    ))
                    links.append(Link(
                        source=py_rt_id,
                        target=tool_id,
                        relationship="Isolated UV Tool",
                        description=f"UV tool manager hosts {tool_dir.name} in an isolated Python virtual environment ({len(tool_pkgs)} packages)"
                    ))

    # 2. Virtualenvs (.venv / venv) across cross-platform directories
    search_dirs = [
        home,
        home / "Documents",
        home / "Projects",
        home / "Developer",
        home / "workspace",
        home / "repos",
        Path.cwd()
    ]
    seen_venvs = set()
    for sdir in search_dirs:
        if not sdir.exists():
            continue
        for root, dirs, files in os.walk(sdir):
            dirs[:] = [d for d in dirs if d not in [".git", "node_modules", ".cache", "snap", ".gemini", ".local", "AppData", "Library"]]
            if "pyvenv.cfg" in files:
                vpath = Path(root)
                if str(vpath) in seen_venvs:
                    continue
                seen_venvs.add(str(vpath))

                proj_dir = vpath.parent
                proj_name = proj_dir.name
                size_bytes, mtime = get_dir_size_and_mtime(vpath)
                date_str, days, status = calculate_age_and_status(mtime)

                # Determine category
                p_lower = proj_name.lower()
                if any(k in p_lower for k in ("ml", "kaggle", "vision", "torch", "data", "train", "model", "segment")):
                    cat = "Data Science & ML"
                elif any(k in p_lower for k in ("scrape", "crawl", "monitor", "refresh", "bot", "auto", "fetch", "spider")):
                    cat = "Automation & Scraping"
                elif any(k in p_lower for k in ("agent", "ai", "llm", "chat", "copilot", "prompt", "career")):
                    cat = "AI & Agents"
                elif any(k in p_lower for k in ("web", "app", "frontend", "backend", "api", "server", "fullstack")):
                    cat = "Fullstack Web"
                else:
                    cat = "Data Science & ML"

                venv_id = f"venv:{proj_name}"
                py_bin = find_python_in_venv(vpath)
                v_pkgs = get_installed_packages(uv_bin, py_bin)
                pkg_summary = f"({len(v_pkgs)} packages installed)" if v_pkgs else ""
                del_cmd = f"rmdir /s /q \"{vpath}\"" if IS_WIN else f"rm -rf '{vpath}'"

                nodes.append(Node(
                    id=venv_id,
                    name=f"{proj_name} (.venv)",
                    category=cat,
                    type="python-venv",
                    path=str(vpath),
                    size_bytes=size_bytes,
                    size_human=format_size(size_bytes),
                    last_used=date_str,
                    days_inactive=days,
                    status=status,
                    uninstall_cmd=del_cmd,
                    notes=f"Virtualenv for {proj_name} {pkg_summary}".strip(),
                    val=size_to_radius(size_bytes),
                    installed_packages=v_pkgs
                ))
                links.append(Link(
                    source=py_rt_id,
                    target=venv_id,
                    relationship="Virtual Environment",
                    description=f"Isolated Python virtual environment housing {len(v_pkgs)} packages for {proj_name}"
                ))

                # Link venv to its project workspace
                target_proj = f"project:{proj_name}"
                links.append(Link(
                    source=venv_id,
                    target=target_proj,
                    relationship="Project Environment",
                    description=f"Powers {proj_name} with {len(v_pkgs)} isolated Python packages"
                ))

                # Link venv to imported packages that exist as nodes
                for pkg in v_pkgs:
                    raw_name = pkg["name"].lower()
                    alt_name = raw_name.replace("-", "_")
                    for cand in set([f"pkg:{raw_name}", f"pkg:{alt_name}"]):
                        links.append(Link(
                            source=venv_id,
                            target=cand,
                            relationship="Installed Package",
                            description=f"Houses {pkg['name']} v{pkg['version']} in {proj_name}/.venv"
                        ))

    return nodes, links
