<?php
/**
 * Hero Section Template
 *
 * @package kiwi-phase3-test
 */

$title = $args['title'] ?? 'Kiwi Phase3 Test';
$subtitle = $args['subtitle'] ?? '';
$cta_text = $args['cta_text'] ?? 'Mua ngay';
$cta_url = $args['cta_url'] ?? '/shop';
?>

<section class="hero-section relative bg-gradient-to-br from-primary to-secondary text-white py-20 md:py-32">
	<div class="container mx-auto px-4">
		<div class="max-w-3xl mx-auto text-center">
			<h1 class="text-4xl md:text-6xl font-bold mb-6">
				<?php echo esc_html( $title ); ?>
			</h1>

			<?php if ( $subtitle ) : ?>
				<p class="text-xl md:text-2xl mb-8 opacity-90">
					<?php echo esc_html( $subtitle ); ?>
				</p>
			<?php endif; ?>

			<a href="<?php echo esc_url( $cta_url ); ?>"
			   class="inline-block bg-white text-primary px-8 py-4 rounded-lg font-semibold text-lg hover:bg-opacity-90 transition-all">
				<?php echo esc_html( $cta_text ); ?>
			</a>
		</div>
	</div>
</section>
