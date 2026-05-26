<?php
/**
 * Product Archive Template
 *
 * @package kiwi-phase3-complete
 */

get_header();
?>

<main id="main" class="site-main">
	<div class="container mx-auto px-4 py-8">
		<header class="archive-header mb-8">
			<h1 class="text-4xl font-bold">Sản phẩm</h1>
		</header>

		<?php
		// Get products
		if ( function_exists( 'wz_get_products' ) ) {
			$products = wz_get_products( [
				'limit' => 24,
				'page' => get_query_var( 'paged', 1 ),
			] );

			if ( ! empty( $products ) ) {
				echo '<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">';
				foreach ( $products as $product ) {
					if ( function_exists( 'wz_component' ) ) {
						wz_component( 'product-card', [ 'product' => $product ] );
					}
				}
				echo '</div>';

				// Pagination
				if ( function_exists( 'wz_pagination' ) ) {
					wz_pagination();
				}
			} else {
				echo '<p class="text-center text-gray-500">Không có sản phẩm nào.</p>';
			}
		}
		?>
	</div>
</main>

<?php get_footer(); ?>
