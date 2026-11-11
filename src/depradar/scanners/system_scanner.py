"""Cross-platform scanner for System Desktop applications, runtimes, package managers, and hardware across Linux, macOS, and Windows."""

import os
import shutil
import platform
import subprocess
from pathlib import Path
from typing import List, Tuple
from ..models import Node, Link
from .base import get_dir_size_and_mtime, format_size, calculate_age_and_status, size_to_radius

def get_fast_size(p: Path) -> int:
    """Attempts fast size measurement via du, falls back to controlled os.walk."""
    if not p.exists():
        return 0
    try:
        if platform.system() != "Windows":
            out = subprocess.check_output(["du", "-sb", str(p)], stderr=subprocess.DEVNULL, text=True)
            return int(out.split()[0])
    except Exception:
        pass
    size, _ = get_dir_size_and_mtime(p, max_depth=3)
    return size

def scan_system(home: Path) -> Tuple[List[Node], List[Link]]:
    nodes: List[Node] = []
    links: List[Link] = []

    current_os = platform.system()
    is_win = (current_os == "Windows")
    primary_os_id = "runtime:os"

    # --- 1. OS-SPECIFIC RUNTIMES & PACKAGE MANAGERS ---
    if current_os == "Darwin":
        # macOS Homebrew & System
        brew_bin = shutil.which("brew") or ("/opt/homebrew/bin/brew" if Path("/opt/homebrew/bin/brew").exists() else "/usr/local/bin/brew")
        brew_exists = Path(str(brew_bin)).exists() or shutil.which("brew")
        nodes.append(Node(
            id=primary_os_id,
            name="macOS Homebrew & System",
            category="Desktop & System",
            type="runtime",
            path=str(brew_bin) if brew_exists else "/Applications",
            size_bytes=500 * 1024 * 1024,
            size_human="macOS Core",
            last_used="Active",
            days_inactive=0,
            status="active",
            notes=f"Apple macOS Darwin ({platform.release()}) package management & desktop",
            val=18.0
        ))

        # Check /Applications
        mac_apps = [
            ("Visual Studio Code.app", "VS Code IDE", 400),
            ("Docker.app", "Docker Desktop for Mac", 1200),
            ("Google Chrome.app", "Google Chrome", 350),
            ("Slack.app", "Slack", 250),
        ]
        for app_file, label, mb in mac_apps:
            app_p = Path("/Applications") / app_file
            if app_p.exists():
                a_id = f"app:{app_file.lower().replace('.app', '')}"
                nodes.append(Node(
                    id=a_id,
                    name=label,
                    category="Desktop & System",
                    type="desktop-app",
                    path=str(app_p),
                    size_bytes=mb * 1024 * 1024,
                    size_human=f"~{mb} MB",
                    last_used="Active",
                    days_inactive=0,
                    status="active",
                    notes="macOS native application",
                    val=16.0
                ))
                links.append(Link(source=primary_os_id, target=a_id, relationship="Desktop App", description=f"macOS runs {label}"))

    elif current_os == "Windows":
        # Windows System & Winget / Scoop
        nodes.append(Node(
            id=primary_os_id,
            name="Windows System & Winget",
            category="Desktop & System",
            type="runtime",
            path="C:\\Windows\\System32",
            size_bytes=800 * 1024 * 1024,
            size_human="Windows Core",
            last_used="Active",
            days_inactive=0,
            status="active",
            notes=f"Microsoft Windows ({platform.release()}) package management & runtime",
            val=18.0
        ))

        # Check common Windows program directories
        prog_dirs = [
            Path(os.environ.get("ProgramFiles", "C:\\Program Files")),
            Path(os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local"))) / "Programs"
        ]
        for pdir in prog_dirs:
            if pdir.exists():
                vscode_win = pdir / "Microsoft VS Code"
                if vscode_win.exists():
                    nodes.append(Node(
                        id="app:vscode",
                        name="VS Code & Extensions",
                        category="Desktop & System",
                        type="ide",
                        path=str(vscode_win),
                        size_bytes=900 * 1024 * 1024,
                        size_human="~900 MB",
                        last_used="Active",
                        days_inactive=0,
                        status="active",
                        notes="VS Code IDE on Windows",
                        val=20.0
                    ))
                    links.append(Link(source=primary_os_id, target="app:vscode", relationship="Native IDE", description="Windows native installation of VS Code"))

    else:
        # Linux (Ubuntu / Debian / Fedora / Arch)
        snap_rt_id = "runtime:snapd"
        apt_rt_id = "runtime:apt"
        primary_os_id = apt_rt_id

        nodes.append(Node(
            id=snap_rt_id,
            name="Canonical Snap Runtime",
            category="Desktop & System",
            type="runtime",
            path="/snap",
            size_bytes=500 * 1024 * 1024,
            size_human="~500 MB",
            last_used="Active",
            days_inactive=0,
            status="active",
            notes="Containerized desktop & CLI application daemon",
            val=18.0
        ))

        nodes.append(Node(
            id=apt_rt_id,
            name="Ubuntu APT System",
            category="Desktop & System",
            type="runtime",
            path="/usr/bin/dpkg",
            size_bytes=800 * 1024 * 1024,
            size_human="System",
            last_used="Active",
            days_inactive=0,
            status="active",
            notes="Native Debian/Ubuntu package manager",
            val=18.0
        ))

        # Snap Applications & Wine
        try:
            res = subprocess.run(["snap", "list"], capture_output=True, text=True)
            if res.returncode == 0:
                snap_lines = [l.split() for l in res.stdout.strip().split("\n")[1:] if l]
                snap_names = [parts[0] for parts in snap_lines if parts]

                wine_runtimes = [n for n in snap_names if "wine" in n]
                if wine_runtimes:
                    wine_cluster_id = "snap-runtime:wine"
                    nodes.append(Node(
                        id=wine_cluster_id,
                        name=f"Wine Runtimes ({len(wine_runtimes)} layers)",
                        category="Desktop & System",
                        type="snap-runtime",
                        path="/snap/wine-platform-*",
                        size_bytes=1500 * 1024 * 1024,
                        size_human="~1.5 GB",
                        last_used="Active",
                        days_inactive=0,
                        status="active",
                        uninstall_cmd="sudo snap remove " + " ".join(wine_runtimes[:2]),
                        notes=f"Windows binary compatibility layers: {', '.join(wine_runtimes[:3])}...",
                        val=26.0
                    ))
                    links.append(Link(
                        source=snap_rt_id,
                        target=wine_cluster_id,
                        relationship="Platform Layer",
                        description="Canonical Snap daemon provides multiple Wine runtime environments for Windows binaries"
                    ))

                if "notepad-plus-plus" in snap_names:
                    npp_id = "snap:notepad-plus-plus"
                    nodes.append(Node(
                        id=npp_id,
                        name="Notepad++ (Snap)",
                        category="Desktop & System",
                        type="snap-app",
                        path="/snap/notepad-plus-plus",
                        size_bytes=60 * 1024 * 1024,
                        size_human="~60 MB (+1.5GB Wine)",
                        last_used="Active",
                        days_inactive=2,
                        status="active",
                        uninstall_cmd="sudo snap remove notepad-plus-plus",
                        notes="Text editor running via Wine translation layer in Snap container",
                        val=12.0
                    ))
                    if wine_runtimes:
                        links.append(Link(
                            source=wine_cluster_id,
                            target=npp_id,
                            relationship="Windows Emulation Layer",
                            description="Translates Windows system calls so Notepad++ can execute seamlessly on Linux"
                        ))

                if "steam" in snap_names:
                    steam_id = "snap:steam"
                    nodes.append(Node(
                        id=steam_id,
                        name="Steam Gaming Client",
                        category="Desktop & System",
                        type="snap-app",
                        path="/snap/steam",
                        size_bytes=1200 * 1024 * 1024,
                        size_human="~1.2 GB",
                        last_used="Active",
                        days_inactive=5,
                        status="active",
                        uninstall_cmd="sudo snap remove steam",
                        notes="Steam client (uses gaming-graphics-core24 & mesa-2404)",
                        val=22.0
                    ))
                    links.append(Link(
                        source=snap_rt_id,
                        target=steam_id,
                        relationship="Containerized App",
                        description="Snap sandbox runs Steam with access to hardware 3D acceleration and Mesa drivers"
                    ))

                for media_app, size_str, mb_val in [("gimp", "GIMP Image Editor", 450), ("vlc", "VLC Media Player", 380)]:
                    if media_app in snap_names:
                        m_id = f"snap:{media_app}"
                        nodes.append(Node(
                            id=m_id,
                            name=size_str,
                            category="Desktop & System",
                            type="snap-app",
                            path=f"/snap/{media_app}",
                            size_bytes=mb_val * 1024 * 1024,
                            size_human=f"~{mb_val} MB",
                            last_used="Active",
                            days_inactive=15,
                            status="inactive",
                            uninstall_cmd=f"sudo snap remove {media_app}",
                            notes="Desktop application via Snap",
                            val=15.0
                        ))
                        links.append(Link(
                            source=snap_rt_id,
                            target=m_id,
                            relationship="Sandboxed Desktop App",
                            description=f"Snap daemon isolates and executes {size_str}"
                        ))
        except Exception:
            pass

        # Standalone Heavyweights on Linux / cross-platform (CPLEX, LaTeX, Docker)
        cplex_candidates = [home / "IBMcplex", Path("/opt/ibm/ILOG"), Path("/Applications/CPLEX_Studio"), Path("C:/Program Files/IBM/ILOG")]
        for c_cand in cplex_candidates:
            if c_cand.exists():
                size_bytes, mtime = get_dir_size_and_mtime(c_cand, max_depth=3)
                date_str, days, status = calculate_age_and_status(mtime)
                cplex_id = "app:cplex"
                del_cmd = f"rmdir /s /q \"{c_cand}\"" if is_win else f"rm -rf '{c_cand}'"
                nodes.append(Node(
                    id=cplex_id,
                    name="IBM CPLEX Optimization Studio",
                    category="Data Science & ML",
                    type="standalone",
                    path=str(c_cand),
                    size_bytes=size_bytes,
                    size_human=format_size(size_bytes),
                    last_used=date_str,
                    days_inactive=days,
                    status=status,
                    uninstall_cmd=del_cmd,
                    notes="Mathematical programming solver (OPL, Concert, JRE runtime)",
                    val=size_to_radius(size_bytes)
                ))
                break

        latex_id = "suite:latex"
        nodes.append(Node(
            id=latex_id,
            name="LaTeX Suite (XeTeX & Texmaker)",
            category="Desktop & System",
            type="apt-suite",
            path="/usr/bin/xelatex",
            size_bytes=850 * 1024 * 1024,
            size_human="~850 MB",
            last_used="Active",
            days_inactive=1,
            status="active",
            notes="Document typesetting engine used for CVs and academic papers",
            val=18.0
        ))
        links.append(Link(
            source=apt_rt_id,
            target=latex_id,
            relationship="System Package Suite",
            description="Ubuntu APT packages provide XeTeX compiler and Texmaker for document processing"
        ))

        docker_id = "suite:docker"
        nodes.append(Node(
            id=docker_id,
            name="Docker Engine & Compose",
            category="Desktop & System",
            type="apt-suite",
            path="/usr/bin/docker",
            size_bytes=480 * 1024 * 1024,
            size_human="~480 MB",
            last_used="Active",
            days_inactive=2,
            status="active",
            notes="Container virtualization platform",
            val=16.0
        ))
        links.append(Link(
            source=apt_rt_id,
            target=docker_id,
            relationship="Daemon & Plugins",
            description="Ubuntu APT daemon manages Docker engine, CLI, and Compose container runtime"
        ))

    # --- 2. CROSS-PLATFORM DEVELOPER TOOLS & CACHES (Linux, macOS, Windows) ---
    # VS Code Extensions & Config
    vscode_candidates = [
        home / ".vscode",
        home / "Library" / "Application Support" / "Code",
        home / "AppData" / "Roaming" / "Code"
    ]
    for vdir in vscode_candidates:
        if vdir.exists() and "app:vscode" not in [n.id for n in nodes]:
            v_size = get_fast_size(vdir)
            nodes.append(Node(
                id="app:vscode",
                name="VS Code & Extensions",
                category="Desktop & System",
                type="ide",
                path=str(vdir),
                size_bytes=v_size,
                size_human=format_size(v_size),
                last_used="Active",
                days_inactive=0,
                status="active",
                notes="VS Code IDE extensions (Python, Antigravity, Docker, GitLens) & configs",
                val=20.0
            ))
            links.append(Link(
                source=primary_os_id,
                target="app:vscode",
                relationship="Native IDE",
                description="Desktop editor installation running development extensions and language servers"
            ))
            break

    # NPM Global Cache
    npm_candidates = [
        home / ".npm",
        home / "AppData" / "Local" / "npm-cache"
    ]
    for ndir in npm_candidates:
        if ndir.exists():
            npm_size = get_fast_size(ndir)
            nodes.append(Node(
                id="cache:npm",
                name="NPM Download Cache",
                category="Fullstack Web",
                type="cache",
                path=str(ndir),
                size_bytes=npm_size,
                size_human=format_size(npm_size),
                last_used="Active",
                days_inactive=1,
                status="active",
                uninstall_cmd="npm cache clean --force",
                notes="Global npm tarball & metadata cache (reclaimable disk space)",
                val=18.0
            ))
            links.append(Link(
                source="runtime:node",
                target="cache:npm",
                relationship="Package Cache",
                description="Node.js npm stores downloaded tarballs and registry metadata in npm cache"
            ))
            break

    # AI Codex Agent Runtime Bundle
    codex_candidates = [
        home / ".cache" / "codex-runtimes",
        home / "Library" / "Caches" / "codex-runtimes"
    ]
    for cdir in codex_candidates:
        if cdir.exists():
            c_size = get_fast_size(cdir)
            nodes.append(Node(
                id="runtime:codex",
                name="Codex Agent Runtime",
                category="AI & Agents",
                type="agent-runtime",
                path=str(cdir),
                size_bytes=c_size,
                size_human=format_size(c_size),
                last_used="Active",
                days_inactive=3,
                status="active",
                notes="Bundled headless LibreOffice, pnpm 11, Node 24, and Poppler agent runtime",
                val=22.0
            ))
            links.append(Link(
                source="runtime:node",
                target="runtime:codex",
                relationship="Agent Sub-runtime",
                description="Autonomous agent runtime bundle with bundled LibreOffice, pnpm 11, and Poppler"
            ))
            break

    # Antigravity CLI Engine
    gemini_candidates = [
        home / ".gemini",
        home / ".antigravity"
    ]
    for gdir in gemini_candidates:
        if gdir.exists():
            g_size = get_fast_size(gdir)
            nodes.append(Node(
                id="runtime:antigravity",
                name="Antigravity CLI Engine",
                category="AI & Agents",
                type="agent-runtime",
                path=str(gdir),
                size_bytes=g_size,
                size_human=format_size(g_size),
                last_used="Active",
                days_inactive=0,
                status="active",
                notes="Antigravity CLI binaries, sidecars, skills, and background tasks",
                val=20.0
            ))
            links.append(Link(
                source="runtime:node",
                target="runtime:antigravity",
                relationship="CLI Runtime",
                description="Core Antigravity CLI execution engine and MCP background sidecars"
            ))
            break

    # Antigravity Standalone IDE (Electron)
    ag_candidates = [
        home / "Antigravity-x64",
        home / ".local/share/Antigravity",
        Path("/opt/Antigravity"),
        Path("/Applications/Antigravity.app"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Antigravity" if os.environ.get("LOCALAPPDATA") else None
    ]
    for ag_dir in ag_candidates:
        if ag_dir and ag_dir.exists():
            ag_size, ag_mtime = get_dir_size_and_mtime(ag_dir, max_depth=3)
            ag_date, ag_days, ag_status = calculate_age_and_status(ag_mtime)
            del_cmd = f"rmdir /s /q \"{ag_dir}\"" if is_win else f"rm -rf '{ag_dir}'"
            nodes.append(Node(
                id="app:antigravity",
                name="Antigravity IDE",
                category="AI & Agents",
                type="standalone",
                path=str(ag_dir),
                size_bytes=ag_size,
                size_human=format_size(ag_size),
                last_used=ag_date,
                days_inactive=ag_days,
                status=ag_status,
                uninstall_cmd=del_cmd,
                notes="Primary Agentic Coding IDE (Electron runtime)",
                val=22.0
            ))
            links.append(Link(
                source="runtime:antigravity",
                target="app:antigravity",
                relationship="IDE Engine",
                description="Antigravity CLI provides language server and agent capabilities to Antigravity IDE"
            ))
            break

    # GPU Hardware Accelerator (NVIDIA or Apple Silicon)
    if current_os == "Darwin":
        try:
            sp = subprocess.check_output(["system_profiler", "SPDisplaysDataType"], stderr=subprocess.DEVNULL, text=True)
            for line in sp.splitlines():
                if "Chipset Model:" in line:
                    chip = line.split(":", 1)[1].strip()
                    nodes.append(Node(
                        id="hw:apple-gpu",
                        name=f"Apple {chip} GPU",
                        category="Desktop & System",
                        type="hardware",
                        path="/System/Library/Extensions/AppleMetal*",
                        size_bytes=8192 * 1024 * 1024,
                        size_human="Unified Memory",
                        last_used="Active",
                        days_inactive=0,
                        status="active",
                        notes=f"Apple Metal hardware GPU accelerator for MPS & PyTorch",
                        val=24.0
                    ))
                    links.append(Link(source="hw:apple-gpu", target="runtime:python", relationship="Metal Acceleration", description="Powers PyTorch MPS hardware acceleration on Apple Silicon"))
                    break
        except Exception:
            pass
    else:
        # Check NVIDIA GPU via nvidia-smi
        try:
            smi = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                stderr=subprocess.DEVNULL, text=True
            ).strip()
            if smi:
                gpu_name = smi.split(",")[0].strip()
                drv_ver = smi.split(",")[-1].strip()
                nodes.append(Node(
                    id="hw:nvidia-gpu",
                    name=f"{gpu_name} (4 GB)",
                    category="Desktop & System",
                    type="hardware",
                    path="/dev/nvidia0" if current_os == "Linux" else "NVIDIA Driver",
                    size_bytes=4096 * 1024 * 1024,
                    size_human="4 GB VRAM",
                    last_used="Active",
                    days_inactive=0,
                    status="active",
                    notes=f"GPU hardware compute accelerator (Driver {drv_ver}) for CUDA & PyTorch",
                    val=24.0
                ))
                links.append(Link(
                    source="hw:nvidia-gpu",
                    target="runtime:python",
                    relationship="CUDA Hardware Acceleration",
                    description="Powers PyTorch and CUDA tensor operations on GPU hardware"
                ))
                links.append(Link(
                    source="hw:nvidia-gpu",
                    target="snap:steam",
                    relationship="3D Graphics Pipeline",
                    description="Supplies hardware graphics acceleration to Steam and gaming client"
                ))
        except Exception:
            pass

    return nodes, links
