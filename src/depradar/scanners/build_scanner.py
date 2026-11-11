"""Build Artifact and Multi-Toolchain Scanner for DepRadar.
Discovers heavy compiled language build directories and global package caches:
- Rust Cargo projects ('target/' directories, global crate registry cache)
- Go module cache ('~/go/pkg/mod') and build cache
- Java / Kotlin Gradle caches ('~/.gradle/caches') and Maven repository ('~/.m2/repository')
- Web framework build outputs ('.next', '.turbo', '.nuxt')
"""

import os
import shutil
import platform
from pathlib import Path
from typing import List, Tuple, Set
from ..models import Node, Link
from .base import get_dir_size_and_mtime, format_size, calculate_age_and_status, size_to_radius

def scan_build_artifacts(home: Path) -> Tuple[List[Node], List[Link]]:
    nodes: List[Node] = []
    links: List[Link] = []
    is_win = platform.system() == "Windows"

    # --- 1. RUST TOOLCHAIN & BUILD ARTIFACTS ---
    cargo_bin = shutil.which("cargo") or (home / ".cargo" / "bin" / ("cargo.exe" if is_win else "cargo"))
    rust_runtime_id = "runtime:rust"
    rust_installed = False

    if isinstance(cargo_bin, Path) and cargo_bin.exists():
        rust_installed = True
    elif isinstance(cargo_bin, str):
        rust_installed = True

    if rust_installed:
        nodes.append(Node(
            id=rust_runtime_id,
            name="Rust & Cargo Toolchain",
            category="Desktop & System",
            type="runtime",
            path=str(cargo_bin) if isinstance(cargo_bin, (Path, str)) else "cargo",
            size_bytes=450 * 1024 * 1024,
            size_human="~450 MB",
            last_used="Active",
            days_inactive=1,
            status="active",
            notes="Systems programming compiler (rustc, cargo package manager, LLVM backend)",
            val=18.0
        ))
        links.append(Link(
            source="runtime:os",
            target=rust_runtime_id,
            relationship="Toolchain",
            description="Host system provides rustc compiler and cargo toolchain"
        ))

        # Cargo Global Registry Cache (~/.cargo/registry/cache)
        cargo_reg_cache = home / ".cargo" / "registry" / "cache"
        if cargo_reg_cache.exists():
            c_size, c_mtime = get_dir_size_and_mtime(cargo_reg_cache, max_depth=3)
            if c_size > 5 * 1024 * 1024:  # > 5 MB
                c_date, c_days, c_status = calculate_age_and_status(c_mtime)
                cargo_cache_id = "cache:cargo:crates"
                del_cmd = f"rmdir /s /q \"{cargo_reg_cache}\"" if is_win else f"rm -rf '{cargo_reg_cache}'"
                nodes.append(Node(
                    id=cargo_cache_id,
                    name="Cargo Crates Download Cache",
                    category="Desktop & System",
                    type="build-cache",
                    path=str(cargo_reg_cache),
                    size_bytes=c_size,
                    size_human=format_size(c_size),
                    last_used=c_date,
                    days_inactive=c_days,
                    status=c_status,
                    uninstall_cmd=del_cmd,
                    notes="Downloaded crate tarballs from crates.io registry",
                    val=size_to_radius(c_size)
                ))
                links.append(Link(
                    source=rust_runtime_id,
                    target=cargo_cache_id,
                    relationship="Package Cache",
                    description="Cargo downloads and caches compressed crate archives"
                ))

    # --- 2. GO RUNTIME & MODULE CACHES ---
    go_bin = shutil.which("go") or (home / "go" / "bin" / ("go.exe" if is_win else "go"))
    go_runtime_id = "runtime:go"
    go_installed = False

    if isinstance(go_bin, Path) and go_bin.exists():
        go_installed = True
    elif isinstance(go_bin, str):
        go_installed = True

    if go_installed:
        nodes.append(Node(
            id=go_runtime_id,
            name="Go Runtime & Toolchain",
            category="Desktop & System",
            type="runtime",
            path=str(go_bin) if isinstance(go_bin, (Path, str)) else "go",
            size_bytes=380 * 1024 * 1024,
            size_human="~380 MB",
            last_used="Active",
            days_inactive=1,
            status="active",
            notes="Compiled backend language runtime, compiler, and module manager",
            val=16.0
        ))
        links.append(Link(
            source="runtime:os",
            target=go_runtime_id,
            relationship="Toolchain",
            description="Host system provides Go compiler and module runtime"
        ))

        # Go Module Cache ($GOPATH/pkg/mod or ~/go/pkg/mod)
        gopath_env = os.environ.get("GOPATH")
        gopath = Path(gopath_env) if gopath_env else (home / "go")
        go_mod_cache = gopath / "pkg" / "mod"
        if go_mod_cache.exists():
            gm_size, gm_mtime = get_dir_size_and_mtime(go_mod_cache, max_depth=3)
            if gm_size > 5 * 1024 * 1024:
                gm_date, gm_days, gm_status = calculate_age_and_status(gm_mtime)
                go_mod_id = "cache:go:modcache"
                nodes.append(Node(
                    id=go_mod_id,
                    name="Go Module Cache (pkg/mod)",
                    category="Desktop & System",
                    type="build-cache",
                    path=str(go_mod_cache),
                    size_bytes=gm_size,
                    size_human=format_size(gm_size),
                    last_used=gm_date,
                    days_inactive=gm_days,
                    status=gm_status,
                    uninstall_cmd="go clean -modcache",
                    notes="Downloaded and unpacked Go module dependencies",
                    val=size_to_radius(gm_size)
                ))
                links.append(Link(
                    source=go_runtime_id,
                    target=go_mod_id,
                    relationship="Module Cache",
                    description="Go downloads and verifies shared versioned modules"
                ))

        # Go Build Cache (~/.cache/go-build or %LOCALAPPDATA%\go-build)
        go_build_cache = Path(os.environ.get("LOCALAPPDATA", "")) / "go-build" if is_win else (home / ".cache" / "go-build")
        if go_build_cache.exists():
            gb_size, gb_mtime = get_dir_size_and_mtime(go_build_cache, max_depth=3)
            if gb_size > 10 * 1024 * 1024:
                gb_date, gb_days, gb_status = calculate_age_and_status(gb_mtime)
                go_build_id = "cache:go:build"
                nodes.append(Node(
                    id=go_build_id,
                    name="Go Compilation Build Cache",
                    category="Desktop & System",
                    type="build-cache",
                    path=str(go_build_cache),
                    size_bytes=gb_size,
                    size_human=format_size(gb_size),
                    last_used=gb_date,
                    days_inactive=gb_days,
                    status=gb_status,
                    uninstall_cmd="go clean -cache",
                    notes="Compiled package objects and test result cache",
                    val=size_to_radius(gb_size)
                ))
                links.append(Link(
                    source=go_runtime_id,
                    target=go_build_id,
                    relationship="Compiler Cache",
                    description="Cached compilation binaries and hash manifests"
                ))

    # --- 3. GRADLE & MAVEN JVM BUILD CACHES ---
    gradle_cache = home / ".gradle" / "caches"
    if gradle_cache.exists():
        gr_size, gr_mtime = get_dir_size_and_mtime(gradle_cache, max_depth=3)
        if gr_size > 15 * 1024 * 1024:
            gr_date, gr_days, gr_status = calculate_age_and_status(gr_mtime)
            gradle_id = "cache:jvm:gradle"
            del_cmd = f"rmdir /s /q \"{gradle_cache}\"" if is_win else f"rm -rf '{gradle_cache}'"
            nodes.append(Node(
                id=gradle_id,
                name="Gradle Dependency & Build Cache",
                category="Desktop & System",
                type="build-cache",
                path=str(gradle_cache),
                size_bytes=gr_size,
                size_human=format_size(gr_size),
                last_used=gr_date,
                days_inactive=gr_days,
                status=gr_status,
                uninstall_cmd=del_cmd,
                notes="Downloaded JAR artifacts, Gradle distribution wrappers, and execution transforms",
                val=size_to_radius(gr_size)
            ))
            links.append(Link(
                source="runtime:os",
                target=gradle_id,
                relationship="Build Cache",
                description="Gradle stores downloaded dependencies and compiled class artifacts"
            ))

    maven_repo = home / ".m2" / "repository"
    if maven_repo.exists():
        mv_size, mv_mtime = get_dir_size_and_mtime(maven_repo, max_depth=3)
        if mv_size > 15 * 1024 * 1024:
            mv_date, mv_days, mv_status = calculate_age_and_status(mv_mtime)
            maven_id = "cache:jvm:maven"
            del_cmd = f"rmdir /s /q \"{maven_repo}\"" if is_win else f"rm -rf '{maven_repo}'"
            nodes.append(Node(
                id=maven_id,
                name="Maven Local Repository (.m2)",
                category="Desktop & System",
                type="build-cache",
                path=str(maven_repo),
                size_bytes=mv_size,
                size_human=format_size(mv_size),
                last_used=mv_date,
                days_inactive=mv_days,
                status=mv_status,
                uninstall_cmd=del_cmd,
                notes="Cached Maven Central POMs, source JARs, and plugin dependencies",
                val=size_to_radius(mv_size)
            ))
            links.append(Link(
                source="runtime:os",
                target=maven_id,
                relationship="Artifact Repository",
                description="Maven caches resolved dependency archives locally"
            ))

    # --- 4. PROJECT-SPECIFIC BUILD ARTIFACTS (Rust target/, Next.js .next, Turbo) ---
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

    scanned_project_dirs: Set[str] = set()

    for sdir in search_dirs:
        if not sdir.exists():
            continue

        candidate_dirs = [sdir] if sdir != home else []
        if sdir.is_dir():
            try:
                for entry in sdir.iterdir():
                    if entry.is_dir() and not entry.name.startswith("."):
                        candidate_dirs.append(entry)
            except (PermissionError, FileNotFoundError):
                pass

        for p_dir in candidate_dirs:
            resolved_p = str(p_dir.resolve())
            if resolved_p in scanned_project_dirs:
                continue
            scanned_project_dirs.add(resolved_p)

            proj_id = f"project:{p_dir.name}"

            # 4A. Rust Cargo target/ directory
            cargo_toml = p_dir / "Cargo.toml"
            target_dir = p_dir / "target"
            if cargo_toml.exists() and target_dir.exists() and target_dir.is_dir():
                t_size, t_mtime = get_dir_size_and_mtime(target_dir, max_depth=3)
                if t_size > 1024 * 1024:  # > 1 MB
                    t_date, t_days, t_status = calculate_age_and_status(t_mtime)
                    target_id = f"build:rust:{p_dir.name}:target"
                    clean_cmd = f"cargo clean --manifest-path \"{cargo_toml}\""
                    nodes.append(Node(
                        id=target_id,
                        name=f"{p_dir.name} (target/ build)",
                        category="Desktop & System",
                        type="build-artifact",
                        path=str(target_dir),
                        size_bytes=t_size,
                        size_human=format_size(t_size),
                        last_used=t_date,
                        days_inactive=t_days,
                        status=t_status,
                        uninstall_cmd=clean_cmd,
                        notes=f"Compiled Rust binaries, intermediate crates, and debug symbols for {p_dir.name}",
                        val=size_to_radius(t_size)
                    ))
                    # Link project to target
                    links.append(Link(
                        source=proj_id,
                        target=target_id,
                        relationship="Build Output",
                        description=f"{p_dir.name} generates compiled crate binaries into target/ ({format_size(t_size)})"
                    ))
                    if rust_installed:
                        links.append(Link(
                            source=rust_runtime_id,
                            target=target_id,
                            relationship="Compiler Backend",
                            description="Cargo and rustc emit compiled artifacts and link dependencies"
                        ))

            # 4B. Next.js .next build cache
            next_dir = p_dir / ".next"
            if next_dir.exists() and next_dir.is_dir():
                nx_size, nx_mtime = get_dir_size_and_mtime(next_dir, max_depth=3)
                if nx_size > 1024 * 1024:
                    nx_date, nx_days, nx_status = calculate_age_and_status(nx_mtime)
                    next_id = f"build:next:{p_dir.name}:cache"
                    del_cmd = f"rmdir /s /q \"{next_dir}\"" if is_win else f"rm -rf '{next_dir}'"
                    nodes.append(Node(
                        id=next_id,
                        name=f"{p_dir.name} (.next cache)",
                        category="Fullstack Web",
                        type="build-artifact",
                        path=str(next_dir),
                        size_bytes=nx_size,
                        size_human=format_size(nx_size),
                        last_used=nx_date,
                        days_inactive=nx_days,
                        status=nx_status,
                        uninstall_cmd=del_cmd,
                        notes=f"Next.js build cache, serverless bundle chunks, and SSR static files for {p_dir.name}",
                        val=size_to_radius(nx_size)
                    ))
                    links.append(Link(
                        source=proj_id,
                        target=next_id,
                        relationship="SSR Build Cache",
                        description=f"{p_dir.name} builds Next.js server components and webpack/turbopack caches"
                    ))

            # 4C. Turborepo .turbo cache
            turbo_dir = p_dir / ".turbo"
            if turbo_dir.exists() and turbo_dir.is_dir():
                tb_size, tb_mtime = get_dir_size_and_mtime(turbo_dir, max_depth=3)
                if tb_size > 1024 * 1024:
                    tb_date, tb_days, tb_status = calculate_age_and_status(tb_mtime)
                    turbo_id = f"build:turbo:{p_dir.name}:cache"
                    del_cmd = f"rmdir /s /q \"{turbo_dir}\"" if is_win else f"rm -rf '{turbo_dir}'"
                    nodes.append(Node(
                        id=turbo_id,
                        name=f"{p_dir.name} (.turbo cache)",
                        category="Fullstack Web",
                        type="build-artifact",
                        path=str(turbo_dir),
                        size_bytes=tb_size,
                        size_human=format_size(tb_size),
                        last_used=tb_date,
                        days_inactive=tb_days,
                        status=tb_status,
                        uninstall_cmd=del_cmd,
                        notes=f"Turborepo task execution cache and artifact logs for {p_dir.name}",
                        val=size_to_radius(tb_size)
                    ))
                    links.append(Link(
                        source=proj_id,
                        target=turbo_id,
                        relationship="Monorepo Task Cache",
                        description=f"{p_dir.name} caches incremental monorepo pipeline builds"
                    ))

    return nodes, links
