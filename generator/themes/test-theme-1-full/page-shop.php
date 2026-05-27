<?php
/**
 * Template Name: Shop
 */

get_header(); ?>

<main class="shop-page">
    <?php get_template_part('template-parts/breadcrumb'); ?>

    <div class="container mx-auto px-4 py-8">
        <div class="flex flex-col lg:flex-row gap-8">
            <aside class="lg:w-1/4">
                <?php get_template_part('template-parts/filter-bar'); ?>
            </aside>

            <div class="lg:w-3/4">
                <div class="flex justify-between items-center mb-6">
                    <h1 class="text-3xl font-bold">Shop</h1>
                    <select class="border rounded px-4 py-2">
                        <option>Sort by: Latest</option>
                        <option>Price: Low to High</option>
                        <option>Price: High to Low</option>
                        <option>Best Selling</option>
                    </select>
                </div>

                <?php get_template_part('template-parts/product-grid'); ?>
            </div>
        </div>
    </div>
</main>

<?php get_footer(); ?>
