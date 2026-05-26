<?php
global $wpdb;
$rows = [['id' => 1], ['id' => 2]];
foreach ( $rows as $row ) {
    $wpdb->insert("{$wpdb->prefix}analytics", $row);
}
