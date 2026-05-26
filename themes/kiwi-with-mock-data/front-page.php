<!DOCTYPE html>
<html <?php language_attributes(); ?>>
<head>
	<meta charset="<?php bloginfo( 'charset' ); ?>">
	<meta name="viewport" content="width=device-width, initial-scale=1">
	<?php wp_head(); ?>
</head>

<body <?php body_class(); ?>>
<?php wp_body_open(); ?>

<?php get_header(); ?>

<main id="main" class="site-main">
	<?php
	// Hero section
	if ( function_exists( 'wz_component' ) ) {
		wz_component( 'hero', [
			'title' => 'Kiwi Shop Demo',
			'subtitle' => '',
			'cta_text' => 'Mua ngay',
			'cta_url' => '/shop',
		] );
	}

	// Categories section
	if ( function_exists( 'wz_get_product_categories' ) ) {
		$categories = wz_get_product_categories( [ 'limit' => 8 ] );
		if ( ! empty( $categories ) ) {
			echo '<section class="categories-section py-12">';
			echo '<div class="container mx-auto px-4">';
			echo '<h2 class="text-3xl font-bold mb-8">Danh mục sản phẩm</h2>';
			echo '<div class="grid grid-cols-2 md:grid-cols-4 gap-6">';
			foreach ( $categories as $category ) {
				wz_component( 'category-card', [ 'category' => $category ] );
			}
			echo '</div>';
			echo '</div>';
			echo '</section>';
		}
	}

	// Flash sale section
	if ( function_exists( 'wz_get_flash_sale_products' ) ) {
		$flash_products = wz_get_flash_sale_products( [ 'limit' => 8 ] );
		if ( ! empty( $flash_products ) ) {
			echo '<section class="flash-sale-section py-12 bg-red-50">';
			echo '<div class="container mx-auto px-4">';
			echo '<h2 class="text-3xl font-bold mb-8 text-red-600">Flash Sale</h2>';
			echo '<div class="grid grid-cols-2 md:grid-cols-4 gap-6">';
			foreach ( $flash_products as $product ) {
				wz_component( 'product-card', [ 'product' => $product ] );
			}
			echo '</div>';
			echo '</div>';
			echo '</section>';
		}
	}

	// Featured products
	if ( function_exists( 'wz_get_products' ) ) {
		$products = wz_get_products( [ 'featured' => true, 'limit' => 8 ] );
		if ( ! empty( $products ) ) {
			echo '<section class="featured-products py-12">';
			echo '<div class="container mx-auto px-4">';
			echo '<h2 class="text-3xl font-bold mb-8">Sản phẩm nổi bật</h2>';
			echo '<div class="grid grid-cols-2 md:grid-cols-4 gap-6">';
			foreach ( $products as $product ) {
				wz_component( 'product-card', [ 'product' => $product ] );
			}
			echo '</div>';
			echo '</div>';
			echo '</section>';
		}
	}
	?>
</main>

<?php get_footer(); ?>

</body>
</html>
