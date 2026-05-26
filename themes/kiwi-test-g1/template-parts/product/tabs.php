<?php
/**
 * Product Tabs Template
 *
 * @package kiwi-test-g1
 */

$description = $args['description'] ?? '';
$specifications = $args['specifications'] ?? [];
?>

<div class="product-tabs mt-8">
	<div class="tab-buttons flex border-b mb-6">
		<button class="tab-button active px-6 py-3 font-semibold border-b-2 border-primary">
			Mô tả
		</button>
		<?php if ( ! empty( $specifications ) ) : ?>
			<button class="tab-button px-6 py-3 font-semibold">
				Thông số
			</button>
		<?php endif; ?>
	</div>

	<div class="tab-content">
		<div class="tab-pane active">
			<?php echo wp_kses_post( $description ); ?>
		</div>

		<?php if ( ! empty( $specifications ) ) : ?>
			<div class="tab-pane hidden">
				<table class="w-full">
					<?php foreach ( $specifications as $key => $value ) : ?>
						<tr class="border-b">
							<td class="py-3 font-semibold w-1/3"><?php echo esc_html( $key ); ?></td>
							<td class="py-3"><?php echo esc_html( $value ); ?></td>
						</tr>
					<?php endforeach; ?>
				</table>
			</div>
		<?php endif; ?>
	</div>
</div>
