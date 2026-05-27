"""G1 Pages Generator — Generate 11 page templates and template-parts."""

from pathlib import Path
from typing import Dict, Any, List


class G1PagesGenerator:
    """
    Generate G1 Pages files for WordPress theme.

    11 files:
    - page-home.php (homepage template)
    - page-shop.php (shop page template)
    - page-about.php (about page template)
    - template-parts/hero.php (hero section)
    - template-parts/product-grid.php (product grid)
    - template-parts/product-card.php (product card)
    - template-parts/categories.php (category list)
    - template-parts/trust-badges.php (trust badges)
    - template-parts/newsletter.php (newsletter signup)
    - template-parts/breadcrumb.php (breadcrumb)
    - template-parts/filter-bar.php (filter bar)
    """

    def __init__(self, tokens: Dict[str, Any], components: List[Dict[str, Any]]):
        self.tokens = tokens
        self.components = components
        self.primary_color = tokens.get('colors', {}).get('primary', '#000000')
        self.secondary_color = tokens.get('colors', {}).get('secondary', '#666666')

    def generate_all(self, theme_dir: Path) -> List[str]:
        """Generate all G1 Pages files."""
        created_files = []

        # Create template-parts directory
        template_parts_dir = theme_dir / 'template-parts'
        template_parts_dir.mkdir(exist_ok=True)

        # Page templates
        created_files.append(self._generate_page_home(theme_dir))
        created_files.append(self._generate_page_shop(theme_dir))
        created_files.append(self._generate_page_about(theme_dir))

        # Template parts
        created_files.append(self._generate_hero(template_parts_dir))
        created_files.append(self._generate_product_grid(template_parts_dir))
        created_files.append(self._generate_product_card(template_parts_dir))
        created_files.append(self._generate_categories(template_parts_dir))
        created_files.append(self._generate_trust_badges(template_parts_dir))
        created_files.append(self._generate_newsletter(template_parts_dir))
        created_files.append(self._generate_breadcrumb(template_parts_dir))
        created_files.append(self._generate_filter_bar(template_parts_dir))

        return created_files

    def _generate_page_home(self, theme_dir: Path) -> str:
        """Generate page-home.php — homepage template."""
        content = f"""<?php
/**
 * Template Name: Homepage
 */

get_header(); ?>

<main class="homepage">
    <?php get_template_part('template-parts/hero'); ?>

    <?php get_template_part('template-parts/categories'); ?>

    <section class="featured-products py-16">
        <div class="container mx-auto px-4">
            <h2 class="text-3xl font-bold mb-8 text-center">Featured Products</h2>
            <?php get_template_part('template-parts/product-grid'); ?>
        </div>
    </section>

    <?php get_template_part('template-parts/trust-badges'); ?>

    <?php get_template_part('template-parts/newsletter'); ?>
</main>

<?php get_footer(); ?>
"""
        file_path = theme_dir / 'page-home.php'
        file_path.write_text(content, encoding='utf-8')
        return str(file_path)

    def _generate_page_shop(self, theme_dir: Path) -> str:
        """Generate page-shop.php — shop page template."""
        content = f"""<?php
/**
 * Template Name: Shop
 */

get_header(); ?>

<main class="shop-page">
    <?php get_template_part('template-parts/breadcrumb'); ?>

    <div class="container mx-auto px-4 py-8">
        <div class="flex flex-col lg:flex-row gap-8">
            <aside class="lg:w-1/4">
                <?php get_template_part('template-parts/filter-bar'); ?>
            </aside>

            <div class="lg:w-3/4">
                <div class="flex justify-between items-center mb-6">
                    <h1 class="text-3xl font-bold">Shop</h1>
                    <select class="border rounded px-4 py-2">
                        <option>Sort by: Latest</option>
                        <option>Price: Low to High</option>
                        <option>Price: High to Low</option>
                        <option>Best Selling</option>
                    </select>
                </div>

                <?php get_template_part('template-parts/product-grid'); ?>
            </div>
        </div>
    </div>
</main>

<?php get_footer(); ?>
"""
        file_path = theme_dir / 'page-shop.php'
        file_path.write_text(content, encoding='utf-8')
        return str(file_path)

    def _generate_page_about(self, theme_dir: Path) -> str:
        """Generate page-about.php — about page template."""
        content = f"""<?php
/**
 * Template Name: About
 */

get_header(); ?>

<main class="about-page">
    <?php get_template_part('template-parts/breadcrumb'); ?>

    <div class="container mx-auto px-4 py-16">
        <div class="max-w-4xl mx-auto">
            <h1 class="text-4xl font-bold mb-8 text-center">About Us</h1>

            <div class="prose max-w-none mb-12">
                <?php
                while (have_posts()) : the_post();
                    the_content();
                endwhile;
                ?>
            </div>

            <?php get_template_part('template-parts/trust-badges'); ?>
        </div>
    </div>
</main>

<?php get_footer(); ?>
"""
        file_path = theme_dir / 'page-about.php'
        file_path.write_text(content, encoding='utf-8')
        return str(file_path)

    def _generate_hero(self, template_parts_dir: Path) -> str:
        """Generate template-parts/hero.php — hero section."""
        content = f"""<?php
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
            <h1 class="text-4xl lg:text-6xl font-bold mb-6" style="color: {self.primary_color};">
                <?php echo esc_html($hero_title); ?>
            </h1>
            <p class="text-xl lg:text-2xl mb-8 text-gray-700">
                <?php echo esc_html($hero_subtitle); ?>
            </p>
            <a href="<?php echo esc_url($hero_cta_link); ?>"
               class="inline-block px-8 py-4 text-white font-semibold rounded-lg hover:opacity-90 transition"
               style="background-color: {self.primary_color};">
                <?php echo esc_html($hero_cta_text); ?>
            </a>
        </div>
    </div>
</section>
"""
        file_path = template_parts_dir / 'hero.php'
        file_path.write_text(content, encoding='utf-8')
        return str(file_path)

    def _generate_product_grid(self, template_parts_dir: Path) -> str:
        """Generate template-parts/product-grid.php — product grid."""
        content = f"""<?php
/**
 * Product Grid
 */

if (!function_exists('wz_get_products')) {{
    return;
}}

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
"""
        file_path = template_parts_dir / 'product-grid.php'
        file_path.write_text(content, encoding='utf-8')
        return str(file_path)

    def _generate_product_card(self, template_parts_dir: Path) -> str:
        """Generate template-parts/product-card.php — product card."""
        content = f"""<?php
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
                    <span class="text-lg font-bold" style="color: {self.primary_color};">
                        <?php echo wz_format_price($sale_price); ?>
                    </span>
                    <span class="text-sm text-gray-500 line-through">
                        <?php echo wz_format_price($price); ?>
                    </span>
                <?php else : ?>
                    <span class="text-lg font-bold" style="color: {self.primary_color};">
                        <?php echo wz_format_price($price); ?>
                    </span>
                <?php endif; ?>
            </div>
        </div>
    </a>
</article>
"""
        file_path = template_parts_dir / 'product-card.php'
        file_path.write_text(content, encoding='utf-8')
        return str(file_path)

    def _generate_categories(self, template_parts_dir: Path) -> str:
        """Generate template-parts/categories.php — category list."""
        content = f"""<?php
/**
 * Categories Section
 */

if (!function_exists('wz_get_categories')) {{
    return;
}}

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
"""
        file_path = template_parts_dir / 'categories.php'
        file_path.write_text(content, encoding='utf-8')
        return str(file_path)

    def _generate_trust_badges(self, template_parts_dir: Path) -> str:
        """Generate template-parts/trust-badges.php — trust badges."""
        content = f"""<?php
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
"""
        file_path = template_parts_dir / 'trust-badges.php'
        file_path.write_text(content, encoding='utf-8')
        return str(file_path)

    def _generate_newsletter(self, template_parts_dir: Path) -> str:
        """Generate template-parts/newsletter.php — newsletter signup."""
        content = f"""<?php
/**
 * Newsletter Signup Section
 */
?>

<section class="newsletter py-16" style="background-color: {self.primary_color};">
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
                        style="color: {self.primary_color};">
                    Subscribe
                </button>
            </form>
        </div>
    </div>
</section>
"""
        file_path = template_parts_dir / 'newsletter.php'
        file_path.write_text(content, encoding='utf-8')
        return str(file_path)

    def _generate_breadcrumb(self, template_parts_dir: Path) -> str:
        """Generate template-parts/breadcrumb.php — breadcrumb."""
        content = f"""<?php
/**
 * Breadcrumb Navigation
 */

if (!function_exists('wz_get_breadcrumb')) {{
    return;
}}

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
                           style="color: {self.primary_color};">
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
"""
        file_path = template_parts_dir / 'breadcrumb.php'
        file_path.write_text(content, encoding='utf-8')
        return str(file_path)

    def _generate_filter_bar(self, template_parts_dir: Path) -> str:
        """Generate template-parts/filter-bar.php — filter bar."""
        content = f"""<?php
/**
 * Product Filter Bar
 */

if (!function_exists('wz_get_categories')) {{
    return;
}}

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
                       style="color: <?php echo ($current_category == $category['id']) ? '{self.primary_color}' : 'inherit'; ?>;">
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
            style="background-color: {self.primary_color};">
        Apply Filters
    </button>
</aside>
"""
        file_path = template_parts_dir / 'filter-bar.php'
        file_path.write_text(content, encoding='utf-8')
        return str(file_path)