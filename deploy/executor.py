"""Deployment executor — SSH/rsync execution, template filling, health checks."""

import json
import os
import platform
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

from .wp_theme_activator import activate_theme_on_subsite, create_subsite

DEPLOY_DIR = Path(__file__).parent
CONFIG_PATH = DEPLOY_DIR / "config.json"
TEMPLATES_PATH = DEPLOY_DIR / "templates.json"
ERRORS_PATH = DEPLOY_DIR / "errors.json"

_config_cache = None
_templates_cache = None
_errors_cache = None
_templates_mtime = None


class DeployExecutor:
    """Executes deployment with pre-built templates and configs."""

    def __init__(self, project_path: str, deploy_type: str, target: str):
        self.project_path = os.path.abspath(project_path)
        self.deploy_type = deploy_type
        self.target = target
        self.config = load_config()
        self.templates = load_templates()
        self.errors = load_errors()

    def get_git_commit(self) -> str:
        """Get current git commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            import sys
            print(f"[kiwi] get_git_commit error: {e}", file=sys.stderr)
        return "unknown"

    def check_git_clean(self) -> bool:
        """Check if git working tree is clean (only tracked files in project path)."""
        try:
            # Get git root
            root_result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if root_result.returncode != 0:
                return False

            git_root = root_result.stdout.strip()

            # Check status from git root
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=git_root,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                return False

            # Filter: only check files within project_path
            rel_path = os.path.relpath(self.project_path, git_root).replace("\\", "/")
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                # Extract file path (skip status prefix)
                file_path = line[3:].strip()
                # Check if file is within project path
                if file_path.startswith(rel_path + "/") or file_path == rel_path:
                    return False

            return True
        except Exception as e:
            import sys
            print(f"[kiwi] check_git_clean error: {e}", file=sys.stderr)
            return False

    def run_kiwi_scan(self, severity: str = "CRITICAL") -> Dict:
        """Run Kiwi scan, return violations summary."""
        import sys
        kiwi_dir = DEPLOY_DIR.parent
        sys.path.insert(0, str(kiwi_dir))

        try:
            from scanner.cli import scan_theme
            report = scan_theme(
                self.project_path,
                severity_filter=severity,
                skip_empty_scope=True,
            )
            return {
                "critical": report.critical_count,
                "high": report.high_count,
                "suggest": report.suggest_count,
                "total": len(report.violations),
            }
        except Exception as e:
            return {"critical": 0, "high": 0, "suggest": 0, "total": 0, "error": str(e)}

    def build_plan(self) -> Dict:
        """Build deployment plan with commands."""
        steps = []
        params = self._get_params()

        template_key = self.deploy_type
        if template_key not in self.templates:
            return {"steps": [], "error": f"Unknown deploy type: {self.deploy_type}"}

        template = self.templates[template_key]

        if "backup" in template:
            steps.append({
                "name": "Backup current version",
                "command": self._fill_template(template["backup"], params),
            })

        if "deploy" in template:
            steps.append({
                "name": "Deploy files",
                "command": self._fill_template(template["deploy"], params),
            })

        if "build" in template:
            steps.append({
                "name": "Build on server",
                "command": self._fill_template(template["build"], params),
            })

        if "network_enable" in template:
            steps.append({
                "name": "Network-enable theme",
                "command": self._fill_template(template["network_enable"], params),
            })

        if "post_deploy" in template:
            steps.append({
                "name": "Post-deploy setup",
                "command": self._fill_template(template["post_deploy"], params),
            })

        if "restart" in template:
            steps.append({
                "name": "Restart service",
                "command": self._fill_template(template["restart"], params),
            })

        if "verify" in template:
            steps.append({
                "name": "Verify deployment",
                "command": self._fill_template(template["verify"], params),
            })

        return {"steps": steps, "params": params}

    def execute(self, plan: Dict) -> Dict:
        """Execute deployment plan."""
        import sys
        results = []
        multisite_needed = False
        backup_path = None

        for i, step in enumerate(plan["steps"], 1):
            # Check if this is a conditional step
            if step.get("conditional") and not multisite_needed:
                continue  # Skip conditional steps if condition not met

            print(f"[{i}/{len(plan['steps'])}] {step['name']}...", file=sys.stderr, flush=True)
            result = self._execute_command(step["command"])
            results.append({
                "step": step["name"],
                "success": result["returncode"] == 0,
                "output": result["stdout"],
                "error": result["stderr"],
            })

            # Capture backup path from backup step output
            if step["name"] == "Backup current version" and result["returncode"] == 0:
                backup_path = self._extract_backup_path(result["stdout"], plan["params"])

            # Check if multisite needs to be enabled
            if step.get("check_output") and step["check_output"] in result["stdout"]:
                multisite_needed = True

            if result["returncode"] != 0:
                print(f"[{i}/{len(plan['steps'])}] FAILED: {step['name']}", file=sys.stderr, flush=True)
                print(f"Error: {result['stderr'][:200]}", file=sys.stderr, flush=True)
                error_match = match_error(result["stderr"], self.errors, plan["params"])
                return {
                    "success": False,
                    "error": result["stderr"],
                    "error_pattern": error_match["id"] if error_match else None,
                    "fix_suggestion": error_match["fix"] if error_match else None,
                    "results": results,
                    "backup_path": backup_path,
                }

            print(f"[{i}/{len(plan['steps'])}] OK: {step['name']}", file=sys.stderr, flush=True)

        health_status = self._check_health()
        if not health_status["healthy"]:
            return {
                "success": False,
                "error": "Health checks failed",
                "health_status": health_status,
                "results": results,
                "backup_path": backup_path,
            }

        return {
            "success": True,
            "health_status": health_status,
            "results": results,
            "backup_path": backup_path,
        }

    def rollback(self, backup_path: str = None) -> Dict:
        """Rollback to previous deployment."""
        import sys

        params = self._get_params()

        # Get rollback template for this deploy type
        rollback_template = self.templates.get("rollback", {}).get(self.deploy_type)
        if not rollback_template:
            return {"status": "failed", "error": f"No rollback template for {self.deploy_type}"}

        # If backup_path provided, use it; otherwise get latest backup
        if backup_path:
            params["backup_path"] = backup_path
        else:
            latest_backup = self._get_latest_backup()
            if not latest_backup:
                return {"status": "failed", "error": "No backup found to rollback to"}
            params["backup_path"] = latest_backup

        print(f"[rollback] Rolling back to {params['backup_path']}...", file=sys.stderr)
        command = self._fill_template(rollback_template, params)
        result = self._execute_command(command)

        if result["returncode"] == 0:
            print(f"[rollback] Rollback successful", file=sys.stderr)
        else:
            print(f"[rollback] Rollback failed: {result['stderr'][:200]}", file=sys.stderr)

        return {
            "status": "success" if result["returncode"] == 0 else "failed",
            "output": result["stdout"],
            "error": result["stderr"],
            "backup_path": params["backup_path"],
        }

    def _get_params(self) -> Dict:
        """Get deployment parameters from config."""
        params = {"local_path": self.project_path}

        if self.deploy_type == "wp_theme":
            vps = self.config["vps"]["wp"]
            key_path = vps.get("key_path", "~/.ssh/id_rsa")
            # Expand Windows path
            if key_path.startswith("~"):
                import os
                key_path = os.path.expanduser(key_path)
            params.update({
                "host": vps["host"],
                "port": vps.get("port", 22),
                "user": vps["user"],
                "key_path": key_path,
                "wp_path": vps["wp_path"],
                "theme_name": Path(self.project_path).name,
            })
        elif self.deploy_type == "wp_plugin":
            vps = self.config["vps"]["wp"]
            key_path = vps.get("key_path", "~/.ssh/id_rsa")
            # Expand Windows path
            if key_path.startswith("~"):
                import os
                key_path = os.path.expanduser(key_path)
            params.update({
                "host": vps["host"],
                "port": vps.get("port", 22),
                "user": vps["user"],
                "key_path": key_path,
                "wp_path": vps["wp_path"],
            })
        elif self.deploy_type == "nextjs":
            vps = self.config["vps"]["nextjs"]
            app_type = "demo" if "demo" in self.project_path.lower() else "main"
            pm2_config = vps["pm2"][app_type]
            params.update({
                "host": vps["host"],
                "port": vps["port"],
                "user": vps["user"],
                "remote_path": vps["paths"][app_type],
                "backup_path": vps["paths"]["backup"],
                "pm2_name": pm2_config["name"],
                "pm2_port": pm2_config["port"],
                "health_url": self.config["health_checks"]["nextjs"][0 if app_type == "main" else 1],
            })
        elif self.deploy_type == "demo_html":
            vps = self.config["vps"]["wp"]
            # Use explicit remote_path if provided, otherwise auto-detect from project structure
            if hasattr(self, 'remote_path') and self.remote_path:
                remote_path = self.remote_path
            else:
                # Auto-detect: themes/{theme}/demos/{demo} → /var/www/.../themes/{theme}/demos/{demo}
                theme_name = Path(self.project_path).parent.parent.name
                demo_name = Path(self.project_path).name
                remote_path = f"{vps['wp_path']}/wp-content/themes/{theme_name}/demos/{demo_name}"

            params.update({
                "host": vps["host"],
                "port": vps.get("port", 22),
                "user": vps["user"],
                "remote_path": remote_path,
            })

        return params

    def _fill_template(self, template: str, params: Dict) -> str:
        """Fill template placeholders with params."""
        result = template
        for key, value in params.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result

    def _execute_command(self, command: str) -> Dict:
        """Execute shell command, return result."""
        try:
            # On Windows, use PowerShell wrapper for WSL commands
            if platform.system() == "Windows" and (command.startswith("rsync ") or command.startswith("ssh ")):
                wrapper_path = DEPLOY_DIR / "wsl_wrapper.ps1"
                # Use full path to PowerShell
                ps_path = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
                result = subprocess.run(
                    [ps_path, "-ExecutionPolicy", "Bypass", "-File", str(wrapper_path), command],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
            else:
                # Non-WSL commands
                result = subprocess.run(
                    shlex.split(command),
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": "Command timeout after 300s",
            }
        except Exception as e:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
            }

    def _convert_to_wsl_paths(self, command: str) -> str:
        """Convert Windows paths in command to WSL paths."""
        import re

        # Convert C:/path/to/file to /mnt/c/path/to/file
        def convert_path(match):
            path = match.group(0)
            # C:/Users/... -> /mnt/c/Users/...
            if path.startswith("C:/") or path.startswith("C:\\"):
                wsl_path = "/mnt/c/" + path[3:].replace("\\", "/")
                return wsl_path
            elif path.startswith("D:/") or path.startswith("D:\\"):
                wsl_path = "/mnt/d/" + path[3:].replace("\\", "/")
                return wsl_path
            return path

        # Match Windows paths (C:/ or D:/ followed by path)
        command = re.sub(r'[CD]:[/\\][^\s\'\"]+', convert_path, command)
        return command

    def _check_health(self) -> Dict:
        """Check health endpoints."""
        if self.deploy_type == "wp_theme" or self.deploy_type == "wp_plugin":
            urls = self.config["health_checks"]["wp"]
        elif self.deploy_type == "nextjs":
            urls = self.config["health_checks"]["nextjs"]
        else:
            return {"healthy": True, "checks": []}

        checks = []
        for url in urls:
            try:
                result = subprocess.run(
                    ["curl", "-f", "-s", "-o", "/dev/null", "-w", "%{http_code}", url],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                status_code = result.stdout.strip()
                checks.append({
                    "url": url,
                    "status": int(status_code) if status_code.isdigit() else 0,
                    "healthy": status_code.startswith("2"),
                })
            except Exception as e:
                checks.append({
                    "url": url,
                    "status": 0,
                    "healthy": False,
                    "error": str(e),
                })

        return {
            "healthy": all(c["healthy"] for c in checks),
            "checks": checks,
        }

    def _extract_backup_path(self, output: str, params: Dict) -> str:
        """Extract backup path from backup command output."""
        # Backup path format: {wp_path}/wp-content/themes/.backup-{theme_name}-{timestamp}
        # or: {wp_path}/wp-content/mu-plugins/.backup-wezone-plugins-{timestamp}
        if self.deploy_type == "wp_theme":
            theme_name = params.get("theme_name", "")
            base_path = f"{params['wp_path']}/wp-content/themes/.backup-{theme_name}-"
        elif self.deploy_type == "wp_plugin":
            base_path = f"{params['wp_path']}/wp-content/mu-plugins/.backup-wezone-plugins-"
        else:
            return None

        # Extract timestamp from command (backup command uses $(date +%s))
        import time
        timestamp = int(time.time())
        return f"{base_path}{timestamp}"

    def _get_latest_backup(self) -> str:
        """Get path to most recent backup directory."""
        params = self._get_params()

        if self.deploy_type == "wp_theme":
            theme_name = params.get("theme_name", "")
            backup_pattern = f".backup-{theme_name}-*"
            backup_dir = f"{params['wp_path']}/wp-content/themes"
        elif self.deploy_type == "wp_plugin":
            backup_pattern = ".backup-wezone-plugins-*"
            backup_dir = f"{params['wp_path']}/wp-content/mu-plugins"
        else:
            return None

        # List backup directories via SSH, sort by timestamp (newest first)
        list_cmd = f"ssh -o StrictHostKeyChecking=no -p {params['port']} -i {params['key_path']} {params['user']}@{params['host']} 'ls -dt {backup_dir}/{backup_pattern} 2>/dev/null | head -1'"
        result = self._execute_command(list_cmd)

        if result["returncode"] == 0 and result["stdout"].strip():
            return result["stdout"].strip()

        return None


def load_config() -> Dict:
    """Load deployment config, cached."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    with open(CONFIG_PATH, encoding="utf-8") as f:
        _config_cache = json.load(f)
    return _config_cache


def load_templates() -> Dict:
    """Load command templates, cached with mtime check."""
    global _templates_cache, _templates_mtime
    current_mtime = os.path.getmtime(TEMPLATES_PATH)
    if _templates_cache is not None and _templates_mtime == current_mtime:
        return _templates_cache
    with open(TEMPLATES_PATH, encoding="utf-8") as f:
        _templates_cache = json.load(f)
        _templates_mtime = current_mtime
    return _templates_cache


def load_errors() -> Dict:
    """Load error patterns, cached."""
    global _errors_cache
    if _errors_cache is not None:
        return _errors_cache
    with open(ERRORS_PATH, encoding="utf-8") as f:
        _errors_cache = json.load(f)
    return _errors_cache


def match_error(output: str, errors: Dict, params: Dict) -> Optional[Dict]:
    """Match output against error patterns, return fix suggestion."""
    for pattern in errors["patterns"]:
        if re.search(pattern["regex"], output, re.IGNORECASE):
            fix = pattern["fix"]
            for key, value in params.items():
                fix = fix.replace(f"{{{key}}}", str(value))
            return {
                "id": pattern["id"],
                "severity": pattern["severity"],
                "root_cause": pattern["root_cause"],
                "fix": fix,
            }
    return None