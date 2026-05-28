"""
Data bindings — canonical mapping from component type to wz_* function calls.

This is the single source of truth for how each component type gets its data.
Used by both the generator (to produce correct PHP) and the validator (to check bindings).
"""

from typing import Dict, Any

# Each entry defines how a component type maps to Wezone Core data sources.
# Keys match ComponentDetector.PATTERNS keys.
COMPONENT_BINDINGS: Dict[str, Dict[str, Any]] = {

    'product-card': {
        'data_source':  'wz_get_products()',
        'loop_var':     '$product',
        'guard':        "if ( ! function_exists( 'wz_get_products' ) ) return;",
        'fields': {
            'image':       '$product[\'thumbnail\']',
            'title':       '$product[\'name\']',
            'price':       '$product[\'price\']',
            'sale_price':  '$product[\'sale_price\']',
            'on_sale':     '$product[\'on_sale\']',
            'permalink':   'wz_get_permalink( $product )',
            'sku':         '$product[\'sku\']',
        },
        'format': {
            'price': 'wz_format_price( {value} )',
        },
    },

    'category-grid': {
        'data_source':  'wz_get_product_categories()',
        'loop_var':     '$category',
        'guard':        "if ( ! function_exists( 'wz_get_product_categories' ) ) return;",
        'fields': {
            'name':      '$category[\'name\']',
            'icon':      '$category[\'icon\']',
            'permalink': 'wz_get_category_link( $category )',
            'count':     '$category[\'count\']',
        },
    },

    'hero': {
        'data_source': 'wz_config()',
        'guard':       "if ( ! function_exists( 'wz_config' ) ) return;",
        'fields': {
            'title':    "wz_config( 'hero.title', get_bloginfo( 'name' ) )",
            'subtitle': "wz_config( 'hero.subtitle', get_bloginfo( 'description' ) )",
            'cta_text': "wz_config( 'hero.cta_text', 'Mua ngay' )",
            'cta_link': "wz_config( 'hero.cta_link', wz_get_shop_url() )",
            'image':    "wz_config( 'hero.image', '' )",
        },
    },

    'trust-badges': {
        'data_source': 'static_array',
        'guard':       None,
        'fields': {
            'icon': '$badge[\'icon\']',
            'text': '$badge[\'text\']',
        },
        'static_default': [
            {'icon': 'local_shipping', 'text': 'Miễn phí vận chuyển'},
            {'icon': 'verified_user',  'text': 'Thanh toán bảo mật'},
            {'icon': 'autorenew',      'text': 'Đổi trả dễ dàng'},
            {'icon': 'star',           'text': 'Chất lượng đảm bảo'},
        ],
    },

    'flash-sale': {
        'data_source':  "get_posts( [ 'post_type' => 'wz_product', 'meta_key' => '_sale_price', 'meta_compare' => '>', 'meta_value' => 0, 'posts_per_page' => 8 ] )",
        'loop_var':     '$product',
        'guard':        "if ( ! function_exists( 'wz_get_products' ) ) return;",
        'fields': {
            'title':      '$product[\'name\']',
            'price':      '$product[\'price\']',
            'sale_price': '$product[\'sale_price\']',
            'permalink':  'wz_get_permalink( $product )',
            'image':      '$product[\'thumbnail\']',
        },
    },

    'breadcrumb': {
        'data_source': 'wz_get_breadcrumb()',
        'loop_var':    '$item',
        'guard':       "if ( ! function_exists( 'wz_get_breadcrumb' ) ) return;",
        'fields': {
            'text': '$item[\'text\']',
            'url':  '$item[\'url\']',
        },
    },

    'cart': {
        'data_source': 'wz_cart()',
        'guard':       "if ( ! function_exists( 'wz_cart' ) ) return;",
        'fields': {
            'items':       '$cart[\'items\']',
            'total':       '$cart[\'total\']',
            'item_count':  'wz_get_cart_count()',
        },
    },

    'account-menu': {
        'data_source': 'static_links',
        'guard':       None,
        'fields': {
            'dashboard':    "home_url( '/account' )",
            'orders':       "home_url( '/account/orders' )",
            'profile':      "home_url( '/account/profile' )",
            'wishlist':     "home_url( '/account/wishlist' )",
            'logout':       "wp_logout_url( home_url() )",
        },
    },

    'footer-links': {
        'data_source': 'wz_config()',
        'guard':       "if ( ! function_exists( 'wz_config' ) ) return;",
        'fields': {
            'phone':        "wz_config( 'phone' )",
            'email':        "wz_config( 'email' )",
            'address':      "wz_config( 'address' )",
            'facebook_url': "wz_config( 'social.facebook_url' )",
            'zalo_url':     "wz_config( 'social.zalo_url' )",
            'copyright':    "wz_config( 'footer.copyright' )",
        },
    },

    'search-bar': {
        'data_source': 'get_search_query()',
        'guard':       None,
        'fields': {
            'query':       'get_search_query()',
            'action':      "home_url( '/' )",
            'placeholder': "'Tìm kiếm sản phẩm...'",
        },
    },

    'product-filters': {
        'data_source':  'wz_get_product_categories()',
        'loop_var':     '$category',
        'guard':        "if ( ! function_exists( 'wz_get_product_categories' ) ) return;",
        'fields': {
            'name':      '$category[\'name\']',
            'permalink': 'wz_get_category_link( $category )',
            'count':     '$category[\'count\']',
            'active':    '$current_category == $category[\'id\']',
        },
    },
}


def get_binding(component_type: str) -> Dict[str, Any]:
    """Return binding for component_type, or empty dict if unknown."""
    return COMPONENT_BINDINGS.get(component_type, {})


def get_guard(component_type: str) -> str:
    """Return PHP guard string for component_type, or empty string."""
    binding = get_binding(component_type)
    return binding.get('guard') or ''


def get_field(component_type: str, field_name: str) -> str:
    """Return PHP expression for a field in a component, or empty string."""
    binding = get_binding(component_type)
    return binding.get('fields', {}).get(field_name, '')


def get_data_source(component_type: str) -> str:
    """Return PHP data source expression for component_type."""
    binding = get_binding(component_type)
    return binding.get('data_source', '')
