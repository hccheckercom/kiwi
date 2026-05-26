<?php
/**
 * Test file to verify Kiwi learning loop
 * Contains intentional violations to trigger pattern mining
 */

// VIOLATION 1: Missing nonce verification
if (isset($_POST['action'])) {
    process_action();
}

// VIOLATION 2: SQL injection via concatenation
$id = $_GET['id'];
$wpdb->query("SELECT * FROM table WHERE id = " . $id);

// VIOLATION 3: Unescaped output
echo $_POST['user_input'];

// VIOLATION 4: Missing sanitization
$name = $_POST['name'];
update_user_meta($user_id, 'name', $name);

// VIOLATION 5: Hardcoded credentials
define('API_KEY', 'sk_live_abc123def456');

// VIOLATION 6: Missing error handling
$response = wp_remote_get('https://api.example.com');
$data = json_decode($response['body']);