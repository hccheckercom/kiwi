<?php
/**
 * Security Functions
 *
 * Input sanitization and security helpers for Kiwi Shop Demo theme.
 *
 * @package kiwi-with-mock-data
 * @generated 2026-05-25T11:09:37.928493
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
function kiwi_with_mock_data_sanitize_text( $input ) {
	return sanitize_text_field( $input );
}

/**
 * Sanitize email input.
 *
 * @param string $input Raw input.
 * @return string
 */
function kiwi_with_mock_data_sanitize_email( $input ) {
	return sanitize_email( $input );
}

/**
 * Verify nonce for AJAX requests.
 *
 * @param string $action Nonce action.
 * @return bool
 */
function kiwi_with_mock_data_verify_nonce( $action ) {
	$nonce = isset( $_POST['nonce'] ) ? $_POST['nonce'] : '';
	return wp_verify_nonce( $nonce, $action );
}

/**
 * Check if current user can perform action.
 *
 * @param string $capability Required capability.
 * @return bool
 */
function kiwi_with_mock_data_user_can( $capability ) {
	return current_user_can( $capability );
}
