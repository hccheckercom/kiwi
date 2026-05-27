<?php
/**
 * Trust Badges Section
 */

$badges = wz_config('trust_badges') ?: [
    ['icon' => '🚚', 'text' => 'Free Shipping'],
    ['icon' => '🔒', 'text' => 'Secure Payment'],
    ['icon' => '↩️', 'text' => 'Easy Returns'],
    ['icon' => '⭐', 'text' => 'Quality Guaranteed'],
];
?>

<section class="trust-badges py-12 bg-white">
    <div class="container mx-auto px-4">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-6">
            <?php foreach ($badges as $badge) : ?>
                <div class="text-center">
                    <div class="text-4xl mb-2"><?php echo $badge['icon']; ?></div>
                    <p class="font-medium"><?php echo esc_html($badge['text']); ?></p>
                </div>
            <?php endforeach; ?>
        </div>
    </div>
</section>
