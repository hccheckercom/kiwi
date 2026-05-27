<?php
/**
 * Newsletter Signup Section
 */
?>

<section class="newsletter py-16" style="background-color: #2c3e50;">
    <div class="container mx-auto px-4">
        <div class="max-w-2xl mx-auto text-center text-white">
            <h2 class="text-3xl font-bold mb-4">Subscribe to Our Newsletter</h2>
            <p class="mb-8">Get the latest updates on new products and upcoming sales</p>

            <form class="flex flex-col sm:flex-row gap-4 max-w-md mx-auto" method="post" action="<?php echo esc_url(admin_url('admin-post.php')); ?>">
                <input type="hidden" name="action" value="wz_newsletter_subscribe">
                <?php wp_nonce_field('wz_newsletter_subscribe', 'wz_newsletter_nonce'); ?>

                <input type="email"
                       name="email"
                       placeholder="Enter your email"
                       required
                       class="flex-1 px-4 py-3 rounded-lg text-gray-900">

                <button type="submit"
                        class="px-8 py-3 bg-white font-semibold rounded-lg hover:bg-gray-100 transition"
                        style="color: #2c3e50;">
                    Subscribe
                </button>
            </form>
        </div>
    </div>
</section>
