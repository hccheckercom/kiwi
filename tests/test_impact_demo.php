<?php
/**
 * Demo file for testing impact analysis
 */

function calculate_price($base_price, $discount = 0) {
    return $base_price * (1 - $discount / 100);
}

function format_currency($amount) {
    return '$' . number_format($amount, 2);
}

class ProductHelper {
    public function get_total($items) {
        $total = 0;
        foreach ($items as $item) {
            $total += calculate_price($item['price'], $item['discount']);
        }
        return $total;
    }
}