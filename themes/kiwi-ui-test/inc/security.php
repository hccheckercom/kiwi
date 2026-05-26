<?php
/**
 * Security Functions
 *
 * Input sanitization and security helpers for Kiwi UI Test theme.
 *
 * @package kiwi-ui-test
 * @generated 2026-05-25T10:56:27.546652
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Sanitize text input.
 *
 * @param string $input Raw input.
 * @return string
 */
function kiwi_ui_test_sanitize_text( $input ) {
	return sanitize_text_field( $input );
}

/**
 * Sanitize email input.
 *
 * @param string $input Raw input.
 * @return string
 */
function kiwi_ui_test_sanitize_email( $input ) {
	return sanitize_email( $input );
}

/**
 * Verify nonce for AJAX requests.
 *
 * @param string $action Nonce action.
 * @return bool
 */
function kiwi_ui_test_verify_nonce( $action ) {
	$nonce = isset( $_POST['nonce'] ) ? $_POST['nonce'] : '';
	return wp_verify_nonce( $nonce, $action );
}

/**
 * Check if current user can perform action.
 *
 * @param string $capability Required capability.
 * @return bool
 */
function kiwi_ui_test_user_can( $capability ) {
	return current_user_can( $capability );
}
