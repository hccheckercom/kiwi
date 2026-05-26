<?php
/**
 * Cart Functions
 *
 * Cart-related functionality for Kiwi Test Shop theme.
 *
 * @package kiwi-test-g1
 * @generated 2026-05-25T10:36:13.304345
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Get cart data.
 *
 * @return array
 */
function kiwi_test_g1_get_cart() {
	if ( function_exists( 'wz_cart' ) ) {
		return wz_cart();
	}

	return [
		'items' => [],
		'total' => 0,
	];
}

/**
 * Add product to cart.
 *
 * @param int $product_id Product ID.
 * @param int $quantity   Quantity.
 * @return bool
 */
function kiwi_test_g1_cart_add( $product_id, $quantity = 1 ) {
	if ( function_exists( 'wz_cart_add' ) ) {
		return wz_cart_add( $product_id, $quantity );
	}

	return false;
}

/**
 * AJAX handler: Add to cart.
 */
add_action( 'wp_ajax_kiwi_test_g1_add_to_cart', 'kiwi_test_g1_ajax_add_to_cart' );
add_action( 'wp_ajax_nopriv_kiwi_test_g1_add_to_cart', 'kiwi_test_g1_ajax_add_to_cart' );
function kiwi_test_g1_ajax_add_to_cart() {
	if ( ! kiwi_test_g1_verify_nonce( 'kiwi-test-g1_add_to_cart' ) ) {
		wp_send_json_error( [ 'message' => 'Invalid nonce' ] );
	}

	$product_id = isset( $_POST['product_id'] ) ? absint( $_POST['product_id'] ) : 0;
	$quantity = isset( $_POST['quantity'] ) ? absint( $_POST['quantity'] ) : 1;

	if ( ! $product_id ) {
		wp_send_json_error( [ 'message' => 'Invalid product ID' ] );
	}

	$result = kiwi_test_g1_cart_add( $product_id, $quantity );

	if ( $result ) {
		wp_send_json_success( [
			'message' => __( 'Added to cart', 'kiwi-test-g1' ),
			'cart' => kiwi_test_g1_get_cart(),
		] );
	} else {
		wp_send_json_error( [ 'message' => __( 'Failed to add to cart', 'kiwi-test-g1' ) ] );
	}
}
