<?php
// Test file for Semgrep basic PHP rule

// BAD: wp_mail without wz_config
wp_mail( $email, 'Hardcoded Subject', 'Hardcoded body text' );

// BAD: Another hardcoded example
wp_mail(
    'user@example.com',
    'Order Confirmation',
    'Your order has been received.'
);

// GOOD: Using wz_config
$shop_name = wz_config( 'shop_name', 'Shop' );
wp_mail(
    $email,
    '[' . $shop_name . '] Order Confirmation',
    'Your order has been received.'
);

// BAD: SQL injection
$wpdb->query( "SELECT * FROM users WHERE id = " . $_GET['id'] );

// GOOD: Prepared statement
$wpdb->query( $wpdb->prepare( "SELECT * FROM users WHERE id = %d", $_GET['id'] ) );
