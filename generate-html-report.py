#!/usr/bin/env python3
"""Generate static HTML report from Kiwi scan results."""

import json
import subprocess
import sys
from pathlib import Path

def run_scan(theme_path, severity="CRITICAL"):
    """Run Kiwi scan and return JSON results."""
    cmd = [
        "python3.11", "-m", "scanner.cli",
        "--theme", theme_path,
        "--severity", severity,
        "--json"
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd="/opt/kiwi"
    )

    # Extract JSON from output (skip progress lines)
    lines = result.stdout.split('\n')
    json_start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('{'):
            json_start = i
            break

    json_text = '\n'.join(lines[json_start:])
    return json.loads(json_text)

def generate_html(data, output_path):
    """Generate static HTML report."""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kiwi Scanner Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            padding: 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{
            font-size: 32px;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .meta {{
            color: #8b949e;
            margin-bottom: 20px;
            font-size: 14px;
        }}
        .summary {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
        }}
        .stat {{
            text-align: center;
            padding: 15px;
            background: #0d1117;
            border-radius: 6px;
        }}
        .stat-value {{
            font-size: 36px;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .stat-label {{
            font-size: 12px;
            text-transform: uppercase;
            color: #8b949e;
            letter-spacing: 1px;
        }}
        .critical {{ color: #f85149; }}
        .high {{ color: #f0883e; }}
        .suggest {{ color: #58a6ff; }}
        .violation {{
            background: #161b22;
            border-left: 4px solid;
            border-radius: 6px;
            padding: 20px;
            margin: 15px 0;
        }}
        .violation.CRITICAL {{ border-color: #f85149; }}
        .violation.HIGH {{ border-color: #f0883e; }}
        .violation.SUGGEST {{ border-color: #58a6ff; }}
        .violation-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 10px;
            flex-wrap: wrap;
        }}
        .badge {{
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
            text-transform: uppercase;
        }}
        .badge.CRITICAL {{ background: #f85149; color: #fff; }}
        .badge.HIGH {{ background: #f0883e; color: #fff; }}
        .badge.SUGGEST {{ background: #58a6ff; color: #fff; }}
        .lesson-id {{
            font-family: 'Courier New', monospace;
            color: #58a6ff;
            font-weight: bold;
        }}
        .category {{
            color: #8b949e;
            font-size: 12px;
            text-transform: uppercase;
        }}
        .description {{
            font-size: 16px;
            margin: 10px 0;
            line-height: 1.5;
        }}
        .file-info {{
            background: #0d1117;
            padding: 10px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            color: #8b949e;
            margin-top: 10px;
            word-break: break-all;
        }}
        .match {{
            background: #1f2937;
            padding: 8px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            margin-top: 8px;
            color: #f0883e;
            word-break: break-all;
        }}
        .success {{
            background: #161b22;
            border-left: 4px solid #3fb950;
            border-radius: 6px;
            padding: 20px;
            margin: 15px 0;
            text-align: center;
            font-size: 18px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🥝 Kiwi Scanner Report</h1>
        <div class="meta">
            Theme: {data['theme']}<br>
            Generated: {Path(__file__).stem}
        </div>

        <div class="summary">
            <div class="stat">
                <div class="stat-value critical">{data['summary']['critical']}</div>
                <div class="stat-label">Critical</div>
            </div>
            <div class="stat">
                <div class="stat-value high">{data['summary']['high']}</div>
                <div class="stat-label">High</div>
            </div>
            <div class="stat">
                <div class="stat-value suggest">{data['summary']['suggest']}</div>
                <div class="stat-label">Suggest</div>
            </div>
            <div class="stat">
                <div class="stat-value">{data['summary']['patterns_checked']}</div>
                <div class="stat-label">Patterns</div>
            </div>
            <div class="stat">
                <div class="stat-value">{data['summary']['files_scanned']}</div>
                <div class="stat-label">Files</div>
            </div>
        </div>
"""

    if not data['violations']:
        html += """
        <div class="success">
            ✓ No violations found! Theme is clean.
        </div>
"""
    else:
        for v in data['violations']:
            match_html = f'<div class="match">{v["match"]}</div>' if v.get('match') else ''
            html += f"""
        <div class="violation {v['severity']}">
            <div class="violation-header">
                <span class="badge {v['severity']}">{v['severity']}</span>
                <span class="lesson-id">{v['id']}</span>
                <span class="category">{v['category']}</span>
            </div>
            <div class="description">{v['description']}</div>
            <div class="file-info">📁 {v['file']}{':' + str(v['line']) if v['line'] > 0 else ''}</div>
            {match_html}
        </div>
"""

    html += """
    </div>
</body>
</html>
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

if __name__ == '__main__':
    theme = sys.argv[1] if len(sys.argv) > 1 else '/var/www/wp.wezone.vn/wp-content/themes/kiwi-production-test'
    severity = sys.argv[2] if len(sys.argv) > 2 else 'CRITICAL'
    output = sys.argv[3] if len(sys.argv) > 3 else '/var/www/html/kiwi-report.html'

    print(f"Scanning {theme}...")
    data = run_scan(theme, severity)

    print(f"Generating HTML report...")
    generate_html(data, output)

    print(f"✓ Report saved to {output}")
    print(f"  View at: http://103.90.227.103/kiwi-report.html")