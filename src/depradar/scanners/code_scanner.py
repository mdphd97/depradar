"""AST & Static Code Analysis Scanner for DepRadar.
Parses source files (.py, .ts, .js) to discover deep imported third-party libraries.
"""

import os
import ast
import re
import json
import sys
from pathlib import Path
from typing import List, Tuple, Set
from ..models import Node, Link

# Common Python Standard Library modules to filter out
STDLIB_MODULES = {
    "abc", "argparse", "array", "ast", "asyncio", "base64", "collections",
    "concurrent", "contextlib", "copy", "csv", "ctypes", "datetime",
    "decimal", "difflib", "dis", "distutils", "email", "enum", "errno",
    "fnmatch", "functools", "gc", "getopt", "getpass", "glob", "gzip",
    "hashlib", "heapq", "hmac", "html", "http", "importlib", "inspect",
    "io", "itertools", "json", "logging", "math", "multiprocessing",
    "operator", "os", "pathlib", "pickle", "platform", "pprint", "queue",
    "random", "re", "shlex", "shutil", "signal", "site", "socket",
    "sqlite3", "ssl", "stat", "string", "struct", "subprocess", "sys",
    "tempfile", "threading", "time", "traceback", "types", "typing",
    "unittest", "urllib", "uuid", "warnings", "weakref", "xml", "zipfile", "zlib"
}

# Domain knowledge base for imported third-party library roles & usages
KNOWN_LIBRARY_ROLES = {
    "selenium": ("Browser Automation", "Automates multi-tab browser control, DOM clicks, and stealth refresh interactions"),
    "undetected_chromedriver": ("Stealth Driver", "Bypasses anti-bot challenges and Cloudflare Turnstile for automated tab loading"),
    "requests": ("HTTP Client", "Performs synchronous HTTP requests, queries REST endpoints, and fetches remote pages"),
    "urllib3": ("HTTP Transport", "Low-level connection pooling and socket management for HTTP traffic"),
    "pysocks": ("Proxy Tunneling", "Directs automated browser or script traffic through SOCKS5 proxy networks"),
    "zarr": ("Microscopy Tensor Storage", "Reads and writes compressed, chunked multi-dimensional biological image arrays"),
    "blosc2": ("Fast Tensor Compression", "High-throughput codec for compressing and decompressing cell imaging arrays"),
    "numpy": ("Numerical Matrices", "Performs vectorized matrix calculations, coordinate transforms, and array operations"),
    "pandas": ("Tabular Data Science", "Dataframe operations, feature engineering, and competition data preprocessing"),
    "scipy": ("Scientific Computing", "Applies spatial algorithms, morphological transformations, and distance metrics"),
    "contourpy": ("Contour Computation", "Extracts polygon contours and boundaries for image segmentation masks"),
    "matplotlib": ("Visualization", "Renders diagnostic loss plots, cell image overlays, and visual analytics"),
    "jupyter": ("Notebook Environment", "Executes interactive analysis cells and exploratory data analysis"),
    "torch": ("Deep Learning Framework", "PyTorch GPU tensor computation and neural network model training"),
    "torchvision": ("Computer Vision Models", "Pretrained vision backbones and image augmentation pipelines"),
    "playwright": ("Headless Browser Engine", "Orchestrates headless Chromium and browser workers for web automation"),
    "@google/generative-ai": ("Gemini LLM Inference", "Connects to Google Gemini API for prompt processing and structured generation"),
    "@supabase/supabase-js": ("PostgreSQL Database & Auth", "Performs database queries and handles user session authentication"),
    "next": ("React Application Framework", "Next.js App Router, React Server Components, and SSR architecture"),
    "react": ("UI Component Library", "Declarative UI rendering engine and component lifecycle management"),
    "react-dom": ("DOM Rendering", "Mounts and synchronizes React virtual DOM components into browser DOM"),
    "lucide-react": ("Vector Icon Library", "Supplies SVG iconography for buttons, navigation, and state indicators"),
    "browser-image-compression": ("Client-side Image Optimization", "Compresses uploaded images in the browser before storage upload"),
    "js-yaml": ("YAML Schema Parser", "Parses pipeline configurations, prompt templates, and job schemas"),
    "dotenv": ("Environment Credentials", "Loads secret API keys and environment variables securely from .env files"),
    "undici": ("High-Performance HTTP Client", "Fast HTTP/1.1 and HTTP/2 fetch client for Node.js microservices"),
    "winston": ("Logger Framework", "Structured application and error logging for daemon bots"),
    "puppeteer": ("Headless Chrome Engine", "Automates Chrome page interaction, clicking, and scraping flows"),
    "beautifulsoup4": ("HTML DOM Parsing", "Parses webpage markup and extracts pricing and stock availability"),
    "bs4": ("HTML DOM Parsing", "Parses webpage markup and extracts pricing and stock availability"),
    "geff": ("Lineage Graph Codec", "Parses and serializes GEFF lineage graphs for biological cell division tracking"),
    "ipykernel": ("Jupyter Kernel Core", "Connects Jupyter notebook client to Python execution environment")
}

def extract_python_imports(file_path: Path) -> Set[str]:
    imports = set()
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(content, filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    pkg = alias.name.split(".")[0]
                    if pkg and pkg not in STDLIB_MODULES and not pkg.startswith("_"):
                        imports.add(pkg)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    pkg = node.module.split(".")[0]
                    if pkg and pkg not in STDLIB_MODULES and not pkg.startswith("_") and node.level == 0:
                        imports.add(pkg)
    except Exception:
        pass
    return imports

def extract_notebook_imports(file_path: Path) -> Set[str]:
    imports = set()
    try:
        data = json.loads(file_path.read_text(encoding="utf-8", errors="ignore"))
        for cell in data.get("cells", []):
            if cell.get("cell_type") == "code":
                lines = [l for l in cell.get("source", []) if not l.strip().startswith(("%", "!"))]
                try:
                    tree = ast.parse("".join(lines))
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                pkg = alias.name.split(".")[0]
                                if pkg and pkg not in STDLIB_MODULES and not pkg.startswith("_"):
                                    imports.add(pkg)
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                pkg = node.module.split(".")[0]
                                if pkg and pkg not in STDLIB_MODULES and not pkg.startswith("_") and node.level == 0:
                                    imports.add(pkg)
                except Exception:
                    pass
    except Exception:
        pass
    return imports

def extract_pyproject_deps(proj_dir: Path) -> Set[str]:
    deps = set()
    pyproj = proj_dir / "pyproject.toml"
    if pyproj.exists():
        try:
            content = pyproj.read_text(encoding="utf-8", errors="ignore")
            in_deps = False
            for line in content.splitlines():
                if "dependencies" in line and "=" in line:
                    in_deps = True
                elif in_deps:
                    if "]" in line:
                        in_deps = False
                    m = re.search(r'["\']([a-zA-Z0-9_\-]+)', line)
                    if m:
                        pkg = m.group(1).lower().replace("-", "_")
                        if pkg and pkg not in STDLIB_MODULES:
                            deps.add(pkg)
        except Exception:
            pass
    return deps

def is_valid_pkg_name(name: str) -> bool:
    if not name or len(name) > 64 or any(c in name for c in [" ", "\n", "\r", "\t", "*", "?", ":", "<", ">", "|"]):
        return False
    return bool(re.match(r"^(@[a-zA-Z0-9_\-]+\/)?[a-zA-Z0-9_\-\.]+$", name))

def extract_js_imports(file_path: Path) -> Set[str]:
    imports = set()
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        # Match ES6 imports: from 'pkg' or from "pkg"
        for m in re.finditer(r'from\s+[\'"]([@a-zA-Z0-9_\-\.\/]+)[\'"]', content):
            spec = m.group(1).strip()
            if spec.startswith((".", "/")):
                continue
            if spec.startswith("@") and "/" in spec:
                parts = spec.split("/")
                pkg = f"{parts[0]}/{parts[1]}"
            else:
                pkg = spec.split("/")[0]
            if is_valid_pkg_name(pkg):
                imports.add(pkg)

        # Match require('pkg')
        for m in re.finditer(r'require\(\s*[\'"]([@a-zA-Z0-9_\-\.\/]+)[\'"]\s*\)', content):
            spec = m.group(1).strip()
            if spec.startswith((".", "/")):
                continue
            if spec.startswith("@") and "/" in spec:
                parts = spec.split("/")
                pkg = f"{parts[0]}/{parts[1]}"
            else:
                pkg = spec.split("/")[0]
            if is_valid_pkg_name(pkg):
                imports.add(pkg)
    except Exception:
        pass
    return imports

def scan_code_imports(home: Path, target_projects: List[Tuple[str, str, Path]]) -> Tuple[List[Node], List[Link]]:
    """
    Scans project source files via AST to extract direct code imports.
    target_projects: [(project_id, category, project_path)]
    """
    nodes: List[Node] = []
    links: List[Link] = []
    discovered_pkgs: Set[str] = set()

    for proj_id, category, proj_dir in target_projects:
        if not proj_dir.exists():
            continue

        imported_libs: Set[str] = set()

        # Traverse source files
        for root, dirs, files in os.walk(proj_dir):
            dirs[:] = [d for d in dirs if d not in [".git", "node_modules", ".venv", "venv", "__pycache__", ".next", "dist"]]
            for f in files:
                fp = Path(root) / f
                if f.endswith(".py"):
                    imported_libs.update(extract_python_imports(fp))
                elif f.endswith(".ipynb"):
                    imported_libs.update(extract_notebook_imports(fp))
                elif f.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs")):
                    imported_libs.update(extract_js_imports(fp))

        # Also collect declared dependencies from pyproject.toml
        imported_libs.update(extract_pyproject_deps(proj_dir))

        # Add code package nodes and links
        for lib in imported_libs:
            pkg_id = f"pkg:{lib}"
            if pkg_id not in discovered_pkgs:
                discovered_pkgs.add(pkg_id)
                role, usage = KNOWN_LIBRARY_ROLES.get(lib, ("Code Library", f"Imported by {proj_dir.name} source code"))
                nodes.append(Node(
                    id=pkg_id,
                    name=lib,
                    category=category,
                    type="code-import",
                    path=f"Imported in {proj_dir.name}",
                    size_bytes=5 * 1024 * 1024,
                    size_human="Library",
                    last_used="Active",
                    days_inactive=0,
                    status="active",
                    notes=f"{role}: {usage}",
                    val=8.0
                ))

            # Link project to imported package with rich relationship & usage description
            role, usage = KNOWN_LIBRARY_ROLES.get(lib, ("Imports Library", f"Direct code dependency of {proj_dir.name}"))
            links.append(Link(
                source=proj_id,
                target=pkg_id,
                relationship=role,
                description=f"{proj_dir.name} uses {lib}: {usage}"
            ))

    return nodes, links
