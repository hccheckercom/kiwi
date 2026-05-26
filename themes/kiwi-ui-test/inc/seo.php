<?php
/**
 * SEO Functions
 *
 * SEO optimization and meta tags for Kiwi UI Test theme.
 *
 * @package kiwi-ui-test
 * @generated 2026-05-25T10:56:27.943099
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Add meta tags to head.
 */
add_action( 'wp_head', 'kiwi_ui_test_meta_tags', 1 );
function kiwi_ui_test_meta_tags() {
	$config = kiwi_ui_test_config();

	// Charset and viewport
	echo '<meta charset="' . esc_attr( get_bloginfo( 'charset' ) ) . '">' . "\n";
	echo '<meta name="viewport" content="width=device-width, initial-scale=1">' . "\n";

	// Description
	if ( is_front_page() && ! empty( $config['seo']['description'] ) ) {
		echo '<meta name="description" content="' . esc_attr( $config['seo']['description'] ) . '">' . "\n";
	}

	// Open Graph
	echo '<meta property="og:site_name" content="' . esc_attr( get_bloginfo( 'name' ) ) . '">' . "\n";
	echo '<meta property="og:type" content="website">' . "\n";
	echo '<meta property="og:url" content="' . esc_url( get_permalink() ) . '">' . "\n";
	echo '<meta property="og:title" content="' . esc_attr( wp_get_document_title() ) . '">' . "\n";

	if ( ! empty( $config['seo']['og_image'] ) ) {
		echo '<meta property="og:image" content="' . esc_url( $config['seo']['og_image'] ) . '">' . "\n";
	}
}

/**
 * Add canonical URL.
 */
add_action( 'wp_head', 'kiwi_ui_test_canonical_url', 2 );
function kiwi_ui_test_canonical_url() {
	if ( is_singular() ) {
		echo '<link rel="canonical" href="' . esc_url( get_permalink() ) . '">' . "\n";
	}
}
