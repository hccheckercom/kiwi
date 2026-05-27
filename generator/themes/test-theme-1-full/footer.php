
<footer class="site-footer bg-gray-900 text-white py-12 mt-16">
    <div class="container mx-auto px-4">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div>
                <h3 class="text-xl font-bold mb-4"><?php bloginfo('name'); ?></h3>
                <p><?php bloginfo('description'); ?></p>
            </div>
            <div>
                <h3 class="text-xl font-bold mb-4"><?php _e('Quick Links'); ?></h3>
                <?php
                wp_nav_menu([
                    'theme_location' => 'footer',
                    'menu_class' => 'space-y-2',
                    'container' => false,
                ]);
                ?>
            </div>
            <div>
                <h3 class="text-xl font-bold mb-4"><?php _e('Contact'); ?></h3>
                <p>&copy; <?php echo date('Y'); ?> <?php bloginfo('name'); ?></p>
            </div>
        </div>
    </div>
</footer>

<?php wp_footer(); ?>
</body>
</html>
