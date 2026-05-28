"""File watcher — auto-check on save, broadcast via WebSocket."""

import asyncio
import os
import time
from pathlib import Path
from typing import Optional

SCANNABLE_EXTENSIONS = {".php", ".js", ".ts", ".tsx", ".jsx", ".css", ".py", ".go", ".rs"}
DEBOUNCE_MS = 500


class FileWatcher:
    def __init__(self, project_path: str, loop: Optional[asyncio.AbstractEventLoop] = None):
        self.project_path = project_path
        self._loop = loop
        self._observer = None
        self._last_event: dict[str, float] = {}

    def start(self):
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
        except ImportError:
            return

        watcher = self

        class Handler(FileSystemEventHandler):
            def on_modified(self, event):
                if event.is_directory:
                    return
                ext = Path(event.src_path).suffix.lower()
                if ext not in SCANNABLE_EXTENSIONS:
                    return

                now = time.time()
                last = watcher._last_event.get(event.src_path, 0)
                if (now - last) * 1000 < DEBOUNCE_MS:
                    return
                watcher._last_event[event.src_path] = now

                if watcher._loop:
                    asyncio.run_coroutine_threadsafe(
                        watcher._on_file_changed(event.src_path),
                        watcher._loop,
                    )

        self._observer = Observer()
        self._observer.schedule(Handler(), self.project_path, recursive=True)
        self._observer.daemon = True
        self._observer.start()

    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2)

    async def _on_file_changed(self, file_path: str):
        from .ws import manager

        await manager.broadcast("file.changed", {"file": file_path, "action": "modified"})

        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from agent.guardrail import check_file, format_result

            result = check_file(file_path=file_path, severity="CRITICAL")
            formatted = format_result(result)

            await manager.broadcast("check.result", {
                "file": file_path,
                "violations": result.get("violations", []),
                "critical": result.get("critical", 0),
                "status": "BLOCK" if result.get("critical", 0) > 0 else "PASS",
            })
        except Exception:
            pass