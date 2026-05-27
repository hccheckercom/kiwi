<?php if (post_password_required()) return; ?>

<div id="comments" class="comments-area mt-8">
    <?php if (have_comments()) : ?>
        <h2 class="text-2xl font-bold mb-4">
            <?php printf(_n('One Comment', '%1$s Comments', get_comments_number()), number_format_i18n(get_comments_number())); ?>
        </h2>

        <ol class="comment-list space-y-4">
            <?php wp_list_comments(['style' => 'ol', 'short_ping' => true]); ?>
        </ol>
    <?php endif; ?>

    <?php comment_form(); ?>
</div>
