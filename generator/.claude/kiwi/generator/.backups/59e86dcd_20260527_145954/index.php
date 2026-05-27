<?php get_header(); ?>

<main class="container mx-auto px-4 py-8">
    <?php if (have_posts()) : ?>
        <?php while (have_posts()) : the_post(); ?>
            <article id="post-<?php the_ID(); ?>" <?php post_class('mb-8'); ?>>
                <h2 class="text-3xl font-bold mb-4">
                    <a href="<?php the_permalink(); ?>"><?php the_title(); ?></a>
                </h2>
                <div class="prose max-w-none">
                    <?php the_excerpt(); ?>
                </div>
            </article>
        <?php endwhile; ?>
    <?php else : ?>
        <p><?php _e('No posts found.'); ?></p>
    <?php endif; ?>
</main>

<?php get_footer(); ?>
