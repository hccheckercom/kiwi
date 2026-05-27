"""Generate more synthetic demos for ML training data collection."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from demo_orchestrator import DemoThemeGenerator

# Check current feedback count
sys.path.insert(0, str(Path(__file__).parent.parent))
from memory.db import get_connection

conn = get_connection()
cursor = conn.execute('SELECT COUNT(*) FROM generator_feedback')
count = cursor.fetchone()[0]
conn.close()

print(f'Current feedback entries: {count}')
print(f'Target for ML training: 10+')
print(f'Status: {"READY" if count >= 10 else "NEED MORE"} ({count}/10)\n')

if count >= 10:
    print('Ready to train ML classifier!')
    sys.exit(0)

# Generate more themes to reach 10+ feedback entries
generator = DemoThemeGenerator()
base_path = Path(__file__).parent.parent.parent.parent / 'themes'

# Test with different confidence thresholds
test_configs = [
    (1, 0.6),  # Demo 1, threshold 0.6
    (2, 0.6),  # Demo 2, threshold 0.6
    (1, 0.8),  # Demo 1, threshold 0.8
    (2, 0.8),  # Demo 2, threshold 0.8
]

for demo_num, threshold in test_configs:
    if count >= 10:
        break

    print(f'\n=== Generating Demo {demo_num} with threshold {threshold} ===')

    demo_path = base_path / f'synthetic-demo-{demo_num}'
    theme_name = f'test-theme-{demo_num}-t{int(threshold*10)}'

    report = generator.generate_from_demo(
        demo_path=str(demo_path),
        theme_name=theme_name,
        mode='foundation',
        confidence_threshold=threshold
    )

    if 'error' in report:
        print(f'FAILED: {report["error"]}')
    else:
        print(f'SUCCESS: Gen ID {report["gen_id"][:8]}')
        count += 1

print(f'\n=== Final Status ===')
print(f'Total feedback entries: {count}')
print(f'Ready for ML training: {"YES" if count >= 10 else "NO"}')
