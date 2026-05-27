"""Test kiwi_suggest_base MCP tool"""
import json
import sys
from pathlib import Path

# Add kiwi to path
KIWI_DIR = Path(__file__).parent
sys.path.insert(0, str(KIWI_DIR))

# Fix UTF-8 encoding for Windows console
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from mcp_server import _handle_suggest_base

def test_beauty_industry():
    """Test suggestion for beauty industry"""
    print("Testing beauty industry...")
    result = _handle_suggest_base({
        "industry": "beauty",
        "description": "Luxury skincare shop"
    })

    data = json.loads(result)
    print(json.dumps(data, indent=2))

    # Should return DNA defaults when no beauty themes in DB
    if data.get("base_theme") is None:
        # DNA defaults fallback
        assert data["suggested_colors"]["primary"] == "#F4E4E4"
        assert data["suggested_fonts"]["primary"] == "Playfair Display, serif"
        assert "dna" in data["reasoning"].lower() or "no beauty themes" in data["reasoning"].lower()
        print("✓ Beauty industry test passed (DNA defaults)\n")
    else:
        # Has theme in DB
        assert "match_score" in data
        assert "quality_score" in data
        print("✓ Beauty industry test passed (DB match)\n")

def test_tech_industry():
    """Test suggestion for tech industry"""
    print("Testing tech industry...")
    result = _handle_suggest_base({
        "industry": "tech"
    })

    data = json.loads(result)
    print(json.dumps(data, indent=2))

    # Should return DNA defaults when no tech themes in DB
    if data.get("base_theme") is None:
        assert data["suggested_colors"]["primary"] == "#105dad"
        assert data["suggested_fonts"]["primary"] == "Inter, sans-serif"
        print("✓ Tech industry test passed (DNA defaults)\n")
    else:
        assert "match_score" in data
        print("✓ Tech industry test passed (DB match)\n")

def test_unknown_industry():
    """Test suggestion for unknown industry"""
    print("Testing unknown industry...")
    result = _handle_suggest_base({
        "industry": "unknown"
    })

    data = json.loads(result)
    print(json.dumps(data, indent=2))

    # Should fallback to tech defaults
    if data.get("base_theme") is None:
        assert data["suggested_colors"]["primary"] == "#105dad"
        print("✓ Unknown industry test passed (DNA defaults)\n")
    else:
        assert "match_score" in data
        print("✓ Unknown industry test passed (DB match)\n")

if __name__ == "__main__":
    print("=" * 60)
    print("Kiwi Suggest Base - Integration Test")
    print("=" * 60 + "\n")

    try:
        test_beauty_industry()
        test_tech_industry()
        test_unknown_industry()

        print("=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)