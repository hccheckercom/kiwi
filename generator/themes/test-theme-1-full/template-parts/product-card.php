<?php
/**
 * Product Card
 */

$product = get_query_var('product');
if (!$product) return;

$permalink = wz_get_permalink($product);
$thumbnail = $product['thumbnail'] ?? '';
$name = $product['name'] ?? '';
$price = $product['price'] ?? 0;
$sale_price = $product['sale_price'] ?? null;
$on_sale = $product['on_sale'] ?? false;
?>

<article class="product-card bg-white rounded-lg shadow hover:shadow-lg transition">
    <a href="<?php echo esc_url($permalink); ?>" class="block">
        <?php if ($thumbnail) : ?>
            <div class="aspect-square overflow-hidden rounded-t-lg">
                <img src="<?php echo esc_url($thumbnail); ?>"
                     alt="<?php echo esc_attr($name); ?>"
                     class="w-full h-full object-cover hover:scale-105 transition">
            </div>
        <?php endif; ?>

        <div class="p-4">
            <h3 class="font-semibold mb-2 line-clamp-2">
                <?php echo esc_html($name); ?>
            </h3>

            <div class="flex items-center gap-2">
                <?php if ($on_sale && $sale_price) : ?>
                    <span class="text-lg font-bold" style="color: #2c3e50;">
                        <?php echo wz_format_price($sale_price); ?>
                    </span>
                    <span class="text-sm text-gray-500 line-through">
                        <?php echo wz_format_price($price); ?>
                    </span>
                <?php else : ?>
                    <span class="text-lg font-bold" style="color: #2c3e50;">
                        <?php echo wz_format_price($price); ?>
                    </span>
                <?php endif; ?>
            </div>
        </div>
    </a>
</article>
