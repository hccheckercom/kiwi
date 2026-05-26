"""
Gap Detector — Identify uncovered patterns and suggest lessons.

Proactive coverage: find patterns not protected by any lesson.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from .inventory import CodePattern, FileInventory
from .coverage import CoverageMatcher, MatchResult


@dataclass
class CoverageGap:
    """A pattern not covered by any lesson"""
    pattern: CodePattern
    gap_type: str  # 'uncovered_api', 'uncovered_security', 'uncovered_error', 'context_specific'
    severity: str  # CRITICAL, HIGH, SUGGEST
    confidence: float  # 0-1 (how confident this is a real gap)
    suggested_lesson: Dict  # auto-generated lesson metadata


@dataclass
class GapReport:
    """Report of coverage gaps in a file"""
    file_path: str
    total_gaps: int = 0
    critical_gaps: int = 0
    high_gaps: int = 0
    suggest_gaps: int = 0
    gaps: List[CoverageGap] = field(default_factory=list)


class GapDetector:
    """Detect patterns not covered by lessons"""

    # API patterns that should always have error handling
    API_PATTERNS = {
        'wp_remote_post', 'wp_remote_get', 'wp_remote_request',
        'fetch', 'axios', '$.ajax',
        'curl_exec', 'file_get_contents',
    }

    # Security operations that should always be validated
    SECURITY_PATTERNS = {
        'wp_verify_nonce', 'check_ajax_referer', 'sanitize_text_field',
        'esc_html', 'esc_attr', 'esc_url',
        '$_GET', '$_POST', '$_REQUEST', '$_SERVER',
    }

    # Database operations that should be prepared
    DB_PATTERNS = {
        '$wpdb->query', '$wpdb->get_results', '$wpdb->insert',
    }

    def __init__(self, platform: Optional[str] = None):
        self.matcher = CoverageMatcher(platform=platform)

    def detect_gaps(self, inventory: FileInventory) -> GapReport:
        """
        Detect coverage gaps in file inventory.

        Returns:
            GapReport with all gaps found
        """
        report = GapReport(file_path=inventory.file_path)

        for pattern in inventory.patterns:
            # Match pattern to lessons
            match = self.matcher.match_pattern(pattern)

            if not match.is_covered:
                # This is a gap
                gap = self._create_gap(pattern, match)
                report.gaps.append(gap)
                report.total_gaps += 1

                # Count by severity
                if gap.severity == 'CRITICAL':
                    report.critical_gaps += 1
                elif gap.severity == 'HIGH':
                    report.high_gaps += 1
                else:
                    report.suggest_gaps += 1

        return report

    def _create_gap(self, pattern: CodePattern, match: MatchResult) -> CoverageGap:
        """Create CoverageGap from uncovered pattern"""
        gap_type = self._infer_gap_type(pattern)
        severity = self._infer_gap_severity(pattern, gap_type)
        confidence = self._calculate_confidence(pattern, match, gap_type)
        suggested_lesson = self._generate_lesson_suggestion(pattern, gap_type)

        return CoverageGap(
            pattern=pattern,
            gap_type=gap_type,
            severity=severity,
            confidence=confidence,
            suggested_lesson=suggested_lesson
        )

    def _infer_gap_type(self, pattern: CodePattern) -> str:
        """Infer gap type from pattern"""
        name = pattern.pattern_name

        # Check if it's an API call
        if any(api.lower() in name.lower() for api in self.API_PATTERNS):
            return 'uncovered_api'

        # Check if it's a security operation (exact match or starts with)
        for sec in self.SECURITY_PATTERNS:
            if name == sec or name.startswith(sec):
                return 'uncovered_security'

        # Check if it's error handling
        if pattern.pattern_type == 'error_handling':
            return 'uncovered_error'

        # Check if it's a database operation
        if any(db in name for db in self.DB_PATTERNS):
            return 'uncovered_db'

        # Default: context-specific
        return 'context_specific'

    def _infer_gap_severity(self, pattern: CodePattern, gap_type: str) -> str:
        """Infer severity for gap"""
        # API calls without error handling = CRITICAL
        if gap_type == 'uncovered_api':
            return 'CRITICAL'

        # Security operations = CRITICAL
        if gap_type == 'uncovered_security':
            return 'CRITICAL'

        # Database operations = HIGH
        if gap_type == 'uncovered_db':
            return 'HIGH'

        # Error handling = HIGH
        if gap_type == 'uncovered_error':
            return 'HIGH'

        # Context-specific = use pattern's inferred severity
        return pattern.severity

    def _calculate_confidence(self, pattern: CodePattern, match: MatchResult, gap_type: str) -> float:
        """
        Calculate confidence that this is a real gap.

        High confidence = definitely needs a lesson
        Low confidence = might be false positive
        """
        confidence = 0.5  # baseline

        # High-risk patterns = high confidence
        if gap_type in ['uncovered_api', 'uncovered_security']:
            confidence += 0.3

        # Low similarity to existing lessons = higher confidence it's truly uncovered
        if match.similarity_score < 0.2:
            confidence += 0.2
        elif match.similarity_score < 0.4:
            confidence += 0.1

        # Pattern type matters
        if pattern.pattern_type in ['security_op', 'function_call']:
            confidence += 0.1

        return min(1.0, confidence)

    def _generate_lesson_suggestion(self, pattern: CodePattern, gap_type: str) -> Dict:
        """
        Auto-generate lesson metadata from gap.

        Returns:
            Dict with title, pattern, why, bad_code, good_code
        """
        name = pattern.pattern_name
        context = pattern.context

        # Generate title
        if gap_type == 'uncovered_api':
            title = f"Missing error handling for {name}"
        elif gap_type == 'uncovered_security':
            title = f"Missing validation for {name}"
        elif gap_type == 'uncovered_db':
            title = f"Unprepared database query in {name}"
        elif gap_type == 'uncovered_error':
            title = f"Missing error handling pattern"
        else:
            title = f"Uncovered pattern: {name}"

        # Generate pattern (regex)
        # Simple approach: escape special chars and make it a literal match
        import re
        pattern_regex = re.escape(name)

        # Generate why
        why_map = {
            'uncovered_api': f"API calls like {name} can fail due to network issues, timeouts, or invalid responses. Without error handling, failures cause silent bugs or fatal errors.",
            'uncovered_security': f"Security operations like {name} must be validated to prevent vulnerabilities. Missing validation can lead to XSS, SQL injection, or unauthorized access.",
            'uncovered_db': f"Database operations like {name} must use prepared statements to prevent SQL injection. Direct queries with user input are a critical security risk.",
            'uncovered_error': "Error handling ensures graceful degradation when operations fail. Missing error handling leads to poor UX and hard-to-debug issues.",
            'context_specific': f"Pattern {name} is used but not covered by existing lessons. This may indicate a new risk or edge case."
        }
        why = why_map.get(gap_type, f"Pattern {name} is not covered by existing lessons.")

        # Generate bad/good code examples
        bad_code = context  # Use actual code as bad example

        if gap_type == 'uncovered_api':
            good_code = f"""// Good: Handle errors
$response = {name}($url, $data);
if (is_wp_error($response)) {{
    error_log('API call failed: ' . $response->get_error_message());
    return false;
}}"""
        elif gap_type == 'uncovered_security':
            good_code = f"""// Good: Validate input
if (!{name}($_POST['field'])) {{
    wp_send_json_error('Invalid input');
}}"""
        elif gap_type == 'uncovered_db':
            good_code = f"""// Good: Use prepared statements
$query = $wpdb->prepare("SELECT * FROM table WHERE id = %d", $id);
$results = $wpdb->get_results($query);"""
        else:
            good_code = f"// TODO: Add good example for {name}"

        # Infer category
        category_map = {
            'uncovered_api': 'php-error-handling',
            'uncovered_security': 'php-security',
            'uncovered_db': 'php-security',
            'uncovered_error': 'php-error-handling',
            'context_specific': 'code-quality'
        }
        category = category_map.get(gap_type, 'code-quality')

        return {
            'title': title,
            'category': category,
            'severity': self._infer_gap_severity(pattern, gap_type),
            'pattern': pattern_regex,
            'why': why,
            'bad_code': bad_code,
            'good_code': good_code,
            'scope': '**/*.php' if pattern.language == 'php' else '**/*.{js,ts,jsx,tsx}',
            'platform': 'wp' if pattern.language == 'php' else 'nextjs',
            'tags': [gap_type.replace('uncovered_', ''), pattern.pattern_type],
        }


def detect_gaps(inventory: FileInventory, platform: Optional[str] = None) -> GapReport:
    """
    Convenience function to detect gaps in file inventory.

    Args:
        inventory: FileInventory from inventory.py
        platform: 'wp' or 'nextjs' (optional)

    Returns:
        GapReport with all gaps
    """
    detector = GapDetector(platform=platform)
    return detector.detect_gaps(inventory)


if __name__ == '__main__':
    import sys
    from .inventory import extract_inventory

    if len(sys.argv) < 2:
        print("Usage: python gaps.py <file_path>")
        sys.exit(1)

    file_path = sys.argv[1]

    # Extract inventory
    print(f"Extracting patterns from {file_path}...")
    inventory = extract_inventory(file_path)

    # Detect gaps
    print(f"Detecting coverage gaps...")
    report = detect_gaps(inventory)

    # Print report
    print()
    print(f"Gap Report: {report.file_path}")
    print(f"Total gaps: {report.total_gaps}")
    print(f"  CRITICAL: {report.critical_gaps}")
    print(f"  HIGH: {report.high_gaps}")
    print(f"  SUGGEST: {report.suggest_gaps}")
    print()

    if report.gaps:
        print("GAPS DETECTED:")
        for i, gap in enumerate(report.gaps[:10], 1):  # Show first 10
            print(f"\n{i}. [{gap.severity}] {gap.suggested_lesson['title']}")
            print(f"   Line {gap.pattern.line}: {gap.pattern.context[:80]}")
            print(f"   Gap type: {gap.gap_type}")
            print(f"   Confidence: {gap.confidence:.2f}")

        if len(report.gaps) > 10:
            print(f"\n... and {len(report.gaps) - 10} more gaps")