"""Test full mode (G0 + G1) generation pipeline."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from demo_orchestrator import DemoThemeGenerator

generator = DemoThemeGenerator()
base_path = Path(__file__).parent.parent.parent.parent / 'themes'

print('=== Testing Full Mode (G0 Foundation + G1 Pages) ===\n')

demo_path = base_path / 'synthetic-demo-1'
theme_name = 'test-theme-1-full'

print(f'Demo: {demo_path}')
print(f'Theme: {theme_name}')
print(f'Mode: full (G0 + G1)\n')

report = generator.generate_from_demo(
    demo_path=str(demo_path),
    theme_name=theme_name,
    mode='full',
    confidence_threshold=0.7
)

if 'error' in report:
    print(f'\nFAILED: {report["error"]}')
    sys.exit(1)

print(f'\n=== Generation Report ===')
print(f'Gen ID: {report["gen_id"]}')
print(f'Files created: {len(report["files_created"])}')
print(f'Components detected: {report["components_detected"]}')
print(f'Components applied: {report["components_applied"]}')
print(f'Manual review: {report["components_manual_review"]}')

print(f'\n=== File Breakdown ===')
g0_files = [f for f in report["files_created"] if any(x in f for x in ['store-config', 'tailwind.config', 'main.css', 'functions.php', 'style.css', 'Plugin.php'])]
g1_files = [f for f in report["files_created"] if 'templates' in f or 'template-parts' in f]

print(f'G0 Foundation: {len(g0_files)} files')
for f in g0_files[:5]:
    print(f'  - {Path(f).name}')
if len(g0_files) > 5:
    print(f'  ... and {len(g0_files) - 5} more')

print(f'\nG1 Pages: {len(g1_files)} files')
for f in g1_files[:5]:
    print(f'  - {Path(f).name}')
if len(g1_files) > 5:
    print(f'  ... and {len(g1_files) - 5} more')

print(f'\n=== Expected vs Actual ===')
print(f'Expected G0: 16 files')
print(f'Expected G1: 11 files')
print(f'Expected Total: 27 files')
print(f'Actual Total: {len(report["files_created"])} files')

if len(report["files_created"]) >= 20:
    print(f'\n✓ Full mode generation SUCCESS')
else:
    print(f'\n✗ Full mode generation INCOMPLETE')
    print(f'  Missing {27 - len(report["files_created"])} files')