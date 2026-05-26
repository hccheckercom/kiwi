<?php
$ids = [1, 2, 3];
foreach ( $ids as $id ) {
    $product = wz_get_product( $id );
    echo $product['name'];
}
