<?php
/**
 * Template Name: Homepage
 */

get_header(); ?>

<main class="homepage">
    <?php get_template_part('template-parts/hero'); ?>

    <?php get_template_part('template-parts/categories'); ?>

    <section class="featured-products py-16">
        <div class="container mx-auto px-4">
            <h2 class="text-3xl font-bold mb-8 text-center">Featured Products</h2>
            <?php get_template_part('template-parts/product-grid'); ?>
        </div>
    </section>

    <?php get_template_part('template-parts/trust-badges'); ?>

    <?php get_template_part('template-parts/newsletter'); ?>
</main>

<?php get_footer(); ?>
