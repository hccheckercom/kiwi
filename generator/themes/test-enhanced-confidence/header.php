<!DOCTYPE html>
<html <?php language_attributes(); ?>>
<head>
    <meta charset="<?php bloginfo('charset'); ?>">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <?php wp_head(); ?>
</head>
<body <?php body_class(); ?>>
<?php wp_body_open(); ?>

<header class="site-header bg-white shadow-md" style="border-bottom: 2px solid #2c3e50;">
    <div class="container mx-auto px-4 py-4 flex justify-between items-center">
        <div class="site-branding">
            <a href="<?php echo esc_url(home_url('/')); ?>" class="text-2xl font-bold">
                <?php bloginfo('name'); ?>
            </a>
        </div>
        <nav class="main-navigation">
            <?php
            wp_nav_menu([
                'theme_location' => 'primary',
                'menu_class' => 'flex gap-6',
                'container' => false,
            ]);
            ?>
        </nav>
    </div>
</header>
