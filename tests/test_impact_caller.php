<?php
/**
 * Demo caller file - uses functions from test_impact_demo.php
 */

require_once __DIR__ . '/test_impact_demo.php';

function display_cart_total($items) {
    $helper = new ProductHelper();
    $total = $helper->get_total($items);
    echo format_currency($total);
}

function apply_discount($price, $discount_percent) {
    $discounted = calculate_price($price, $discount_percent);
    return format_currency($discounted);
}