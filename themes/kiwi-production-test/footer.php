	</main><!-- #primary -->

	<footer id="colophon" class="site-footer bg-surface-dim border-t border-outline mt-16">
		<div class="container-wz py-12">
			<div class="grid grid-cols-1 md:grid-cols-4 gap-8">
				<!-- About -->
				<div>
					<h3 class="text-lg font-bold mb-4"><?php echo esc_html( kiwi_production_test_config( 'name' ) ); ?></h3>
					<p class="text-sm text-on-surface-variant">
						<?php echo esc_html( kiwi_production_test_config( 'tagline' ) ); ?>
					</p>
				</div>

				<!-- Quick Links -->
				<div>
					<h3 class="text-lg font-bold mb-4"><?php esc_html_e( 'Quick Links', 'kiwi-production-test' ); ?></h3>
					<?php
					wp_nav_menu( [
						'theme_location' => 'footer',
						'menu_class'     => 'space-y-2 text-sm',
						'container'      => false,
					] );
					?>
				</div>

				<!-- Contact -->
				<div>
					<h3 class="text-lg font-bold mb-4"><?php esc_html_e( 'Contact', 'kiwi-production-test' ); ?></h3>
					<ul class="space-y-2 text-sm text-on-surface-variant">
						<?php if ( kiwi_production_test_config( 'phone' ) ) : ?>
							<li>
								<a href="tel:<?php echo esc_attr( kiwi_production_test_config( 'phone' ) ); ?>">
									<?php echo esc_html( kiwi_production_test_config( 'phone' ) ); ?>
								</a>
							</li>
						<?php endif; ?>
						<?php if ( kiwi_production_test_config( 'email' ) ) : ?>
							<li>
								<a href="mailto:<?php echo esc_attr( kiwi_production_test_config( 'email' ) ); ?>">
									<?php echo esc_html( kiwi_production_test_config( 'email' ) ); ?>
								</a>
							</li>
						<?php endif; ?>
					</ul>
				</div>

				<!-- Social -->
				<div>
					<h3 class="text-lg font-bold mb-4"><?php esc_html_e( 'Follow Us', 'kiwi-production-test' ); ?></h3>
					<div class="flex gap-4">
						<?php if ( kiwi_production_test_config( 'social.facebook_url' ) ) : ?>
							<a href="<?php echo esc_url( kiwi_production_test_config( 'social.facebook_url' ) ); ?>" target="_blank" rel="noopener">
								Facebook
							</a>
						<?php endif; ?>
						<?php if ( kiwi_production_test_config( 'social.zalo_url' ) ) : ?>
							<a href="<?php echo esc_url( kiwi_production_test_config( 'social.zalo_url' ) ); ?>" target="_blank" rel="noopener">
								Zalo
							</a>
						<?php endif; ?>
					</div>
				</div>
			</div>

			<!-- Copyright -->
			<div class="border-t border-outline mt-8 pt-8 text-center text-sm text-on-surface-variant">
				<p><?php echo esc_html( kiwi_production_test_config( 'footer.copyright' ) ); ?></p>
				<p class="mt-2"><?php echo esc_html( kiwi_production_test_config( 'footer.powered_by' ) ); ?></p>
			</div>
		</div>
	</footer>

	<!-- Mobile Bottom Navigation -->
	<?php if ( wp_is_mobile() ) : ?>
		<nav class="fixed bottom-0 left-0 right-0 bg-surface border-t border-outline z-fixed md:hidden">
			<div class="flex justify-around py-2">
				<a href="<?php echo esc_url( home_url( '/' ) ); ?>" class="flex flex-col items-center text-xs">
					<span class="material-symbols-outlined">home</span>
					<span><?php esc_html_e( 'Home', 'kiwi-production-test' ); ?></span>
				</a>
				<a href="<?php echo esc_url( home_url( '/shop' ) ); ?>" class="flex flex-col items-center text-xs">
					<span class="material-symbols-outlined">storefront</span>
					<span><?php esc_html_e( 'Shop', 'kiwi-production-test' ); ?></span>
				</a>
				<a href="<?php echo esc_url( home_url( '/cart' ) ); ?>" class="flex flex-col items-center text-xs">
					<span class="material-symbols-outlined">shopping_cart</span>
					<span><?php esc_html_e( 'Cart', 'kiwi-production-test' ); ?></span>
				</a>
				<a href="<?php echo esc_url( home_url( '/account' ) ); ?>" class="flex flex-col items-center text-xs">
					<span class="material-symbols-outlined">account_circle</span>
					<span><?php esc_html_e( 'Account', 'kiwi-production-test' ); ?></span>
				</a>
			</div>
		</nav>
	<?php endif; ?>

</div><!-- #page -->

<?php wp_footer(); ?>

</body>
</html>
