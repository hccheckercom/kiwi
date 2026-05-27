"""Test full generation pipeline on synthetic demos."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from demo_orchestrator import DemoThemeGenerator

generator = DemoThemeGenerator()

for i in [1, 2]:
    print(f'\n=== Generating from Demo {i} ===')

    base_path = Path(__file__).parent.parent.parent.parent / 'themes'
    demo_path = base_path / f'synthetic-demo-{i}'

    report = generator.generate_from_demo(
        demo_path=str(demo_path),
        theme_name=f'test-theme-{i}',
        mode='foundation',
        confidence_threshold=0.7
    )

    if 'error' in report:
        print(f'FAILED: {report["error"]}')
    else:
        print(f'SUCCESS: Gen ID {report["gen_id"]}')
        print(f'  Files: {report["files_created"]}')
        print(f'  Components detected: {report["components_detected"]}')
        print(f'  Components applied: {report["components_applied"]}')