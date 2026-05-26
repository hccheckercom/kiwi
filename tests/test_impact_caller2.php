<?php
/**
 * Another caller file - also uses functions from test_impact_demo.php
 */

require_once __DIR__ . '/test_impact_demo.php';

function checkout_summary($cart_items) {
    $subtotal = 0;
    foreach ($cart_items as $item) {
        $price = calculate_price($item['base'], $item['discount']);
        $subtotal += $price;
        echo $item['name'] . ': ' . format_currency($price) . "\n";
    }
    echo 'Total: ' . format_currency($subtotal);
}