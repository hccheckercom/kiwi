<?php
/**
 * Template Name: About
 */

get_header(); ?>

<main class="about-page">
    <?php get_template_part('template-parts/breadcrumb'); ?>

    <div class="container mx-auto px-4 py-16">
        <div class="max-w-4xl mx-auto">
            <h1 class="text-4xl font-bold mb-8 text-center">About Us</h1>

            <div class="prose max-w-none mb-12">
                <?php
                while (have_posts()) : the_post();
                    the_content();
                endwhile;
                ?>
            </div>

            <?php get_template_part('template-parts/trust-badges'); ?>
        </div>
    </div>
</main>

<?php get_footer(); ?>
