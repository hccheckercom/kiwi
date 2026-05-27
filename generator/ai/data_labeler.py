"""Data Labeler — Extract labeled components from Kiwi Templates and demos"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any
from bs4 import BeautifulSoup


class DataLabeler:
    """
    Label components from Kiwi Templates and demos for ML training.

    Usage:
        labeler = DataLabeler()
        training_data = labeler.collect_all()
    """

    def __init__(self, kiwi_dir: Path = None):
        if kiwi_dir is None:
            kiwi_dir = Path(__file__).parent.parent.parent
        self.kiwi_dir = kiwi_dir
        self.templates_dir = kiwi_dir / "templates" / "sections"

    def collect_all(self) -> List[Dict[str, Any]]:
        """Collect all labeled data from templates and demos."""
        data = []

        # From Kiwi Templates
        template_data = self.label_from_templates()
        data.extend(template_data)
        print(f"Collected {len(template_data)} examples from Kiwi Templates")

        return data

    def label_from_templates(self) -> List[Dict[str, Any]]:
        """Extract labeled components from Kiwi Templates."""
        labeled = []

        if not self.templates_dir.exists():
            print(f"WARNING: Templates directory not found: {self.templates_dir}")
            return labeled

        # Scan all TPL-*.md files
        for md_file in self.templates_dir.rglob("TPL-*.md"):
            try:
                component = self._parse_template_file(md_file)
                if component:
                    labeled.append(component)
            except Exception as e:
                print(f"WARNING: Failed to parse {md_file.name}: {e}")

        return labeled

    def _parse_template_file(self, md_path: Path) -> Dict[str, Any]:
        """Parse template markdown file to extract component data."""
        content = md_path.read_text(encoding="utf-8")

        # Extract frontmatter
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if not frontmatter_match:
            return None

        frontmatter_text = frontmatter_match.group(1)
        metadata = self._parse_frontmatter(frontmatter_text)

        # Extract HTML code blocks
        code_blocks = re.findall(r'```(?:html|php)\n(.*?)\n```', content, re.DOTALL)
        if not code_blocks:
            return None

        # Use first code block as example
        html_code = code_blocks[0]

        # Parse HTML to extract features
        soup = BeautifulSoup(html_code, 'html.parser')
        root = soup.find()

        if not root:
            return None

        # Extract features
        classes = root.get('class', [])
        text_content = root.get_text(strip=True)[:200]  # First 200 chars

        return {
            'id': metadata.get('id', md_path.stem),
            'type': metadata.get('section', 'unknown'),
            'html': html_code[:1000],  # First 1000 chars
            'classes': classes,
            'text': text_content,
            'tags': metadata.get('tags', []),
            'source': 'kiwi_template',
            'file': str(md_path.relative_to(self.kiwi_dir))
        }

    def _parse_frontmatter(self, text: str) -> Dict[str, Any]:
        """Parse YAML-like frontmatter."""
        metadata = {}

        for line in text.split('\n'):
            if ':' not in line:
                continue

            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            # Handle arrays
            if value.startswith('[') and value.endswith(']'):
                value = [v.strip().strip('"').strip("'") for v in value[1:-1].split(',')]

            metadata[key] = value

        return metadata

    def save_training_data(self, data: List[Dict], output_path: str):
        """Save training data to JSON file."""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"Saved {len(data)} training examples to {output_path}")


def main():
    """CLI for collecting training data."""
    import sys

    labeler = DataLabeler()
    training_data = labeler.collect_all()

    # Save to file
    output_path = Path(__file__).parent / "training_data.json"
    labeler.save_training_data(training_data, str(output_path))

    # Print summary
    print(f"\nTraining Data Summary:")
    print(f"  Total examples: {len(training_data)}")

    # Count by type
    type_counts = {}
    for item in training_data:
        comp_type = item['type']
        type_counts[comp_type] = type_counts.get(comp_type, 0) + 1

    print(f"  By type:")
    for comp_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"    {comp_type}: {count}")


if __name__ == "__main__":
    main()