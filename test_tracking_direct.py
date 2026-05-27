"""Test rollback tracking directly."""

from memory.rollback_tracking import record_rollback, get_rollback_stats

# Test recording a rollback
print('Recording rollback for LES-999...')
record_rollback('LES-999', 'test.php', 'Tests failed')

# Check stats
stats = get_rollback_stats('LES-999')
print(f'Rollback count: {stats["rollback_count"]}')
print(f'Last rollback at: {stats["last_rollback_at"]}')

if stats['rollback_count'] > 0:
    print('\n[SUCCESS] Rollback tracking works!')
else:
    print('\n[FAIL] Rollback not recorded')