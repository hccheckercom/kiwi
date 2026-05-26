<?php
/**
 * Product Card Template
 *
 * @package kiwi-production-test
 */

$product = $args['product'] ?? null;
if ( ! $product ) {
	return;
}
?>

<div class="product-card bg-white rounded-lg shadow-sm hover:shadow-md transition-shadow overflow-hidden">
	<a href="<?php echo esc_url( $product['url'] ?? '#' ); ?>" class="block">
		<?php if ( ! empty( $product['images'][0] ) ) : ?>
			<div class="product-image aspect-square overflow-hidden">
				<img src="<?php echo esc_url( $product['images'][0] ); ?>"
				     alt="<?php echo esc_attr( $product['name'] ?? '' ); ?>"
				     class="w-full h-full object-cover hover:scale-105 transition-transform">
			</div>
		<?php endif; ?>

		<div class="p-4">
			<h3 class="font-semibold text-lg mb-2 line-clamp-2">
				<?php echo esc_html( $product['name'] ?? '' ); ?>
			</h3>

			<div class="price">
				<?php if ( ! empty( $product['sale_price'] ) ) : ?>
					<span class="text-gray-400 line-through text-sm mr-2">
						<?php echo esc_html( number_format( $product['regular_price'], 0, ',', '.' ) ); ?>đ
					</span>
					<span class="text-primary font-bold text-xl">
						<?php echo esc_html( number_format( $product['sale_price'], 0, ',', '.' ) ); ?>đ
					</span>
				<?php else : ?>
					<span class="text-primary font-bold text-xl">
						<?php echo esc_html( number_format( $product['price'], 0, ',', '.' ) ); ?>đ
					</span>
				<?php endif; ?>
			</div>
		</div>
	</a>
</div>
