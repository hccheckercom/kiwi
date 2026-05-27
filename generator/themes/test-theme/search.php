<?php get_header(); ?>

<main class="container mx-auto px-4 py-8">
    <h1 class="text-4xl font-bold mb-8">
        <?php printf(__('Search Results for: %s'), get_search_query()); ?>
    </h1>

    <?php if (have_posts()) : ?>
        <?php while (have_posts()) : the_post(); ?>
            <article <?php post_class('mb-8'); ?>>
                <h2 class="text-2xl font-bold mb-2">
                    <a href="<?php the_permalink(); ?>"><?php the_title(); ?></a>
                </h2>
                <?php the_excerpt(); ?>
            </article>
        <?php endwhile; ?>
    <?php else : ?>
        <p><?php _e('No results found.'); ?></p>
    <?php endif; ?>
</main>

<?php get_footer(); ?>
