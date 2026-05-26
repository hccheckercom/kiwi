<?php
/**
 * Cart Functions
 *
 * Cart-related functionality for Kiwi Phase3 Complete theme.
 *
 * @package kiwi-phase3-complete
 * @generated 2026-05-25T11:04:21.274191
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Get cart data.
 *
 * @return array
 */
function kiwi_phase3_complete_get_cart() {
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
function kiwi_phase3_complete_cart_add( $product_id, $quantity = 1 ) {
	if ( function_exists( 'wz_cart_add' ) ) {
		return wz_cart_add( $product_id, $quantity );
	}

	return false;
}

/**
 * AJAX handler: Add to cart.
 */
add_action( 'wp_ajax_kiwi_phase3_complete_add_to_cart', 'kiwi_phase3_complete_ajax_add_to_cart' );
add_action( 'wp_ajax_nopriv_kiwi_phase3_complete_add_to_cart', 'kiwi_phase3_complete_ajax_add_to_cart' );
function kiwi_phase3_complete_ajax_add_to_cart() {
	if ( ! kiwi_phase3_complete_verify_nonce( 'kiwi-phase3-complete_add_to_cart' ) ) {
		wp_send_json_error( [ 'message' => 'Invalid nonce' ] );
	}

	$product_id = isset( $_POST['product_id'] ) ? absint( $_POST['product_id'] ) : 0;
	$quantity = isset( $_POST['quantity'] ) ? absint( $_POST['quantity'] ) : 1;

	if ( ! $product_id ) {
		wp_send_json_error( [ 'message' => 'Invalid product ID' ] );
	}

	$result = kiwi_phase3_complete_cart_add( $product_id, $quantity );

	if ( $result ) {
		wp_send_json_success( [
			'message' => __( 'Added to cart', 'kiwi-phase3-complete' ),
			'cart' => kiwi_phase3_complete_get_cart(),
		] );
	} else {
		wp_send_json_error( [ 'message' => __( 'Failed to add to cart', 'kiwi-phase3-complete' ) ] );
	}
}
