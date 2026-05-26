<?php
/**
 * Demo file for testing proactive coverage system
 */

class DemoPlugin {
    public function send_notification($user_id, $message) {
        // API call without error handling - should be detected as gap
        $response = wp_remote_post('https://api.example.com/notify', [
            'body' => json_encode(['user' => $user_id, 'msg' => $message])
        ]);

        return $response;
    }

    public function get_user_data($id) {
        global $wpdb;

        // Unprepared SQL query - should be detected as gap
        $query = "SELECT * FROM users WHERE id = $id";
        return $wpdb->get_results($query);
    }

    public function handle_ajax_request() {
        // Direct superglobal access without sanitization - should be detected as gap
        $value = $_POST['value'];
        $user_id = $_GET['user_id'];

        echo $value;

        wp_send_json_success(['user' => $user_id]);
    }

    public function process_data($data) {
        // Some processing
        add_action('init', [$this, 'init_hook']);

        return $data;
    }
}

function custom_function() {
    // Hook registration
    add_filter('the_content', 'modify_content');
}