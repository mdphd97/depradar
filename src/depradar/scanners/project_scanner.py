"""Dynamic Scanner for projects, workspaces, and code repositories across Linux, macOS, and Windows.
Discovers developer projects automatically from package manifests (package.json, pyproject.toml, Cargo.toml, go.mod).
"""

import os
from pathlib import Path
from typing import List, Tuple, Set
from ..models import Node, Link
from .base import get_dir_size_and_mtime, format_size, calculate_age_and_status, size_to_radius

def detect_project_details(proj_dir: Path) -> Tuple[bool, str, str, str]:
    """Detects whether a directory is a software project, and infers category and role."""
    is_project = False
    cat = "Fullstack Web"
    notes = "Software project"
    primary_runtime = "runtime:node"

    # Node.js / Web Application
    pkg_json = proj_dir / "package.json"
    if pkg_json.exists():
        is_project = True
        primary_runtime = "runtime:node"
        cat = "Fullstack Web"
        notes = "Node.js / Web Application workspace"
        try:
            content = pkg_json.read_text(encoding="utf-8", errors="ignore").lower()
            if any(k in content for k in ["gemini", "openai", "agent", "langchain", "anthropic"]):
                cat = "AI & Agents"
                notes = "AI & Agent application workspace"
            elif any(k in content for k in ["puppeteer", "playwright", "scrape", "bot", "crawler"]):
                cat = "Automation & Scraping"
                notes = "Automated scraping & worker bot"
            elif any(k in content for k in ["next", "react", "vue", "svelte", "nuxt"]):
                cat = "Fullstack Web"
                notes = "Frontend / Fullstack web application"
        except Exception:
            pass

    # Python Projects
    pyproject = proj_dir / "pyproject.toml"
    reqs = proj_dir / "requirements.txt"
    if pyproject.exists() or reqs.exists() or (proj_dir / "setup.py").exists() or (proj_dir / "Pipfile").exists():
        is_project = True
        primary_runtime = "runtime:python"
        cat = "Data Science & ML" if any(k in proj_dir.name.lower() for k in ["ml", "data", "model", "kaggle", "cell", "train"]) else "Automation & Scraping"
        notes = "Python development workspace"
        try:
            sample_content = ""
            if pyproject.exists():
                sample_content += pyproject.read_text(encoding="utf-8", errors="ignore").lower()
            if reqs.exists():
                sample_content += reqs.read_text(encoding="utf-8", errors="ignore").lower()

            if any(k in sample_content for k in ["torch", "tensorflow", "scipy", "numpy", "pandas", "zarr", "blosc2", "sklearn"]):
                cat = "Data Science & ML"
                notes = "Data Science / Machine Learning workspace"
            elif any(k in sample_content for k in ["selenium", "undetected", "beautifulsoup", "playwright", "requests", "scrapy"]):
                cat = "Automation & Scraping"
                notes = "Automated scraper & browser automation workspace"
            elif any(k in sample_content for k in ["fastapi", "flask", "django"]):
                cat = "Fullstack Web"
                notes = "Python web service workspace"
            elif any(k in sample_content for k in ["agent", "langchain", "llamaindex", "crewai"]):
                cat = "AI & Agents"
                notes = "AI agent & LLM workflow workspace"
        except Exception:
            pass

    # Rust Projects
    if (proj_dir / "Cargo.toml").exists():
        is_project = True
        cat = "Desktop & System"
        notes = "Rust language project"
        primary_runtime = "runtime:os"

    # Go Projects
    if (proj_dir / "go.mod").exists():
        is_project = True
        cat = "Desktop & System"
        notes = "Go language microservice"
        primary_runtime = "runtime:os"

    return is_project, cat, notes, primary_runtime

def scan_projects(home: Path) -> Tuple[List[Node], List[Link]]:
    nodes: List[Node] = []
    links: List[Link] = []
    seen_paths: Set[str] = set()

    # Search candidates across common developer workspaces
    search_dirs = [
        Path.cwd(),
        home,
        home / "Projects",
        home / "Developer",
        home / "workspace",
        home / "repos",
        home / "src",
        home / "Documents" / "GitHub",
        home / "Documents"
    ]

    for sdir in search_dirs:
        if not sdir.exists():
            continue

        # Check the directory itself
        if sdir != home:
            is_proj, p_cat, p_notes, p_runtime = detect_project_details(sdir)
            resolved = str(sdir.resolve())
            if is_proj and resolved not in seen_paths:
                seen_paths.add(resolved)
                p_id = f"project:{sdir.name}"
                size_bytes, mtime = get_dir_size_and_mtime(sdir, max_depth=2)
                date_str, days, status = calculate_age_and_status(mtime)

                nodes.append(Node(
                    id=p_id,
                    name=f"{sdir.name} Workspace",
                    category=p_cat,
                    type="project",
                    path=str(sdir),
                    size_bytes=size_bytes,
                    size_human=format_size(size_bytes),
                    last_used=date_str,
                    days_inactive=days,
                    status=status,
                    notes=p_notes,
                    val=size_to_radius(size_bytes)
                ))
                links.append(Link(
                    source=p_runtime,
                    target=p_id,
                    relationship="Runtime Host",
                    description=f"{p_runtime.replace('runtime:', '').capitalize()} executes {sdir.name} workspace"
                ))

        # Check direct subdirectories
        try:
            for item in sdir.iterdir():
                if item.is_dir() and not item.name.startswith((".", "node_modules", ".cache", "snap", "AppData", "Library")):
                    resolved = str(item.resolve())
                    if resolved in seen_paths:
                        continue

                    is_proj, p_cat, p_notes, p_runtime = detect_project_details(item)
                    if is_proj:
                        seen_paths.add(resolved)
                        p_id = f"project:{item.name}"
                        size_bytes, mtime = get_dir_size_and_mtime(item, max_depth=2)
                        date_str, days, status = calculate_age_and_status(mtime)

                        nodes.append(Node(
                            id=p_id,
                            name=f"{item.name} Workspace",
                            category=p_cat,
                            type="project",
                            path=str(item),
                            size_bytes=size_bytes,
                            size_human=format_size(size_bytes),
                            last_used=date_str,
                            days_inactive=days,
                            status=status,
                            notes=p_notes,
                            val=size_to_radius(size_bytes)
                        ))
                        links.append(Link(
                            source=p_runtime,
                            target=p_id,
                            relationship="Runtime Host",
                            description=f"Executes {item.name} project dependencies and processes"
                        ))

                        # Cross-tool integration checks
                        if any(f.suffix == ".tex" for f in item.glob("*.tex")):
                            links.append(Link(
                                source="suite:latex",
                                target=p_id,
                                relationship="Typesetting Engine",
                                description=f"LaTeX engine compiles document templates in {item.name}"
                            ))

                        if (item / "kernel-metadata.json").exists():
                            links.append(Link(
                                source="uv-tool:kaggle",
                                target=p_id,
                                relationship="Dataset Sync",
                                description=f"Kaggle CLI syncs competition datasets and kernels for {item.name}"
                            ))
        except Exception:
            pass

    return nodes, links
