<?php
/**
 * Product Detail Template
 *
 * @package kiwi-ui-test
 */

get_header();

// Get product ID from URL
$product_id = get_query_var( 'product_id' );

if ( function_exists( 'wz_get_product' ) ) {
	$product = wz_get_product( $product_id );

	if ( $product ) {
		?>
		<main id="main" class="site-main">
			<div class="container mx-auto px-4 py-8">
				<div class="grid grid-cols-1 md:grid-cols-2 gap-8">
					<!-- Product Gallery -->
					<div class="product-gallery">
						<?php if ( ! empty( $product['images'] ) ) : ?>
							<img src="<?php echo esc_url( $product['images'][0] ); ?>"
							     alt="<?php echo esc_attr( $product['name'] ); ?>"
							     class="w-full rounded-lg">
						<?php endif; ?>
					</div>

					<!-- Product Info -->
					<div class="product-info">
						<h1 class="text-3xl font-bold mb-4"><?php echo esc_html( $product['name'] ); ?></h1>

						<div class="price mb-6">
							<span class="text-3xl font-bold text-primary">
								<?php echo esc_html( number_format( $product['price'], 0, ',', '.' ) ); ?>đ
							</span>
						</div>

						<div class="description mb-6">
							<?php echo wp_kses_post( $product['description'] ?? '' ); ?>
						</div>

						<!-- Add to Cart -->
						<?php if ( function_exists( 'wz_component' ) ) : ?>
							<?php wz_component( 'add-to-cart', [ 'product' => $product ] ); ?>
						<?php endif; ?>
					</div>
				</div>

				<!-- Related Products -->
				<?php
				if ( function_exists( 'wz_get_related_products' ) ) {
					$related = wz_get_related_products( $product_id, [ 'limit' => 4 ] );
					if ( ! empty( $related ) ) {
						echo '<section class="related-products mt-12">';
						echo '<h2 class="text-2xl font-bold mb-6">Sản phẩm liên quan</h2>';
						echo '<div class="grid grid-cols-2 md:grid-cols-4 gap-6">';
						foreach ( $related as $rel_product ) {
							if ( function_exists( 'wz_component' ) ) {
								wz_component( 'product-card', [ 'product' => $rel_product ] );
							}
						}
						echo '</div>';
						echo '</section>';
					}
				}
				?>
			</div>
		</main>
		<?php
	} else {
		echo '<main class="site-main"><div class="container mx-auto px-4 py-8"><p>Sản phẩm không tồn tại.</p></div></main>';
	}
}

get_footer();
?>
