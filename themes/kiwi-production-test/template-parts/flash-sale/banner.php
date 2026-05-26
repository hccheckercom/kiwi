<?php
/**
 * Flash Sale Banner Template
 *
 * @package kiwi-production-test
 */

$products = $args['products'] ?? [];
$title = $args['title'] ?? 'Flash Sale';
?>

<section class="flash-sale-section py-12 bg-red-50">
	<div class="container mx-auto px-4">
		<h2 class="text-3xl font-bold mb-8 text-red-600"><?php echo esc_html( $title ); ?></h2>
		<div class="grid grid-cols-2 md:grid-cols-4 gap-6">
			<?php foreach ( $products as $product ) : ?>
				<?php if ( function_exists( 'wz_component' ) ) : ?>
					<?php wz_component( 'product-card', [ 'product' => $product ] ); ?>
				<?php endif; ?>
			<?php endforeach; ?>
		</div>
	</div>
</section>
