<?php
/**
 * Cart Functions
 *
 * Cart-related functionality for Kiwi Shop Demo theme.
 *
 * @package kiwi-with-mock-data
 * @generated 2026-05-25T11:09:38.218337
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Get cart data.
 *
 * @return array
 */
function kiwi_with_mock_data_get_cart() {
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
function kiwi_with_mock_data_cart_add( $product_id, $quantity = 1 ) {
	if ( function_exists( 'wz_cart_add' ) ) {
		return wz_cart_add( $product_id, $quantity );
	}

	return false;
}

/**
 * AJAX handler: Add to cart.
 */
add_action( 'wp_ajax_kiwi_with_mock_data_add_to_cart', 'kiwi_with_mock_data_ajax_add_to_cart' );
add_action( 'wp_ajax_nopriv_kiwi_with_mock_data_add_to_cart', 'kiwi_with_mock_data_ajax_add_to_cart' );
function kiwi_with_mock_data_ajax_add_to_cart() {
	if ( ! kiwi_with_mock_data_verify_nonce( 'kiwi-with-mock-data_add_to_cart' ) ) {
		wp_send_json_error( [ 'message' => 'Invalid nonce' ] );
	}

	$product_id = isset( $_POST['product_id'] ) ? absint( $_POST['product_id'] ) : 0;
	$quantity = isset( $_POST['quantity'] ) ? absint( $_POST['quantity'] ) : 1;

	if ( ! $product_id ) {
		wp_send_json_error( [ 'message' => 'Invalid product ID' ] );
	}

	$result = kiwi_with_mock_data_cart_add( $product_id, $quantity );

	if ( $result ) {
		wp_send_json_success( [
			'message' => __( 'Added to cart', 'kiwi-with-mock-data' ),
			'cart' => kiwi_with_mock_data_get_cart(),
		] );
	} else {
		wp_send_json_error( [ 'message' => __( 'Failed to add to cart', 'kiwi-with-mock-data' ) ] );
	}
}
