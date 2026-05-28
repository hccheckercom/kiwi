"""Kiwi LSP Server — main server using pygls."""

import logging
import sys
from pathlib import Path
from typing import Optional

from lsprotocol.types import (
    TEXT_DOCUMENT_CODE_ACTION,
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_DID_SAVE,
    TEXT_DOCUMENT_HOVER,
    CodeActionParams,
    DiagnosticSeverity,
    DidChangeTextDocumentParams,
    DidOpenTextDocumentParams,
    DidSaveTextDocumentParams,
    HoverParams,
    InitializeParams,
    InitializeResult,
    Position,
    ServerCapabilities,
    TextDocumentSyncKind,
    CodeActionOptions,
)
from pygls.lsp.server import LanguageServer

from .bridge import KiwiBridge
from .config import LspConfig
from .capabilities.diagnostics import violations_to_diagnostics
from .capabilities.code_actions import create_code_actions
from .capabilities.hover import create_hover

logger = logging.getLogger("kiwi-lsp")


class KiwiLanguageServer(LanguageServer):
    def __init__(self):
        super().__init__("kiwi-lsp", "1.0.0")
        self.config = LspConfig()
        self.bridge = KiwiBridge(self.config)
        self._diagnostics_cache: dict = {}


def create_server() -> KiwiLanguageServer:
    server = KiwiLanguageServer()

    @server.feature("initialize")
    def on_initialize(params: InitializeParams) -> InitializeResult:
        if params.initialization_options:
            opts = params.initialization_options
            if "severity" in opts:
                server.config.severity_filter = opts["severity"]
            if "platform" in opts:
                server.config.platform = opts["platform"]
            if "scanOnOpen" in opts:
                server.config.scan_on_open = opts["scanOnOpen"]
            if "scanOnSave" in opts:
                server.config.scan_on_save = opts["scanOnSave"]
            if "scanOnChange" in opts:
                server.config.scan_on_change = opts["scanOnChange"]
            if "lessonsDir" in opts:
                server.config.lessons_dir = opts["lessonsDir"]
            server.bridge = KiwiBridge(server.config)

        return InitializeResult(
            capabilities=ServerCapabilities(
                text_document_sync=TextDocumentSyncKind.Full,
                code_action_provider=CodeActionOptions(
                    resolve_provider=False
                ),
                hover_provider=True,
            )
        )

    @server.feature(TEXT_DOCUMENT_DID_OPEN)
    def on_did_open(params: DidOpenTextDocumentParams):
        if not server.config.scan_on_open:
            return
        uri = params.text_document.uri
        file_path = _uri_to_path(uri)
        content = params.text_document.text
        _publish_diagnostics(server, uri, file_path, content)

    @server.feature(TEXT_DOCUMENT_DID_SAVE)
    def on_did_save(params: DidSaveTextDocumentParams):
        if not server.config.scan_on_save:
            return
        uri = params.text_document.uri
        file_path = _uri_to_path(uri)
        _publish_diagnostics(server, uri, file_path)

    @server.feature(TEXT_DOCUMENT_DID_CHANGE)
    def on_did_change(params: DidChangeTextDocumentParams):
        if not server.config.scan_on_change:
            return
        uri = params.text_document.uri
        file_path = _uri_to_path(uri)
        content = params.content_changes[-1].text if params.content_changes else None
        if content:
            _publish_diagnostics(server, uri, file_path, content)

    @server.feature(TEXT_DOCUMENT_CODE_ACTION)
    def on_code_action(params: CodeActionParams):
        diagnostics = params.context.diagnostics
        kiwi_diags = [d for d in diagnostics if d.source == "kiwi"]
        if not kiwi_diags:
            return []
        return create_code_actions(params.text_document.uri, kiwi_diags, server.bridge)

    @server.feature(TEXT_DOCUMENT_HOVER)
    def on_hover(params: HoverParams) -> Optional[object]:
        uri = params.text_document.uri
        line = params.position.line
        cached = server._diagnostics_cache.get(uri, [])
        for diag in cached:
            if diag.range.start.line <= line <= diag.range.end.line:
                if diag.data and "lesson_id" in diag.data:
                    info = server.bridge.get_lesson_info(diag.data["lesson_id"])
                    return create_hover(info)
        return None

    @server.feature("kiwi/scanWorkspace")
    def on_scan_workspace(params):
        """Scan all matching files in workspace."""
        import glob as globmod
        workspace_path = params.get("path", "") if isinstance(params, dict) else ""
        if not workspace_path:
            return {"total": 0, "violations": 0}

        extensions = ["*.php", "*.js", "*.ts", "*.css", "*.html"]
        total_violations = 0
        files_scanned = 0

        for ext in extensions:
            pattern = str(Path(workspace_path) / "**" / ext)
            for file_path in globmod.glob(pattern, recursive=True):
                excluded = any(
                    ex.replace("**/", "") in file_path.replace("\\", "/")
                    for ex in server.config.excluded_patterns
                )
                if excluded:
                    continue

                violations = server.bridge.scan_file(file_path)
                if violations:
                    uri = _path_to_uri(file_path)
                    diagnostics = violations_to_diagnostics(violations)
                    server._diagnostics_cache[uri] = diagnostics
                    server.publish_diagnostics(uri, diagnostics)
                    total_violations += len(violations)
                files_scanned += 1

        return {"total": files_scanned, "violations": total_violations}

    @server.feature("kiwi/scanUncommitted")
    def on_scan_uncommitted(params):
        """Scan only files with uncommitted changes."""
        import subprocess
        workspace_path = params.get("path", "") if isinstance(params, dict) else ""
        if not workspace_path:
            return {"total": 0, "violations": 0, "files": []}

        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            staged = subprocess.run(
                ["git", "diff", "--name-only", "--cached"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            untracked = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return {"total": 0, "violations": 0, "files": []}

        changed_files = set()
        for output in [result.stdout, staged.stdout, untracked.stdout]:
            for line in output.strip().split("\n"):
                if line.strip():
                    changed_files.add(line.strip())

        total_violations = 0
        scanned_files = []
        workspace = Path(workspace_path)

        for rel_path in changed_files:
            full_path = workspace / rel_path
            if not full_path.exists():
                continue
            ext = full_path.suffix.lower()
            if ext not in (".php", ".js", ".ts", ".css", ".html"):
                continue

            violations = server.bridge.scan_file(str(full_path))
            if violations:
                uri = _path_to_uri(str(full_path))
                diagnostics = violations_to_diagnostics(violations)
                server._diagnostics_cache[uri] = diagnostics
                server.publish_diagnostics(uri, diagnostics)
                total_violations += len(violations)
                scanned_files.append(rel_path)

        return {"total": len(changed_files), "violations": total_violations, "files": scanned_files}

    @server.feature("kiwi/stats")
    def on_stats(params):
        """Get scan statistics for dashboard."""
        cached = server._diagnostics_cache
        total_files = len(cached)
        total_violations = sum(len(diags) for diags in cached.values())

        by_severity = {"CRITICAL": 0, "HIGH": 0, "SUGGEST": 0}
        by_lesson: dict = {}

        for diags in cached.values():
            for d in diags:
                sev = "SUGGEST"
                if d.severity == DiagnosticSeverity.Error:
                    sev = "CRITICAL"
                elif d.severity == DiagnosticSeverity.Warning:
                    sev = "HIGH"
                by_severity[sev] = by_severity.get(sev, 0) + 1

                lid = d.data.get("lesson_id", "UNKNOWN") if d.data else "UNKNOWN"
                by_lesson[lid] = by_lesson.get(lid, 0) + 1

        top_lessons = sorted(by_lesson.items(), key=lambda x: x[1], reverse=True)[:10]

        patterns = server.bridge._ensure_patterns()
        total_patterns = len(patterns)

        return {
            "total_files": total_files,
            "total_violations": total_violations,
            "by_severity": by_severity,
            "top_lessons": [{"id": lid, "count": cnt} for lid, cnt in top_lessons],
            "total_patterns": total_patterns,
        }

    @server.feature("kiwi/lessonDetail")
    def on_lesson_detail(params):
        """Get full lesson content for webview display."""
        if not isinstance(params, dict):
            return None
        lesson_id = params.get("lesson_id", "")
        if not lesson_id:
            return None
        info = server.bridge.get_lesson_info(lesson_id)
        return info

    @server.feature("kiwi/dismiss")
    def on_dismiss(params):
        """Dismiss a violation as false positive."""
        if not isinstance(params, dict):
            return {"success": False, "error": "Invalid params"}

        lesson_id = params.get("lesson_id", "")
        file_path = params.get("file", "")
        reason = params.get("reason", "")
        scope = params.get("scope", "file")

        if not lesson_id or not file_path:
            return {"success": False, "error": "lesson_id and file required"}

        try:
            memory_dir = Path(__file__).parent.parent / "memory"
            memory_dir.mkdir(exist_ok=True)
            import json
            fp_file = memory_dir / "false_positives.json"
            fps = []
            if fp_file.exists():
                fps = json.loads(fp_file.read_text(encoding="utf-8"))

            fps.append({
                "lesson_id": lesson_id,
                "file": file_path if scope == "file" else "*",
                "reason": reason,
                "scope": scope,
            })
            fp_file.write_text(json.dumps(fps, indent=2), encoding="utf-8")

            if scope == "file":
                uri = _path_to_uri(file_path)
                cached = server._diagnostics_cache.get(uri, [])
                filtered = [d for d in cached if not (d.data and d.data.get("lesson_id") == lesson_id)]
                server._diagnostics_cache[uri] = filtered
                server.publish_diagnostics(uri, filtered)

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    return server


def _uri_to_path(uri: str) -> str:
    if uri.startswith("file:///"):
        from urllib.parse import unquote
        path = unquote(uri[7:])  # strip "file://" keeping leading /
        if sys.platform == "win32" and len(path) > 2 and path[0] == "/" and path[2] == ":":
            path = path[1:]  # strip leading / before drive letter
        return path
    return uri


def _path_to_uri(file_path: str) -> str:
    from urllib.parse import quote
    path = file_path.replace("\\", "/")
    if len(path) > 1 and path[1] == ":":
        path = "/" + path
    return "file://" + quote(path, safe="/:")


def _publish_diagnostics(
    server: KiwiLanguageServer,
    uri: str,
    file_path: str,
    content: Optional[str] = None,
):
    violations = server.bridge.scan_file(file_path, content)
    diagnostics = violations_to_diagnostics(violations)
    server._diagnostics_cache[uri] = diagnostics
    server.publish_diagnostics(uri, diagnostics)


def main(args=None):
    """Entry point for kiwi lsp --stdio."""
    server = create_server()
    if args and "--tcp" in args:
        port = 7892
        for i, a in enumerate(args):
            if a == "--port" and i + 1 < len(args):
                port = int(args[i + 1])
        server.start_tcp("127.0.0.1", port)
    else:
        server.start_io()
