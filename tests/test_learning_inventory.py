"""Unit tests for Pattern Inventory Extractor"""

import pytest
from pathlib import Path
import tempfile
import os

from learning.inventory import (
    InventoryExtractor,
    extract_inventory,
    CodePattern,
    FileInventory
)


@pytest.fixture
def temp_php_file():
    """Create temporary PHP file for testing"""
    content = """<?php
class TestPlugin {
    public function send_notification($user_id, $message) {
        $response = wp_remote_post($url, $data);
        return $response;
    }

    public function get_user_data($id) {
        global $wpdb;
        $query = "SELECT * FROM users WHERE id = $id";
        return $wpdb->get_results($query);
    }

    public function handle_ajax() {
        $value = $_POST['value'];
        echo $value;
    }
}

function custom_hook() {
    add_action('init', 'my_function');
}
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.php', delete=False, encoding='utf-8') as f:
        f.write(content)
        temp_path = f.name

    yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_js_file():
    """Create temporary JS file for testing"""
    content = """
async function fetchData() {
    const response = await fetch('/api/data');
    return response.json();
}

class DataService {
    async getData(id) {
        try {
            const result = await axios.get(`/api/${id}`);
            return result.data;
        } catch (error) {
            console.error(error);
        }
    }
}

function MyComponent() {
    const [data, setData] = useState(null);

    useEffect(() => {
        fetchData();
    }, []);
}
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
        f.write(content)
        temp_path = f.name

    yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


class TestInventoryExtractor:
    """Test InventoryExtractor class"""

    def test_extract_php_functions(self, temp_php_file):
        """Test extraction of PHP function definitions"""
        extractor = InventoryExtractor()
        inventory = extractor.extract(temp_php_file)

        assert inventory.language == 'php'
        assert inventory.total_patterns > 0

        # Check function definitions
        func_patterns = [p for p in inventory.patterns if p.pattern_type == 'function_def']
        assert len(func_patterns) >= 1
        assert any(p.pattern_name == 'custom_hook' for p in func_patterns)

    def test_extract_php_classes(self, temp_php_file):
        """Test extraction of PHP class definitions"""
        extractor = InventoryExtractor()
        inventory = extractor.extract(temp_php_file)

        class_patterns = [p for p in inventory.patterns if p.pattern_type == 'class_def']
        assert len(class_patterns) >= 1
        assert any(p.pattern_name == 'TestPlugin' for p in class_patterns)

    def test_extract_security_ops(self, temp_php_file):
        """Test extraction of security-sensitive operations"""
        extractor = InventoryExtractor()
        inventory = extractor.extract(temp_php_file)

        security_patterns = [p for p in inventory.patterns if p.pattern_type == 'security_op']
        assert len(security_patterns) >= 1
        assert any(p.pattern_name == 'wp_remote_post' for p in security_patterns)

        # Check severity
        wp_remote = [p for p in security_patterns if p.pattern_name == 'wp_remote_post'][0]
        assert wp_remote.severity == 'CRITICAL'

    def test_extract_db_ops(self, temp_php_file):
        """Test extraction of database operations"""
        extractor = InventoryExtractor()
        inventory = extractor.extract(temp_php_file)

        db_patterns = [p for p in inventory.patterns if p.pattern_type == 'db_op']
        assert len(db_patterns) >= 1
        assert any('$wpdb->get_results' in p.pattern_name for p in db_patterns)

        # Check severity
        assert all(p.severity == 'HIGH' for p in db_patterns)

    def test_extract_hooks(self, temp_php_file):
        """Test extraction of WordPress hooks"""
        extractor = InventoryExtractor()
        inventory = extractor.extract(temp_php_file)

        hook_patterns = [p for p in inventory.patterns if p.pattern_type == 'hook']
        assert len(hook_patterns) >= 1
        assert any(p.pattern_name == 'add_action' for p in hook_patterns)

    def test_extract_js_functions(self, temp_js_file):
        """Test extraction of JS function definitions"""
        extractor = InventoryExtractor()
        inventory = extractor.extract(temp_js_file)

        assert inventory.language == 'javascript'

        func_patterns = [p for p in inventory.patterns if p.pattern_type == 'function_def']
        assert len(func_patterns) >= 1
        assert any(p.pattern_name == 'fetchData' for p in func_patterns)

    def test_extract_js_api_calls(self, temp_js_file):
        """Test extraction of JS API calls"""
        extractor = InventoryExtractor()
        inventory = extractor.extract(temp_js_file)

        api_patterns = [p for p in inventory.patterns if p.pattern_type == 'function_call']
        assert len(api_patterns) >= 2  # fetch + axios

        pattern_names = [p.pattern_name for p in api_patterns]
        assert 'fetch' in pattern_names
        assert 'axios' in pattern_names

        # Check severity
        assert all(p.severity == 'CRITICAL' for p in api_patterns)

    def test_extract_js_error_handling(self, temp_js_file):
        """Test extraction of JS error handling"""
        extractor = InventoryExtractor()
        inventory = extractor.extract(temp_js_file)

        error_patterns = [p for p in inventory.patterns if p.pattern_type == 'error_handling']
        assert len(error_patterns) >= 2  # try + catch

        pattern_names = [p.pattern_name for p in error_patterns]
        assert 'try' in pattern_names
        assert 'catch' in pattern_names

    def test_extract_react_hooks(self, temp_js_file):
        """Test extraction of React hooks"""
        extractor = InventoryExtractor()
        inventory = extractor.extract(temp_js_file)

        hook_patterns = [p for p in inventory.patterns if p.pattern_type == 'hook']
        assert len(hook_patterns) >= 2  # useState + useEffect

        pattern_names = [p.pattern_name for p in hook_patterns]
        assert any('useState' in name for name in pattern_names)
        assert any('useEffect' in name for name in pattern_names)

    def test_nonexistent_file(self):
        """Test handling of nonexistent file"""
        extractor = InventoryExtractor()
        inventory = extractor.extract('/nonexistent/file.php')

        assert inventory.file_path == '/nonexistent/file.php'
        assert inventory.language == 'unknown'
        assert inventory.total_patterns == 0

    def test_unsupported_language(self):
        """Test handling of unsupported file type"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("some text")
            temp_path = f.name

        try:
            extractor = InventoryExtractor()
            inventory = extractor.extract(temp_path)

            assert inventory.language == 'unknown'
            assert inventory.total_patterns == 0
        finally:
            os.unlink(temp_path)


class TestConvenienceFunction:
    """Test convenience function"""

    def test_extract_inventory(self, temp_php_file):
        """Test extract_inventory convenience function"""
        inventory = extract_inventory(temp_php_file)

        assert isinstance(inventory, FileInventory)
        assert inventory.language == 'php'
        assert inventory.total_patterns > 0


class TestCodePattern:
    """Test CodePattern dataclass"""

    def test_code_pattern_creation(self):
        """Test creating CodePattern instance"""
        pattern = CodePattern(
            pattern_type='security_op',
            pattern_name='wp_remote_post',
            context='$response = wp_remote_post($url, $data);',
            line=42,
            severity='CRITICAL',
            file_path='/path/to/file.php',
            language='php'
        )

        assert pattern.pattern_type == 'security_op'
        assert pattern.pattern_name == 'wp_remote_post'
        assert pattern.line == 42
        assert pattern.severity == 'CRITICAL'


class TestFileInventory:
    """Test FileInventory dataclass"""

    def test_add_pattern(self):
        """Test adding patterns to inventory"""
        inventory = FileInventory(file_path='/test.php', language='php')

        pattern1 = CodePattern(
            pattern_type='function_def',
            pattern_name='test_func',
            context='function test_func() {}',
            line=1,
            severity='SUGGEST',
            file_path='/test.php',
            language='php'
        )

        pattern2 = CodePattern(
            pattern_type='security_op',
            pattern_name='wp_remote_post',
            context='wp_remote_post($url)',
            line=5,
            severity='CRITICAL',
            file_path='/test.php',
            language='php'
        )

        inventory.add_pattern(pattern1)
        inventory.add_pattern(pattern2)

        assert inventory.total_patterns == 2
        assert len(inventory.patterns) == 2
        assert inventory.patterns[0] == pattern1
        assert inventory.patterns[1] == pattern2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])