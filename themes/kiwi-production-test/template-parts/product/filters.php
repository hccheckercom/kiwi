<?php
/**
 * Product Filters Template
 *
 * @package kiwi-production-test
 */

$categories = $args['categories'] ?? [];
$current_category = $args['current_category'] ?? '';
?>

<div class="product-filters bg-white rounded-lg p-6 mb-6">
	<h3 class="font-semibold text-lg mb-4">Lọc sản phẩm</h3>

	<?php if ( ! empty( $categories ) ) : ?>
		<div class="filter-group mb-6">
			<h4 class="font-medium mb-3">Danh mục</h4>
			<ul class="space-y-2">
				<?php foreach ( $categories as $category ) : ?>
					<li>
						<a href="<?php echo esc_url( $category['url'] ?? '#' ); ?>"
						   class="block py-1 hover:text-primary <?php echo $current_category === $category['slug'] ? 'text-primary font-semibold' : ''; ?>">
							<?php echo esc_html( $category['name'] ?? '' ); ?>
							<span class="text-gray-400 text-sm">(<?php echo intval( $category['count'] ?? 0 ); ?>)</span>
						</a>
					</li>
				<?php endforeach; ?>
			</ul>
		</div>
	<?php endif; ?>
</div>
