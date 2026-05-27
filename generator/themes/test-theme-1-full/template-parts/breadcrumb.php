<?php
/**
 * Breadcrumb Navigation
 */

if (!function_exists('wz_get_breadcrumb')) {
    return;
}

$breadcrumb = wz_get_breadcrumb();

if (empty($breadcrumb)) return;
?>

<nav class="breadcrumb bg-gray-50 py-4">
    <div class="container mx-auto px-4">
        <ol class="flex items-center gap-2 text-sm">
            <?php foreach ($breadcrumb as $index => $item) : ?>
                <?php if ($index > 0) : ?>
                    <li class="text-gray-400">/</li>
                <?php endif; ?>

                <li>
                    <?php if (!empty($item['url'])) : ?>
                        <a href="<?php echo esc_url($item['url']); ?>"
                           class="hover:underline"
                           style="color: #2c3e50;">
                            <?php echo esc_html($item['text']); ?>
                        </a>
                    <?php else : ?>
                        <span class="text-gray-600"><?php echo esc_html($item['text']); ?></span>
                    <?php endif; ?>
                </li>
            <?php endforeach; ?>
        </ol>
    </div>
</nav>
