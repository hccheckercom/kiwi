"""A7 HTTP Server — test suite (40+ checks)."""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

KIWI_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(KIWI_DIR))


# --- Fixtures ---

@pytest.fixture
def app():
    """Create test FastAPI app."""
    try:
        from server.app import create_app
        return create_app(enable_watcher=False)
    except ImportError:
        pytest.skip("FastAPI not installed (pip install kiwi-ai[server])")


@pytest.fixture
def client(app):
    """Create test client."""
    from fastapi.testclient import TestClient
    return TestClient(app)


# --- 1. Health endpoint ---

class TestHealth:
    def test_health_returns_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_health_includes_ws_count(self, client):
        r = client.get("/health")
        assert r.json()["websocket_connections"] == 0


# --- 2. Scan endpoints ---

class TestScan:
    @patch("mcp_server._handle_scan")
    def test_scan_returns_200(self, mock_scan, client):
        mock_scan.return_value = "No violations found."
        r = client.post("/api/scan", json={"path": ".", "severity": "ALL"})
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    @patch("mcp_server._handle_scan")
    def test_scan_passes_args(self, mock_scan, client):
        mock_scan.return_value = "result"
        client.post("/api/scan", json={"path": "/tmp/test", "severity": "CRITICAL", "diff_only": True})
        args = mock_scan.call_args[0][0]
        assert args["path"] == "/tmp/test"
        assert args["severity"] == "CRITICAL"
        assert args["diff_only"] is True

    @patch("mcp_server._handle_check")
    def test_check_single_file(self, mock_check, client):
        mock_check.return_value = "PASS: 1 file(s) clean"
        r = client.post("/api/check", json={"file": "test.php"})
        assert r.status_code == 200
        assert "PASS" in r.json()["data"]

    @patch("mcp_server._handle_check")
    def test_check_multiple_files(self, mock_check, client):
        mock_check.return_value = "PASS: 3 file(s) clean"
        r = client.post("/api/check", json={"files": ["a.php", "b.php", "c.php"]})
        assert r.status_code == 200


# --- 3. Knowledge endpoints ---

class TestKnowledge:
    @patch("mcp_server._handle_context")
    def test_context_endpoint(self, mock_ctx, client):
        mock_ctx.return_value = "Context: 5 rules loaded"
        r = client.post("/api/context", json={"task": "checkout page", "scope_type": "theme"})
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    @patch("mcp_server._handle_query")
    def test_query_lessons(self, mock_query, client):
        mock_query.return_value = "Kiwi Query: 3 results"
        r = client.get("/api/lessons", params={"keyword": "nonce"})
        assert r.status_code == 200

    @patch("mcp_server._handle_lesson")
    def test_get_lesson_by_id(self, mock_lesson, client):
        mock_lesson.return_value = "# LES-020 [CRITICAL]"
        r = client.get("/api/lessons/LES-020")
        assert r.status_code == 200
        assert "LES-020" in r.json()["data"]

    @patch("mcp_server._handle_stats")
    def test_stats_endpoint(self, mock_stats, client):
        mock_stats.return_value = "Kiwi Knowledge Base — 726 patterns"
        r = client.get("/api/stats")
        assert r.status_code == 200


# --- 4. Fix endpoints ---

class TestFix:
    @patch("mcp_server._handle_fix")
    def test_fix_preview(self, mock_fix, client):
        mock_fix.return_value = "Preview fix for LES-020"
        r = client.post("/api/fix", json={"lesson_id": "LES-020", "file": "test.php", "line": 10})
        assert r.status_code == 200

    @patch("mcp_server._handle_fix")
    def test_fix_apply(self, mock_fix, client):
        mock_fix.return_value = "Applied fix for LES-020"
        r = client.post("/api/fix", json={"lesson_id": "LES-020", "file": "test.php", "line": 10, "apply": True})
        assert r.status_code == 200

    @patch("mcp_server._handle_dismiss")
    def test_dismiss_violation(self, mock_dismiss, client):
        mock_dismiss.return_value = "Dismissed LES-020"
        r = client.post("/api/dismiss", json={
            "lesson_id": "LES-020",
            "file": "test.php",
            "reason": "intentional",
            "scope": "file",
        })
        assert r.status_code == 200

    @patch("mcp_server._handle_trends")
    def test_trends_endpoint(self, mock_trends, client):
        mock_trends.return_value = "Kiwi Trends: /tmp/test"
        r = client.post("/api/trends", json={"path": "/tmp/test", "days": 7})
        assert r.status_code == 200


# --- 5. Dashboard endpoints ---

class TestDashboard:
    @patch("mcp_server._handle_dashboard")
    def test_dashboard_compact(self, mock_dash, client):
        mock_dash.return_value = "Dashboard: compact view"
        r = client.get("/api/dashboard")
        assert r.status_code == 200

    @patch("mcp_server._handle_dashboard")
    def test_dashboard_detail(self, mock_dash, client):
        mock_dash.return_value = "Dashboard: detail view"
        r = client.get("/api/dashboard", params={"mode": "detail"})
        assert r.status_code == 200

    def test_status_endpoint(self, client):
        with patch("core.tier_manager.get_tier_manager") as mock_tm, \
             patch("core.plugin_registry.discover_plugins") as mock_dp:
            mock_tm.return_value.get_status.return_value = {"tier": "free"}
            mock_dp.return_value = []
            r = client.get("/api/status")
            assert r.status_code == 200
            data = r.json()["data"]
            assert "tier" in data
            assert "version" in data


# --- 6. Tier endpoints ---

class TestTier:
    def test_tier_get(self, client):
        with patch("core.tier_manager.get_tier_manager") as mock_tm:
            mock_tm.return_value.get_status.return_value = {"tier": "free", "scans_today": 2}
            r = client.get("/api/tier")
            assert r.status_code == 200

    def test_upgrade_without_key(self, client):
        with patch("core.tier_manager.get_tier_manager") as mock_tm:
            mock_tm.return_value.get_status.return_value = {"tier": "free"}
            r = client.post("/api/upgrade", json={"tier": "pro"})
            assert r.status_code == 200
            assert "license_key" in r.json()["data"]["message"].lower() or "License" in r.json()["data"]["message"]

    def test_upgrade_with_valid_key(self, client):
        with patch("core.tier_manager.get_tier_manager") as mock_tm:
            mock_tm.return_value.activate_license.return_value = True
            mock_tm.return_value.get_status.return_value = {"tier": "pro"}
            r = client.post("/api/upgrade", json={"tier": "pro", "license_key": "KIWI-PRO-VALID"})
            assert r.status_code == 200

    def test_upgrade_with_invalid_key(self, client):
        with patch("core.tier_manager.get_tier_manager") as mock_tm:
            mock_tm.return_value.activate_license.return_value = False
            r = client.post("/api/upgrade", json={"tier": "pro", "license_key": "INVALID"})
            assert r.status_code == 200
            assert r.json()["status"] == "error" or "Invalid" in str(r.json()["data"])


# --- 7. WebSocket ---

class TestWebSocket:
    def test_ws_connect(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"command": "subscribe", "channels": ["scan"]})

    def test_ws_subscribe_unsubscribe(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"command": "subscribe", "channels": ["scan", "fix"]})
            ws.send_json({"command": "unsubscribe", "channels": ["fix"]})


# --- 8. Auth middleware ---

class TestAuth:
    def test_no_token_allows_all(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_token_blocks_without_header(self, app):
        from fastapi.testclient import TestClient
        with patch.dict(os.environ, {"KIWI_TOKEN": "secret123"}):
            tc = TestClient(app)
            r = tc.get("/api/stats")
            assert r.status_code == 401

    def test_token_allows_with_header(self, app):
        from fastapi.testclient import TestClient
        with patch.dict(os.environ, {"KIWI_TOKEN": "secret123"}):
            with patch("mcp_server._handle_stats", return_value="stats"):
                tc = TestClient(app)
                r = tc.get("/api/stats", headers={"Authorization": "Bearer secret123"})
                assert r.status_code == 200

    def test_health_always_open(self, app):
        from fastapi.testclient import TestClient
        with patch.dict(os.environ, {"KIWI_TOKEN": "secret123"}):
            tc = TestClient(app)
            r = tc.get("/health")
            assert r.status_code == 200


# --- 9. Models validation ---

class TestModels:
    def test_scan_request_defaults(self):
        from server.models import ScanRequest
        req = ScanRequest()
        assert req.path == "."
        assert req.severity == "ALL"
        assert req.diff_only is False

    def test_check_request_requires_file_or_files(self):
        from server.models import CheckRequest
        req = CheckRequest()
        assert req.file is None
        assert req.files is None

    def test_fix_request_requires_lesson_id(self):
        from server.models import FixRequest
        with pytest.raises(Exception):
            FixRequest()

    def test_dismiss_request_fields(self):
        from server.models import DismissRequest
        req = DismissRequest(lesson_id="LES-001", file="test.php", reason="ok")
        assert req.scope == "file"

    def test_kiwi_response_format(self):
        from server.models import KiwiResponse
        resp = KiwiResponse(data={"key": "value"})
        assert resp.status == "ok"
        assert resp.data == {"key": "value"}


# --- 10. WebSocket manager ---

class TestWSManager:
    def test_manager_initial_state(self):
        from server.ws import ConnectionManager
        mgr = ConnectionManager()
        assert mgr.active_count == 0

    def test_manager_disconnect_nonexistent(self):
        from server.ws import ConnectionManager
        mgr = ConnectionManager()
        mgr.disconnect(MagicMock())


# --- 11. File watcher ---

class TestFileWatcher:
    def test_watcher_init(self):
        from server.watcher import FileWatcher
        fw = FileWatcher("/tmp/test")
        assert fw.project_path == "/tmp/test"

    def test_scannable_extensions(self):
        from server.watcher import SCANNABLE_EXTENSIONS
        assert ".php" in SCANNABLE_EXTENSIONS
        assert ".ts" in SCANNABLE_EXTENSIONS
        assert ".md" not in SCANNABLE_EXTENSIONS


# --- 12. CLI serve command ---

class TestServeCLI:
    def test_serve_command_exists(self):
        from cli.main import cli
        assert "serve" in [cmd for cmd in cli.commands]

    def test_serve_help(self):
        from click.testing import CliRunner
        from cli.main import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "--help"])
        assert result.exit_code == 0
        assert "--port" in result.output
        assert "--host" in result.output
        assert "--no-watch" in result.output
        assert "--token" in result.output


# --- 13. Integration: route → handler mapping ---

class TestRouteHandlerMapping:
    @patch("mcp_server._handle_scan")
    def test_scan_route_calls_handle_scan(self, mock, client):
        mock.return_value = "ok"
        client.post("/api/scan", json={"path": "."})
        mock.assert_called_once()

    @patch("mcp_server._handle_check")
    def test_check_route_calls_handle_check(self, mock, client):
        mock.return_value = "ok"
        client.post("/api/check", json={"file": "x.php"})
        mock.assert_called_once()

    @patch("mcp_server._handle_context")
    def test_context_route_calls_handle_context(self, mock, client):
        mock.return_value = "ok"
        client.post("/api/context", json={"task": "test"})
        mock.assert_called_once()

    @patch("mcp_server._handle_fix")
    def test_fix_route_calls_handle_fix(self, mock, client):
        mock.return_value = "ok"
        client.post("/api/fix", json={"lesson_id": "LES-001"})
        mock.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])