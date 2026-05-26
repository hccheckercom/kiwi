<?php
/**
 * Theme Setup
 *
 * Theme activation and setup hooks for Kiwi Phase3 Complete theme.
 *
 * @package kiwi-phase3-complete
 * @generated 2026-05-25T11:04:20.930345
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Theme setup.
 */
add_action( 'after_setup_theme', 'kiwi_phase3_complete_setup' );
function kiwi_phase3_complete_setup() {
	// Add theme support
	add_theme_support( 'title-tag' );
	add_theme_support( 'post-thumbnails' );
	add_theme_support( 'html5', [ 'search-form', 'comment-form', 'comment-list', 'gallery', 'caption' ] );
	add_theme_support( 'custom-logo' );

	// Register navigation menus
	register_nav_menus( [
		'primary' => __( 'Primary Menu', 'kiwi-phase3-complete' ),
		'footer'  => __( 'Footer Menu', 'kiwi-phase3-complete' ),
	] );

	// Set content width
	if ( ! isset( $GLOBALS['content_width'] ) ) {
		$GLOBALS['content_width'] = 1280;
	}
}

/**
 * Register widget areas.
 */
add_action( 'widgets_init', 'kiwi_phase3_complete_widgets_init' );
function kiwi_phase3_complete_widgets_init() {
	register_sidebar( [
		'name'          => __( 'Sidebar', 'kiwi-phase3-complete' ),
		'id'            => 'sidebar-1',
		'description'   => __( 'Add widgets here.', 'kiwi-phase3-complete' ),
		'before_widget' => '<section id="%1$s" class="widget %2$s">',
		'after_widget'  => '</section>',
		'before_title'  => '<h2 class="widget-title">',
		'after_title'   => '</h2>',
	] );
}
