<?php
/**
 * The main template file
 *
 * This is the most generic template file in a WordPress theme
 * and one of the two required files for a theme (the other being style.css).
 * It is used to display a page when nothing more specific matches a query.
 *
 * @package kiwi-phase3-test
 * @generated 2026-05-25T11:01:55.743289
 */

get_header();
?>

<div class="container-wz py-8">
	<?php if ( have_posts() ) : ?>
		<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
			<?php while ( have_posts() ) : the_post(); ?>
				<article id="post-<?php the_ID(); ?>" <?php post_class( 'bg-surface rounded-lg overflow-hidden shadow-sm' ); ?>>
					<?php if ( has_post_thumbnail() ) : ?>
						<div class="aspect-video">
							<?php the_post_thumbnail( 'medium', [ 'class' => 'w-full h-full object-cover' ] ); ?>
						</div>
					<?php endif; ?>

					<div class="p-6">
						<h2 class="text-xl font-bold mb-2">
							<a href="<?php the_permalink(); ?>" class="text-on-surface hover:text-primary">
								<?php the_title(); ?>
							</a>
						</h2>

						<div class="text-sm text-on-surface-variant mb-4">
							<?php echo esc_html( get_the_date() ); ?>
						</div>

						<div class="text-on-surface-variant">
							<?php the_excerpt(); ?>
						</div>

						<a href="<?php the_permalink(); ?>" class="inline-block mt-4 text-primary hover:underline">
							<?php esc_html_e( 'Read more', 'kiwi-phase3-test' ); ?>
						</a>
					</div>
				</article>
			<?php endwhile; ?>
		</div>

		<?php
		the_posts_pagination( [
			'mid_size'  => 2,
			'prev_text' => __( '&laquo; Previous', 'kiwi-phase3-test' ),
			'next_text' => __( 'Next &raquo;', 'kiwi-phase3-test' ),
		] );
		?>

	<?php else : ?>
		<div class="text-center py-12">
			<h1 class="text-2xl font-bold mb-4"><?php esc_html_e( 'Nothing Found', 'kiwi-phase3-test' ); ?></h1>
			<p class="text-on-surface-variant"><?php esc_html_e( 'It seems we can\'t find what you\'re looking for.', 'kiwi-phase3-test' ); ?></p>
		</div>
	<?php endif; ?>
</div>

<?php
get_footer();
