"""Deployment notifications — Slack webhook integration."""

import json
import os
from datetime import datetime
from typing import Dict, Optional
import urllib.request
import urllib.error


class NotificationConfig:
    """Configuration for deployment notifications."""

    def __init__(self):
        self.slack_webhook_url = os.environ.get("KIWI_SLACK_WEBHOOK_URL")
        self.enabled = bool(self.slack_webhook_url)
        self.mention_on_failure = os.environ.get("KIWI_SLACK_MENTION_ON_FAILURE", "")


def send_slack_notification(
    webhook_url: str,
    message: str,
    color: str = "good",
    fields: Optional[list] = None,
) -> bool:
    """Send notification to Slack webhook.

    Args:
        webhook_url: Slack webhook URL
        message: Main message text
        color: Attachment color (good, warning, danger)
        fields: List of field dicts with title/value/short

    Returns:
        True if sent successfully, False otherwise
    """
    if not webhook_url:
        return False

    payload = {
        "attachments": [
            {
                "color": color,
                "text": message,
                "fields": fields or [],
                "footer": "Kiwi Deploy",
                "ts": int(datetime.now().timestamp()),
            }
        ]
    }

    try:
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return False


def notify_deployment_start(
    config: NotificationConfig,
    project_name: str,
    deploy_type: str,
    target: str,
    commit: str,
) -> bool:
    """Notify deployment started."""
    if not config.enabled:
        return False

    message = f"🚀 Deployment started: *{project_name}*"
    fields = [
        {"title": "Type", "value": deploy_type, "short": True},
        {"title": "Target", "value": target, "short": True},
        {"title": "Commit", "value": commit[:7], "short": True},
    ]

    return send_slack_notification(
        config.slack_webhook_url,
        message,
        color="warning",
        fields=fields,
    )


def notify_deployment_success(
    config: NotificationConfig,
    project_name: str,
    deploy_type: str,
    target: str,
    commit: str,
    duration_seconds: float,
    violations_fixed: int = 0,
) -> bool:
    """Notify deployment succeeded."""
    if not config.enabled:
        return False

    message = f"✅ Deployment succeeded: *{project_name}*"
    fields = [
        {"title": "Type", "value": deploy_type, "short": True},
        {"title": "Target", "value": target, "short": True},
        {"title": "Commit", "value": commit[:7], "short": True},
        {"title": "Duration", "value": f"{duration_seconds:.1f}s", "short": True},
    ]

    if violations_fixed > 0:
        fields.append(
            {"title": "Violations Fixed", "value": str(violations_fixed), "short": True}
        )

    return send_slack_notification(
        config.slack_webhook_url,
        message,
        color="good",
        fields=fields,
    )


def notify_deployment_failure(
    config: NotificationConfig,
    project_name: str,
    deploy_type: str,
    target: str,
    commit: str,
    error: str,
    violations_count: int = 0,
) -> bool:
    """Notify deployment failed."""
    if not config.enabled:
        return False

    mention = config.mention_on_failure
    message = f"❌ Deployment failed: *{project_name}*"
    if mention:
        message = f"{mention} {message}"

    fields = [
        {"title": "Type", "value": deploy_type, "short": True},
        {"title": "Target", "value": target, "short": True},
        {"title": "Commit", "value": commit[:7], "short": True},
        {"title": "Error", "value": error[:200], "short": False},
    ]

    if violations_count > 0:
        fields.append(
            {"title": "CRITICAL Violations", "value": str(violations_count), "short": True}
        )

    return send_slack_notification(
        config.slack_webhook_url,
        message,
        color="danger",
        fields=fields,
    )


def notify_scan_blocked(
    config: NotificationConfig,
    project_name: str,
    violations_count: int,
    critical_count: int,
) -> bool:
    """Notify deployment blocked by scan violations."""
    if not config.enabled:
        return False

    mention = config.mention_on_failure
    message = f"🚫 Deployment blocked: *{project_name}*"
    if mention:
        message = f"{mention} {message}"

    fields = [
        {"title": "Total Violations", "value": str(violations_count), "short": True},
        {"title": "CRITICAL", "value": str(critical_count), "short": True},
        {"title": "Action", "value": "Fix violations and retry", "short": False},
    ]

    return send_slack_notification(
        config.slack_webhook_url,
        message,
        color="danger",
        fields=fields,
    )