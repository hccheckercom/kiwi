
// Cart API call without nonce header
fetch('/wp-json/wezone/v1/cart/add', {
    method: 'POST',
    body: JSON.stringify({ product_id: 5, qty: 1 })
});
