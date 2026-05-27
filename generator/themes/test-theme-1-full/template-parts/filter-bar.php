<?php
/**
 * Product Filter Bar
 */

if (!function_exists('wz_get_categories')) {
    return;
}

$categories = wz_get_categories();
$current_category = get_query_var('category_id');
?>

<aside class="filter-bar bg-white rounded-lg shadow p-6">
    <h3 class="text-xl font-bold mb-4">Filters</h3>

    <!-- Categories -->
    <div class="mb-6">
        <h4 class="font-semibold mb-3">Categories</h4>
        <ul class="space-y-2">
            <?php foreach ($categories as $category) : ?>
                <li>
                    <a href="<?php echo esc_url(wz_get_category_link($category)); ?>"
                       class="flex items-center gap-2 hover:underline <?php echo ($current_category == $category['id']) ? 'font-bold' : ''; ?>"
                       style="color: <?php echo ($current_category == $category['id']) ? '#2c3e50' : 'inherit'; ?>;">
                        <span><?php echo esc_html($category['name']); ?></span>
                        <span class="text-sm text-gray-500">(<?php echo $category['count'] ?? 0; ?>)</span>
                    </a>
                </li>
            <?php endforeach; ?>
        </ul>
    </div>

    <!-- Price Range -->
    <div class="mb-6">
        <h4 class="font-semibold mb-3">Price Range</h4>
        <div class="space-y-2">
            <label class="flex items-center gap-2">
                <input type="checkbox" name="price[]" value="0-100000">
                <span>Under 100,000đ</span>
            </label>
            <label class="flex items-center gap-2">
                <input type="checkbox" name="price[]" value="100000-500000">
                <span>100,000đ - 500,000đ</span>
            </label>
            <label class="flex items-center gap-2">
                <input type="checkbox" name="price[]" value="500000-1000000">
                <span>500,000đ - 1,000,000đ</span>
            </label>
            <label class="flex items-center gap-2">
                <input type="checkbox" name="price[]" value="1000000-">
                <span>Over 1,000,000đ</span>
            </label>
        </div>
    </div>

    <!-- Apply Filters Button -->
    <button type="submit"
            class="w-full py-3 text-white font-semibold rounded-lg hover:opacity-90 transition"
            style="background-color: #2c3e50;">
        Apply Filters
    </button>
</aside>
