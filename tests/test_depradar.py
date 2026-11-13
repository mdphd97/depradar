"""Comprehensive test suite for DepRadar."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import unittest
from depradar.models import Node, Link, GraphData
from depradar.diff import compute_diff
from depradar.audit import parse_semver, is_version_vulnerable, audit_packages
from depradar.scanners.base import format_size, calculate_age_and_status, size_to_radius
from depradar.scanners.code_scanner import is_valid_pkg_name

class TestDepRadarCore(unittest.TestCase):

    def test_models_serialization(self):
        node = Node(
            id="test:node",
            name="Test Node",
            category="Desktop & System",
            type="runtime",
            path="/usr/bin/test",
            size_bytes=1024 * 1024,
            size_human="1.0 MB",
            last_used="2026-11-11",
            days_inactive=1,
            status="active"
        )
        link = Link(source="test:node", target="target:node", relationship="test_rel")
        graph = GraphData(nodes=[node], links=[link], metadata={"test": True})

        d = graph.to_dict()
        self.assertEqual(len(d["nodes"]), 1)
        self.assertEqual(len(d["links"]), 1)
        self.assertEqual(d["nodes"][0]["name"], "Test Node")
        self.assertEqual(d["links"][0]["relationship"], "test_rel")

    def test_base_utilities(self):
        self.assertEqual(format_size(500), "500 B")
        self.assertEqual(format_size(1024 * 500), "500.0 KB")
        self.assertEqual(format_size(1024 * 1024 * 500), "500.0 MB")
        self.assertEqual(format_size(1024 * 1024 * 1024 * 2), "2.00 GB")

        self.assertGreater(size_to_radius(1024 * 1024 * 1000), size_to_radius(1024))

        date_str, days, status = calculate_age_and_status(100000.0)
        self.assertEqual(status, "stale")

    def test_pkg_name_validation(self):
        self.assertTrue(is_valid_pkg_name("torch"))
        self.assertTrue(is_valid_pkg_name("@google/generative-ai"))
        self.assertTrue(is_valid_pkg_name("scikit-learn"))
        self.assertFalse(is_valid_pkg_name("not a package with spaces"))
        self.assertFalse(is_valid_pkg_name("sentence with \n newline"))
        self.assertFalse(is_valid_pkg_name("malicious * asterisk"))

    def test_diff_engine(self):
        old_graph = {
            "nodes": [
                {"id": "node:1", "name": "Node 1", "category": "Dev", "size_bytes": 1000, "size_human": "1 KB", "status": "active", "installed_packages": [{"name": "reqs", "version": "1.0.0"}]}
            ],
            "links": []
        }
        new_graph = {
            "nodes": [
                {"id": "node:1", "name": "Node 1", "category": "Dev", "size_bytes": 5000000, "size_human": "5 MB", "status": "active", "installed_packages": [{"name": "reqs", "version": "2.0.0"}, {"name": "numpy", "version": "1.24"}]},
                {"id": "node:2", "name": "Node 2", "category": "Dev", "size_bytes": 2000, "size_human": "2 KB", "status": "active"}
            ],
            "links": []
        }
        res = compute_diff(old_graph, new_graph)
        self.assertEqual(res["summary"]["added_count"], 1)
        self.assertEqual(res["summary"]["removed_count"], 0)
        self.assertEqual(res["summary"]["modified_count"], 1)
        self.assertEqual(len(res["modified"][0]["packages_added"]), 1)
        self.assertEqual(len(res["modified"][0]["packages_upgraded"]), 1)

    def test_security_audit(self):
        self.assertEqual(parse_semver("3.1.3"), [3, 1, 3])
        self.assertEqual(parse_semver("10.2"), [10, 2, 0])
        self.assertTrue(is_version_vulnerable("3.1.2", "3.1.3"))
        self.assertFalse(is_version_vulnerable("3.1.4", "3.1.3"))

        vulnerable_node = Node(
            id="test:venv",
            name="Vulnerable venv",
            category="Data Science & ML",
            type="python-venv",
            path="/tmp/v",
            size_bytes=100,
            size_human="100 B",
            last_used="Today",
            days_inactive=0,
            status="active",
            installed_packages=[{"name": "jinja2", "version": "3.1.2"}]
        )
        graph = GraphData(nodes=[vulnerable_node])
        findings = audit_packages(graph)
        self.assertEqual(findings["total_vulnerabilities_found"], 1)
        self.assertEqual(findings["findings"][0]["cve"], "CVE-2024-22195")

    def test_mcp_server(self):
        import io
        import json
        from unittest.mock import patch
        from depradar.mcp import run_mcp_server

        input_data = "\n".join([
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
            json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "depradar_get_system_overview", "arguments": {}}}),
            json.dumps({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "depradar_audit_vulnerabilities", "arguments": {"online": False}}}),
            json.dumps({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "depradar_list_stale_dependencies", "arguments": {}}}),
            ""
        ])
        output_buffer = io.StringIO()
        with patch("sys.stdin", io.StringIO(input_data)), patch("sys.stdout", output_buffer):
            run_mcp_server()

        lines = [line for line in output_buffer.getvalue().splitlines() if line.strip()]
        self.assertEqual(len(lines), 5)
        resp1 = json.loads(lines[0])
        self.assertEqual(resp1["id"], 1)
        self.assertIn("capabilities", resp1["result"])

        resp2 = json.loads(lines[1])
        tool_names = [t["name"] for t in resp2["result"]["tools"]]
        self.assertIn("depradar_get_system_overview", tool_names)
        self.assertIn("depradar_audit_vulnerabilities", tool_names)

if __name__ == "__main__":
    unittest.main()
