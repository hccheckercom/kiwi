<?php get_header(); ?>

<main class="container mx-auto px-4 py-16 text-center">
    <h1 class="text-6xl font-bold mb-4">404</h1>
    <p class="text-2xl mb-8"><?php _e('Page Not Found'); ?></p>
    <a href="<?php echo esc_url(home_url('/')); ?>" class="btn bg-primary text-white px-8 py-3 rounded-lg">
        <?php _e('Go Home'); ?>
    </a>
</main>

<?php get_footer(); ?>
