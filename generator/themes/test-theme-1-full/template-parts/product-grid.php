<?php
/**
 * Product Grid
 */

if (!function_exists('wz_get_products')) {
    return;
}

$products = wz_get_products(['limit' => 12]);

if (empty($products)) : ?>
    <p class="text-center text-gray-500">No products found.</p>
<?php return; endif; ?>

<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
    <?php foreach ($products as $product) : ?>
        <?php
        set_query_var('product', $product);
        get_template_part('template-parts/product-card');
        ?>
    <?php endforeach; ?>
</div>
