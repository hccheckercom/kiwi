<?php
/**
 * Helper Functions
 *
 * Utility functions for Kiwi Generator Test theme.
 *
 * @package kiwi-generator
 * @generated 2026-05-25T09:51:41.890699
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Get theme configuration value.
 *
 * @param string $key     Config key (dot notation supported).
 * @param mixed  $default Default value if key not found.
 * @return mixed
 */
function kiwi_generator_config( $key = '', $default = null ) {
	static $config = null;

	if ( null === $config ) {
		$config_file = KIWI-GENERATOR_DIR . '/store-config.php';
		$config = file_exists( $config_file ) ? require $config_file : [];
	}

	if ( empty( $key ) ) {
		return $config;
	}

	// Support dot notation: 'theme.primary'
	$keys = explode( '.', $key );
	$value = $config;

	foreach ( $keys as $k ) {
		if ( ! isset( $value[ $k ] ) ) {
			return $default;
		}
		$value = $value[ $k ];
	}

	return $value;
}

/**
 * Render component from WeZone ThemeEngine.
 *
 * @param string $name Component name.
 * @param array  $args Component arguments.
 */
function kiwi_generator_component( $name, $args = [] ) {
	if ( function_exists( 'wz_component' ) ) {
		wz_component( $name, $args );
		return;
	}

	// Fallback rendering when plugin not available
	echo '<!-- Component: ' . esc_html( $name ) . ' (plugin not active) -->';
}

/**
 * Format price with currency symbol.
 *
 * @param float $price Price value.
 * @return string
 */
function kiwi_generator_format_price( $price ) {
	if ( function_exists( 'wz_format_price' ) ) {
		return wz_format_price( $price );
	}

	return number_format( $price, 0, ',', '.' ) . 'đ';
}

/**
 * Check if Wezone plugin is active.
 *
 * @param string $plugin Plugin slug.
 * @return bool
 */
function kiwi_generator_is_plugin_active( $plugin ) {
	if ( function_exists( 'wezone_is_active' ) ) {
		return wezone_is_active( $plugin );
	}

	return false;
}
