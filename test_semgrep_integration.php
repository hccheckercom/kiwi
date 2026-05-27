<?php
// Test file for Semgrep integration

// Should trigger wp_mail without nonce check
function send_email() {
    wp_mail('test@example.com', 'Subject', 'Body');
}

// Should trigger SQL injection
function get_user($id) {
    global $wpdb;
    $query = "SELECT * FROM users WHERE id = $id";
    return $wpdb->get_row($query);
}

// Should trigger XSS
function display_name($name) {
    echo "<div>Hello " . $_GET['name'] . "</div>";
}
