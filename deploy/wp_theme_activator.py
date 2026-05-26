"""WordPress theme activation via PHP script (wp-cli fails on multisite)."""

import subprocess
from pathlib import Path
from typing import Dict, Optional

DEPLOY_DIR = Path(__file__).parent


def activate_theme_on_subsite(
    host: str,
    port: int,
    user: str,
    key_path: str,
    wp_path: str,
    theme_name: str,
    blog_id: int,
    create_homepage: bool = True,
) -> Dict:
    """
    Activate theme on WordPress multisite subsite via PHP script.

    wp-cli `wp theme activate` fails on multisite with "Could not switch to theme" error
    even when theme validation passes. This uses PHP script as workaround.

    Based on: .claude/docs/HANDOFF-WP-THEME-DEPLOYMENT-ISSUE.md
    """

    # Step 1: Disable Redis (cache overrides DB updates)
    disable_redis = f"ssh -o StrictHostKeyChecking=no -p {port} -i {key_path} {user}@{host} 'cd {wp_path} && wp plugin deactivate redis-cache --network --allow-root'"
    result = _execute(disable_redis)
    if result["returncode"] != 0:
        return {"success": False, "error": "Failed to disable Redis", "stderr": result["stderr"]}

    # Step 2: Activate theme via PHP script
    php_script = _build_activation_script(blog_id, theme_name, create_homepage)
    activate_cmd = f"ssh -o StrictHostKeyChecking=no -p {port} -i {key_path} {user}@{host} 'cd {wp_path} && php -r {_shell_quote(php_script)}'"
    result = _execute(activate_cmd)
    if result["returncode"] != 0:
        # Re-enable Redis before returning error
        _execute(f"ssh -o StrictHostKeyChecking=no -p {port} -i {key_path} {user}@{host} 'cd {wp_path} && wp plugin activate redis-cache --network --allow-root'")
        return {"success": False, "error": "Failed to activate theme", "stderr": result["stderr"]}

    # Step 3: Re-enable Redis
    enable_redis = f"ssh -o StrictHostKeyChecking=no -p {port} -i {key_path} {user}@{host} 'cd {wp_path} && wp plugin activate redis-cache --network --allow-root'"
    result = _execute(enable_redis)
    if result["returncode"] != 0:
        return {"success": False, "error": "Failed to re-enable Redis", "stderr": result["stderr"]}

    # Step 4: Flush all caches
    flush_cmd = f"ssh -o StrictHostKeyChecking=no -p {port} -i {key_path} {user}@{host} 'redis-cli FLUSHDB && cd {wp_path} && wp cache flush --allow-root && wp rewrite flush --allow-root'"
    result = _execute(flush_cmd)
    if result["returncode"] != 0:
        return {"success": False, "error": "Failed to flush caches", "stderr": result["stderr"]}

    return {"success": True, "blog_id": blog_id, "theme": theme_name}


def create_subsite(
    host: str,
    port: int,
    user: str,
    key_path: str,
    wp_path: str,
    slug: str,
    title: str,
    email: str = "admin@wezone.vn",
) -> Dict:
    """
    Create WordPress multisite subsite with correct URL structure.

    URL structure: path=/slug/ but URL=https://wp.wezone.vn/slug/ (no /themes/ prefix)
    """
    create_cmd = f"ssh -o StrictHostKeyChecking=no -p {port} -i {key_path} {user}@{host} 'cd {wp_path} && wp site create --slug={slug} --title=\"{title}\" --email={email} --allow-root'"
    result = _execute(create_cmd)

    if result["returncode"] != 0:
        return {"success": False, "error": "Failed to create subsite", "stderr": result["stderr"]}

    # Extract blog ID from output
    blog_id = _extract_blog_id(result["stdout"])
    if not blog_id:
        return {"success": False, "error": "Could not extract blog ID from wp site create output"}

    return {"success": True, "blog_id": blog_id, "slug": slug, "url": f"https://wp.wezone.vn/{slug}/"}


def _build_activation_script(blog_id: int, theme_name: str, create_homepage: bool) -> str:
    """Build PHP script for theme activation."""
    homepage_code = ""
    if create_homepage:
        homepage_code = """
$page_id = wp_insert_post([
    'post_type' => 'page',
    'post_title' => 'Home',
    'post_content' => '<h1>Welcome</h1><p>Theme deployed successfully.</p>',
    'post_status' => 'publish'
]);
update_option('show_on_front', 'page');
update_option('page_on_front', $page_id);
"""

    return f"""
define('WP_USE_THEMES', false);
require('./wp-load.php');
switch_to_blog({blog_id});
switch_theme('{theme_name}');
{homepage_code}
flush_rewrite_rules();
restore_current_blog();
"""


def _shell_quote(text: str) -> str:
    """Quote text for shell execution."""
    return "'" + text.replace("'", "'\\''") + "'"


def _extract_blog_id(output: str) -> Optional[int]:
    """Extract blog ID from wp site create output."""
    import re
    match = re.search(r"Success: Site (\d+) created", output)
    if match:
        return int(match.group(1))
    return None


def _execute(command: str) -> Dict:
    """Execute shell command."""
    import shlex
    try:
        result = subprocess.run(
            shlex.split(command),
            capture_output=True,
            text=True,
            timeout=60,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "stdout": "", "stderr": "Command timeout"}
    except Exception as e:
        return {"returncode": -1, "stdout": "", "stderr": str(e)}