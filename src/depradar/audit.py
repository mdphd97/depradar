"""Security and Vulnerability Audit Engine for DepRadar.
Scans discovered virtual environments and project manifests for known CVEs and security advisories.
Operates with local built-in advisory heuristics and optional online OSV (Open Source Vulnerabilities) batch queries.
"""

import json
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional
from .models import GraphData, Node

# Built-in offline critical advisory database for instant zero-network auditing
OFFLINE_KNOWN_ADVISORIES = {
    "jinja2": [
        {"max_version": "3.1.3", "cve": "CVE-2024-22195", "severity": "HIGH", "summary": "HTML attribute injection vulnerability in xmlattr filter"}
    ],
    "pillow": [
        {"max_version": "10.2.0", "cve": "CVE-2023-50447", "severity": "CRITICAL", "summary": "Arbitrary code execution via environment keys"}
    ],
    "urllib3": [
        {"max_version": "2.0.7", "cve": "CVE-2023-45803", "severity": "HIGH", "summary": "Cookie header leakage on cross-origin redirects"}
    ],
    "requests": [
        {"max_version": "2.31.0", "cve": "CVE-2023-32681", "severity": "MEDIUM", "summary": "Unintended Proxy-Authorization header leak"}
    ],
    "cryptography": [
        {"max_version": "41.0.6", "cve": "CVE-2023-49083", "severity": "HIGH", "summary": "NULL pointer dereference when loading PKCS#7 certificates"}
    ],
    "aiohttp": [
        {"max_version": "3.9.2", "cve": "CVE-2024-23829", "severity": "HIGH", "summary": "HTTP request smuggling via malformed chunked requests"}
    ],
    "tornado": [
        {"max_version": "6.3.3", "cve": "CVE-2023-28370", "severity": "MEDIUM", "summary": "Open redirect vulnerability via double slash"}
    ],
    "werkzeug": [
        {"max_version": "3.0.1", "cve": "CVE-2023-46136", "severity": "HIGH", "summary": "High resource consumption via multipart form parsing"}
    ]
}

def parse_semver(v_str: str) -> List[int]:
    parts = []
    for p in v_str.split("."):
        clean = "".join(c for c in p if c.isdigit())
        parts.append(int(clean) if clean else 0)
    while len(parts) < 3:
        parts.append(0)
    return parts[:3]

def is_version_vulnerable(current_version: str, max_vulnerable: str) -> bool:
    try:
        cur = parse_semver(current_version)
        v_max = parse_semver(max_vulnerable)
        return cur <= v_max
    except Exception:
        return False

def audit_packages(graph: GraphData, online: bool = False) -> Dict[str, Any]:
    """Audits all installed packages across all nodes for security advisories."""
    findings = []
    audited_packages = set()

    # Collect all packages from venvs
    packages_to_check = []
    for node in graph.nodes:
        if node.installed_packages:
            for p in node.installed_packages:
                p_name = p.get("name", "").lower()
                p_ver = p.get("version", "")
                if p_name and p_ver:
                    packages_to_check.append({
                        "node_id": node.id,
                        "node_name": node.name,
                        "node_path": node.path,
                        "name": p_name,
                        "version": p_ver
                    })
                    audited_packages.add((p_name, p_ver))

    # 1. Local Offline Advisory Check
    for item in packages_to_check:
        p_name = item["name"]
        p_ver = item["version"]
        if p_name in OFFLINE_KNOWN_ADVISORIES:
            for adv in OFFLINE_KNOWN_ADVISORIES[p_name]:
                if is_version_vulnerable(p_ver, adv["max_version"]):
                    findings.append({
                        "node_id": item["node_id"],
                        "node_name": item["node_name"],
                        "package": p_name,
                        "installed_version": p_ver,
                        "cve": adv["cve"],
                        "severity": adv["severity"],
                        "summary": adv["summary"],
                        "fixed_in": f"> {adv['max_version']}"
                    })

    # 2. Optional Online OSV Batch Query
    if online and packages_to_check:
        try:
            unique_pkgs = list({(p["name"], p["version"]) for p in packages_to_check})[:40]
            osv_queries = [
                {"package": {"name": name, "ecosystem": "PyPI"}, "version": ver}
                for name, ver in unique_pkgs
            ]
            req_data = json.dumps({"queries": osv_queries}).encode("utf-8")
            req = urllib.request.Request(
                "https://api.osv.dev/v1/querybatch",
                data=req_data,
                headers={"Content-Type": "application/json", "User-Agent": "DepRadar-Audit/0.1"}
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                results = data.get("results", [])
                for idx, res in enumerate(results):
                    vulns = res.get("vulns", [])
                    if vulns:
                        pkg_info = unique_pkgs[idx]
                        for v in vulns[:2]:
                            findings.append({
                                "node_id": "global",
                                "node_name": "Audited Environment",
                                "package": pkg_info[0],
                                "installed_version": pkg_info[1],
                                "cve": v.get("id", "Advisory"),
                                "severity": "HIGH",
                                "summary": v.get("summary", "Security vulnerability in package version"),
                                "fixed_in": "Latest patch release"
                            })
        except Exception:
            pass

    return {
        "total_packages_audited": len(audited_packages),
        "total_vulnerabilities_found": len(findings),
        "findings": findings
    }

def format_audit_cli(audit_res: Dict[str, Any]) -> str:
    """Formats security audit results for terminal display."""
    total = audit_res["total_packages_audited"]
    vulns = audit_res["total_vulnerabilities_found"]

    lines = [
        "══════════════════════════════════════════════════════════════",
        " 🛡️ DepRadar Security & Vulnerability Audit Report",
        "══════════════════════════════════════════════════════════════",
        f" Audited Packages: {total} | Known Vulnerabilities: {vulns}",
        ""
    ]

    if not audit_res["findings"]:
        lines.append("✅ All audited packages and virtual environments are free of known critical advisories.")
    else:
        for f in audit_res["findings"]:
            sev_badge = f"[{f['severity']}]"
            lines.append(f"  ⚠️  {sev_badge} {f['package']} v{f['installed_version']} in {f['node_name']}")
            lines.append(f"      Advisory: {f['cve']} -> {f['summary']}")
            lines.append(f"      Recommendation: Upgrade to {f['fixed_in']}")
            lines.append("")

    return "\n".join(lines)
