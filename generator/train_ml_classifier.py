"""Train ML classifier with labeled data."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ml_retrain import MLRetrainer

print('Starting ML classifier training...')
print('='*60)

retrainer = MLRetrainer()

# Export training data
try:
    features, labels = retrainer.export_training_data()
    print(f'Exported {len(features)} labeled samples')
    print(f'  Positive (accepted): {sum(labels)}')
    print(f'  Negative (rejected): {len(labels) - sum(labels)}')
    print()

    # Train classifier
    results = retrainer.retrain_classifier(features, labels)

    print('Training complete!')
    print(f'  Accuracy: {results["accuracy"]:.2%}')
    print(f'  Precision: {results["precision"]:.2%}')
    print(f'  Recall: {results["recall"]:.2%}')

    # Calculate F1 score manually if not in results
    if "f1" in results:
        print(f'  F1 Score: {results["f1"]:.2%}')
    else:
        precision = results["precision"]
        recall = results["recall"]
        if precision + recall > 0:
            f1 = 2 * (precision * recall) / (precision + recall)
            print(f'  F1 Score: {f1:.2%}')

    print()
    print('Model saved to: generator/ai/component_classifier.pkl')
    print()

    # Show recommendations
    if results["accuracy"] < 0.80:
        print('Recommendations:')
        print('  - Accuracy < 80%: Need more labeled training data')
        print('  - Current: 24 samples, target: 50+ samples')
        print('  - Generate more demos and label components')

except Exception as e:
    print(f'Training failed: {e}')
    import traceback
    traceback.print_exc()
