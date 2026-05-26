<?php
/**
 * Product Gallery Template
 *
 * @package kiwi-ui-test
 */

$images = $args['images'] ?? [];
$product_name = $args['product_name'] ?? '';
?>

<div class="product-gallery">
	<?php if ( ! empty( $images ) ) : ?>
		<div class="main-image mb-4">
			<img src="<?php echo esc_url( $images[0] ); ?>"
			     alt="<?php echo esc_attr( $product_name ); ?>"
			     class="w-full rounded-lg">
		</div>

		<?php if ( count( $images ) > 1 ) : ?>
			<div class="thumbnail-grid grid grid-cols-4 gap-2">
				<?php foreach ( $images as $image ) : ?>
					<img src="<?php echo esc_url( $image ); ?>"
					     alt="<?php echo esc_attr( $product_name ); ?>"
					     class="w-full aspect-square object-cover rounded cursor-pointer hover:opacity-75">
				<?php endforeach; ?>
			</div>
		<?php endif; ?>
	<?php endif; ?>
</div>
