<?php
/**
 * Hero Section
 */

$hero_title = wz_config('hero.title') ?: get_bloginfo('name');
$hero_subtitle = wz_config('hero.subtitle') ?: get_bloginfo('description');
$hero_cta_text = wz_config('hero.cta_text') ?: 'Shop Now';
$hero_cta_link = wz_config('hero.cta_link') ?: home_url('/shop');
?>

<section class="hero relative bg-gradient-to-r from-gray-100 to-gray-200 py-20 lg:py-32">
    <div class="container mx-auto px-4">
        <div class="max-w-3xl">
            <h1 class="text-4xl lg:text-6xl font-bold mb-6" style="color: #2c3e50;">
                <?php echo esc_html($hero_title); ?>
            </h1>
            <p class="text-xl lg:text-2xl mb-8 text-gray-700">
                <?php echo esc_html($hero_subtitle); ?>
            </p>
            <a href="<?php echo esc_url($hero_cta_link); ?>"
               class="inline-block px-8 py-4 text-white font-semibold rounded-lg hover:opacity-90 transition"
               style="background-color: #2c3e50;">
                <?php echo esc_html($hero_cta_text); ?>
            </a>
        </div>
    </div>
</section>
