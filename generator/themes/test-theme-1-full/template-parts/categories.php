<?php
/**
 * Categories Section
 */

if (!function_exists('wz_get_categories')) {
    return;
}

$categories = wz_get_categories(['limit' => 8]);

if (empty($categories)) return;
?>

<section class="categories py-16 bg-gray-50">
    <div class="container mx-auto px-4">
        <h2 class="text-3xl font-bold mb-8 text-center">Shop by Category</h2>

        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4">
            <?php foreach ($categories as $category) : ?>
                <a href="<?php echo esc_url(wz_get_category_link($category)); ?>"
                   class="category-item text-center p-4 bg-white rounded-lg hover:shadow-md transition">
                    <?php if (!empty($category['icon'])) : ?>
                        <div class="text-4xl mb-2"><?php echo $category['icon']; ?></div>
                    <?php endif; ?>
                    <span class="text-sm font-medium"><?php echo esc_html($category['name']); ?></span>
                </a>
            <?php endforeach; ?>
        </div>
    </div>
</section>
