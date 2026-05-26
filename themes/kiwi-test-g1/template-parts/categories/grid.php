<?php
/**
 * Categories Grid Template
 *
 * @package kiwi-test-g1
 */

$categories = $args['categories'] ?? [];
$columns = $args['columns'] ?? 4;
?>

<section class="categories-section py-12">
	<div class="container mx-auto px-4">
		<h2 class="text-3xl font-bold mb-8">Danh mục sản phẩm</h2>
		<div class="grid grid-cols-2 md:grid-cols-<?php echo esc_attr( $columns ); ?> gap-6">
			<?php foreach ( $categories as $category ) : ?>
				<a href="<?php echo esc_url( $category['url'] ?? '#' ); ?>"
				   class="category-card bg-white rounded-lg p-6 text-center hover:shadow-lg transition-shadow">
					<?php if ( ! empty( $category['image'] ) ) : ?>
						<img src="<?php echo esc_url( $category['image'] ); ?>"
						     alt="<?php echo esc_attr( $category['name'] ?? '' ); ?>"
						     class="w-20 h-20 mx-auto mb-4 object-cover rounded-full">
					<?php endif; ?>
					<h3 class="font-semibold text-lg">
						<?php echo esc_html( $category['name'] ?? '' ); ?>
					</h3>
				</a>
			<?php endforeach; ?>
		</div>
	</div>
</section>
