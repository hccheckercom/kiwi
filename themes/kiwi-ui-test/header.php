<!DOCTYPE html>
<html <?php language_attributes(); ?>>
<head>
	<meta charset="<?php bloginfo( 'charset' ); ?>">
	<meta name="viewport" content="width=device-width, initial-scale=1">
	<?php wp_head(); ?>
</head>

<body <?php body_class(); ?>>
<?php wp_body_open(); ?>

<div id="page" class="site">
	<header id="masthead" class="site-header bg-surface border-b border-outline sticky top-0 z-sticky">
		<div class="container-wz">
			<div class="flex items-center justify-between h-16">
				<!-- Logo -->
				<div class="site-branding">
					<?php if ( has_custom_logo() ) : ?>
						<?php the_custom_logo(); ?>
					<?php else : ?>
						<a href="<?php echo esc_url( home_url( '/' ) ); ?>" class="text-xl font-bold text-on-surface">
							<?php bloginfo( 'name' ); ?>
						</a>
					<?php endif; ?>
				</div>

				<!-- Primary Navigation -->
				<nav id="site-navigation" class="main-navigation hidden md:block">
					<?php
					wp_nav_menu( [
						'theme_location' => 'primary',
						'menu_class'     => 'flex gap-6',
						'container'      => false,
					] );
					?>
				</nav>

				<!-- Cart & Account -->
				<div class="flex items-center gap-4">
					<?php if ( function_exists( 'wz_cart' ) ) : ?>
						<a href="<?php echo esc_url( home_url( '/cart' ) ); ?>" class="relative">
							<span class="material-symbols-outlined">shopping_cart</span>
							<?php
							$cart = wz_cart();
							if ( ! empty( $cart['items'] ) ) :
								$count = array_sum( array_column( $cart['items'], 'quantity' ) );
								?>
								<span class="absolute -top-2 -right-2 bg-primary text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
									<?php echo esc_html( $count ); ?>
								</span>
							<?php endif; ?>
						</a>
					<?php endif; ?>

					<?php if ( is_user_logged_in() ) : ?>
						<a href="<?php echo esc_url( home_url( '/account' ) ); ?>" class="text-on-surface">
							<span class="material-symbols-outlined">account_circle</span>
						</a>
					<?php else : ?>
						<a href="<?php echo esc_url( home_url( '/login' ) ); ?>" class="text-on-surface">
							<?php esc_html_e( 'Login', 'kiwi-ui-test' ); ?>
						</a>
					<?php endif; ?>

					<!-- Mobile menu toggle -->
					<button id="mobile-menu-toggle" class="md:hidden">
						<span class="material-symbols-outlined">menu</span>
					</button>
				</div>
			</div>
		</div>
	</header>

	<main id="primary" class="site-main">
