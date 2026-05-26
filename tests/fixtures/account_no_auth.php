<?php
// Account orders page - MISSING auth check
$orders = wz_get_user_orders( get_current_user_id() );
foreach ( $orders as $order ) {
    echo esc_html( $order['id'] );
}
