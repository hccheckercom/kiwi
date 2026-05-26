<?php
// Test file for kiwi_scan_learn
$wpdb->query("SELECT * FROM table WHERE id = " . $_GET['id']);

if (isset($_POST['action'])) {
    process_action();
}

echo $user_input;
