"""Generate synthetic training data by creating more demo variations."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from demo_orchestrator import DemoThemeGenerator


def generate_synthetic_demos():
    """Generate multiple synthetic demos with different configurations."""
    generator = DemoThemeGenerator()
    base_path = Path(__file__).parent.parent.parent.parent / 'themes'

    # Test configurations: (demo_num, threshold, mode)
    configs = [
        (1, 0.6, 'foundation'),
        (1, 0.7, 'foundation'),
        (1, 0.8, 'foundation'),
        (2, 0.6, 'foundation'),
        (2, 0.7, 'foundation'),
        (2, 0.8, 'foundation'),
    ]

    results = []

    for demo_num, threshold, mode in configs:
        demo_path = base_path / f'synthetic-demo-{demo_num}'
        theme_name = f'ml-train-demo{demo_num}-t{int(threshold*10)}'

        print(f'\nGenerating: demo={demo_num}, threshold={threshold}, mode={mode}')

        try:
            report = generator.generate_from_demo(
                demo_path=str(demo_path),
                theme_name=theme_name,
                mode=mode,
                confidence_threshold=threshold
            )

            if 'error' in report:
                print(f'  FAILED: {report["error"]}')
                results.append({'config': (demo_num, threshold, mode), 'status': 'failed'})
            else:
                print(f'  SUCCESS: {report["components_detected"]} components detected')
                results.append({'config': (demo_num, threshold, mode), 'status': 'success', 'report': report})

        except Exception as e:
            print(f'  ERROR: {e}')
            results.append({'config': (demo_num, threshold, mode), 'status': 'error'})

    # Summary
    print('\n=== Generation Summary ===')
    success_count = sum(1 for r in results if r['status'] == 'success')
    print(f'Successful: {success_count}/{len(configs)}')

    return results


if __name__ == '__main__':
    generate_synthetic_demos()
