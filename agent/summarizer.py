"""Context window management: summarization and compression."""

from typing import Any, Dict, List
from collections import defaultdict


class ViolationSummarizer:
    """Compress violations for context window efficiency."""

    def summarize_violations(
        self, violations: List[Dict[str, Any]], max_per_lesson: int = 3
    ) -> Dict[str, Any]:
        """
        Summarize violations by grouping and sampling.

        Returns:
            {
                'summary': {lesson_id: {count, severity, sample_files}},
                'total_count': int,
                'severity_breakdown': {CRITICAL: int, HIGH: int, SUGGEST: int},
                'top_files': [(file, count)],
                'compressed_violations': [sampled violations]
            }
        """
        if not violations:
            return {
                'summary': {},
                'total_count': 0,
                'severity_breakdown': {'CRITICAL': 0, 'HIGH': 0, 'SUGGEST': 0},
                'top_files': [],
                'compressed_violations': []
            }

        # Group by lesson_id
        by_lesson = defaultdict(list)
        for v in violations:
            by_lesson[v['lesson_id']].append(v)

        # Group by file
        by_file = defaultdict(int)
        for v in violations:
            by_file[v['file']] += 1

        # Severity breakdown
        severity_breakdown = {'CRITICAL': 0, 'HIGH': 0, 'SUGGEST': 0}
        for v in violations:
            severity_breakdown[v['severity']] += 1

        # Build summary
        summary = {}
        compressed = []

        for lesson_id, lesson_violations in by_lesson.items():
            # Sample up to max_per_lesson violations
            sampled = lesson_violations[:max_per_lesson]
            compressed.extend(sampled)

            # Get unique files
            files = list(set(v['file'] for v in lesson_violations))

            summary[lesson_id] = {
                'count': len(lesson_violations),
                'severity': lesson_violations[0]['severity'],
                'title': lesson_violations[0].get('title', 'Unknown'),
                'sample_files': files[:5],  # Top 5 files
                'total_files': len(files)
            }

        # Top files by violation count
        top_files = sorted(by_file.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            'summary': summary,
            'total_count': len(violations),
            'severity_breakdown': severity_breakdown,
            'top_files': top_files,
            'compressed_violations': compressed
        }

    def summarize_scan_result(self, scan_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compress full scan result for context efficiency.

        Args:
            scan_result: Full scan result with violations

        Returns:
            Compressed scan result with summary
        """
        violations = scan_result.get('violations', [])
        summary = self.summarize_violations(violations)

        return {
            'path': scan_result.get('path'),
            'platform': scan_result.get('platform'),
            'severity': scan_result.get('severity'),
            'total_violations': summary['total_count'],
            'severity_breakdown': summary['severity_breakdown'],
            'lessons_triggered': len(summary['summary']),
            'top_files': summary['top_files'],
            'lesson_summary': summary['summary'],
            'sample_violations': summary['compressed_violations']
        }

    def compress_agent_history(
        self, history: List[Dict[str, Any]], keep_recent: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Compress agent execution history.

        Keep recent N iterations in full, summarize older ones.

        Args:
            history: List of iteration records
            keep_recent: Number of recent iterations to keep in full

        Returns:
            Compressed history
        """
        if len(history) <= keep_recent:
            return history

        # Keep recent iterations
        recent = history[-keep_recent:]

        # Summarize older iterations
        older = history[:-keep_recent]
        older_summary = {
            'type': 'compressed_history',
            'iterations': len(older),
            'fixes_applied': sum(1 for h in older if h.get('action') == 'fix'),
            'violations_resolved': sum(
                len(h.get('resolved_violations', [])) for h in older
            ),
            'total_tokens': sum(h.get('tokens_used', 0) for h in older)
        }

        return [older_summary] + recent


class ScanResultCompressor:
    """Compress scan results for storage and transmission."""

    def compress(self, scan_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compress scan result by removing redundant data.

        Keeps:
        - Metadata (path, platform, severity)
        - Violation counts and breakdown
        - Sample violations (not all)
        - Lesson summaries

        Removes:
        - Full violation details for all violations
        - Duplicate file paths
        - Verbose lesson bodies
        """
        summarizer = ViolationSummarizer()
        return summarizer.summarize_scan_result(scan_result)

    def decompress(self, compressed: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decompress scan result (partial reconstruction).

        Note: Full violations cannot be recovered, only samples.
        """
        return {
            'path': compressed.get('path'),
            'platform': compressed.get('platform'),
            'severity': compressed.get('severity'),
            'violations': compressed.get('sample_violations', []),
            'metadata': {
                'compressed': True,
                'total_violations': compressed.get('total_violations'),
                'severity_breakdown': compressed.get('severity_breakdown'),
                'lessons_triggered': compressed.get('lessons_triggered')
            }
        }