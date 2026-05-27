<?php get_header(); ?>

<main class="container mx-auto px-4 py-8">
    <?php while (have_posts()) : the_post(); ?>
        <article id="post-<?php the_ID(); ?>" <?php post_class(); ?>>
            <h1 class="text-4xl font-bold mb-4"><?php the_title(); ?></h1>
            <div class="prose max-w-none">
                <?php the_content(); ?>
            </div>
        </article>
    <?php endwhile; ?>
</main>

<?php get_footer(); ?>
