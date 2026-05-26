import subprocess, json, sys

result = subprocess.run(
    [sys.executable, "-m", "scanner.cli", "--theme",
     r"D:\projects\wezone\themes\fashion-apparel\wezone-trunganh-v2",
     "--platform", "wp", "--json"],
    capture_output=True, text=True, encoding="utf-8",
    cwd=r"D:\projects\wezone\.claude\kiwi", timeout=120
)

data = json.loads(result.stdout) if result.stdout.strip() else {"violations": []}
ids = {"LES-268","LES-269","LES-270","LES-271","LES-272","LES-273","LES-274",
       "LES-275","LES-276","LES-277","LES-278","FEA-025","FEA-026","FEA-027"}

edge = [v for v in data.get("violations", []) if v.get("id") in ids]
for v in edge:
    desc = v.get("description", "")[:80]
    f = v.get("file", "NO FILE")
    line = v.get("line", "")
    print(f"[{v['id']}] {v.get('severity','?')} | {f}:{line} | {desc}")

print(f"\n--- Total edge-cases violations: {len(edge)} ---")
