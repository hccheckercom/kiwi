<?php
/**
 * Theme Setup
 *
 * Theme activation and setup hooks for Kiwi UI Test theme.
 *
 * @package kiwi-ui-test
 * @generated 2026-05-25T10:56:27.730205
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Theme setup.
 */
add_action( 'after_setup_theme', 'kiwi_ui_test_setup' );
function kiwi_ui_test_setup() {
	// Add theme support
	add_theme_support( 'title-tag' );
	add_theme_support( 'post-thumbnails' );
	add_theme_support( 'html5', [ 'search-form', 'comment-form', 'comment-list', 'gallery', 'caption' ] );
	add_theme_support( 'custom-logo' );

	// Register navigation menus
	register_nav_menus( [
		'primary' => __( 'Primary Menu', 'kiwi-ui-test' ),
		'footer'  => __( 'Footer Menu', 'kiwi-ui-test' ),
	] );

	// Set content width
	if ( ! isset( $GLOBALS['content_width'] ) ) {
		$GLOBALS['content_width'] = 1280;
	}
}

/**
 * Register widget areas.
 */
add_action( 'widgets_init', 'kiwi_ui_test_widgets_init' );
function kiwi_ui_test_widgets_init() {
	register_sidebar( [
		'name'          => __( 'Sidebar', 'kiwi-ui-test' ),
		'id'            => 'sidebar-1',
		'description'   => __( 'Add widgets here.', 'kiwi-ui-test' ),
		'before_widget' => '<section id="%1$s" class="widget %2$s">',
		'after_widget'  => '</section>',
		'before_title'  => '<h2 class="widget-title">',
		'after_title'   => '</h2>',
	] );
}
