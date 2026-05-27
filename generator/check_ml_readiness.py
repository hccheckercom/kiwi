"""Check labeled data status for ML training."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from memory.db import get_connection

conn = get_connection()

# Check component_patterns table for labeled data
cursor = conn.execute('''
    SELECT
        COUNT(*) as total,
        SUM(CASE WHEN user_accepted IS NOT NULL THEN 1 ELSE 0 END) as labeled,
        SUM(CASE WHEN user_accepted = 1 THEN 1 ELSE 0 END) as accepted,
        SUM(CASE WHEN user_accepted = 0 THEN 1 ELSE 0 END) as rejected
    FROM component_patterns
''')
stats = cursor.fetchone()
conn.close()

print(f'Component Patterns Stats:')
print(f'  Total patterns: {stats[0]}')
print(f'  Labeled (with user feedback): {stats[1]}')
print(f'  Accepted: {stats[2]}')
print(f'  Rejected: {stats[3]}')
print(f'')

if stats[1] >= 20:
    print('ML Training Status: READY')
    print(f'  Minimum required: 20 labeled samples')
    print(f'  Current: {stats[1]} labeled samples')
else:
    print('ML Training Status: NEED MORE LABELS')
    print(f'  Minimum required: 20 labeled samples')
    print(f'  Current: {stats[1]} labeled samples')
    print(f'  Need: {20 - stats[1]} more labeled samples')
    print(f'')
    print('Note: Component patterns are logged automatically during generation.')
    print('To get labeled data, we need user feedback (accepted/rejected).')
    print('For now, we can simulate feedback or skip ML training.')
