<?php
/**
 * Checkout Progress Steps
 *
 * @package kiwi-production-test
 */

$current_step = $args['current_step'] ?? 1;
?>

<div class="checkout-progress mb-8">
	<div class="flex items-center justify-center">
		<!-- Step 1: Cart -->
		<div class="flex items-center">
			<div class="flex items-center justify-center w-10 h-10 rounded-full <?php echo $current_step >= 1 ? 'bg-primary text-white' : 'bg-gray-200 text-gray-600'; ?>">
				<?php if ( $current_step > 1 ) : ?>
					<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
					</svg>
				<?php else : ?>
					<span class="font-medium">1</span>
				<?php endif; ?>
			</div>
			<span class="ml-2 text-sm font-medium <?php echo $current_step >= 1 ? 'text-gray-900' : 'text-gray-500'; ?>">
				Giỏ hàng
			</span>
		</div>

		<!-- Connector -->
		<div class="w-16 h-1 mx-4 <?php echo $current_step >= 2 ? 'bg-primary' : 'bg-gray-200'; ?>"></div>

		<!-- Step 2: Checkout -->
		<div class="flex items-center">
			<div class="flex items-center justify-center w-10 h-10 rounded-full <?php echo $current_step >= 2 ? 'bg-primary text-white' : 'bg-gray-200 text-gray-600'; ?>">
				<?php if ( $current_step > 2 ) : ?>
					<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
					</svg>
				<?php else : ?>
					<span class="font-medium">2</span>
				<?php endif; ?>
			</div>
			<span class="ml-2 text-sm font-medium <?php echo $current_step >= 2 ? 'text-gray-900' : 'text-gray-500'; ?>">
				Thanh toán
			</span>
		</div>

		<!-- Connector -->
		<div class="w-16 h-1 mx-4 <?php echo $current_step >= 3 ? 'bg-primary' : 'bg-gray-200'; ?>"></div>

		<!-- Step 3: Complete -->
		<div class="flex items-center">
			<div class="flex items-center justify-center w-10 h-10 rounded-full <?php echo $current_step >= 3 ? 'bg-primary text-white' : 'bg-gray-200 text-gray-600'; ?>">
				<?php if ( $current_step > 3 ) : ?>
					<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
					</svg>
				<?php else : ?>
					<span class="font-medium">3</span>
				<?php endif; ?>
			</div>
			<span class="ml-2 text-sm font-medium <?php echo $current_step >= 3 ? 'text-gray-900' : 'text-gray-500'; ?>">
				Hoàn tất
			</span>
		</div>
	</div>
</div>
