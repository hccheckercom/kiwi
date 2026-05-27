<?php get_header(); ?>

<main class="container mx-auto px-4 py-8">
    <h1 class="text-4xl font-bold mb-8"><?php the_archive_title(); ?></h1>

    <?php if (have_posts()) : ?>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <?php while (have_posts()) : the_post(); ?>
                <article <?php post_class('bg-white rounded-lg shadow p-6'); ?>>
                    <h2 class="text-2xl font-bold mb-2">
                        <a href="<?php the_permalink(); ?>"><?php the_title(); ?></a>
                    </h2>
                    <?php the_excerpt(); ?>
                </article>
            <?php endwhile; ?>
        </div>
    <?php endif; ?>
</main>

<?php get_footer(); ?>
