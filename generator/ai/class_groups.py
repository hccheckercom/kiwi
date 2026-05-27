"""Class Grouping — Map 43 specific classes to 12 broad categories for ML training"""

# Mapping from specific component types to broad categories
CLASS_GROUPS = {
    # CARD category (any card-like component with icon/title/description)
    'card': [
        'account', 'product-card', 'review-list', 'wallet-balance',
        'loyalty-points', 'notification-list', 'empty-state'
    ],

    # FORM category (forms and form sections)
    'form': [
        'checkout', 'address-form', 'shipping-form', 'payment-methods',
        'contact-form', 'review-form', 'order-tracking'
    ],

    # LIST category (grids and lists of items)
    'list': [
        'product-grid', 'wishlist-grid', 'search-results', 'brand-grid',
        'blog-grid', 'compare-table', 'order-summary', 'cart-summary'
    ],

    # NAVIGATION category (navigation elements)
    'navigation': [
        'header', 'footer', 'breadcrumb', 'sidebar', 'filter-bar'
    ],

    # HERO category (hero sections and banners)
    'hero': [
        'hero', 'landing-hero', 'flash-sale', 'flash-sale-countdown'
    ],

    # INTERACTIVE category (interactive widgets)
    'interactive': [
        'coupon-widget', 'faq-accordion', 'search-filters'
    ],

    # CONTENT category (content pages)
    'content': [
        'blog-post', 'policy-content', 'error-page', 'maintenance-page'
    ],

    # MEDIA category (media components)
    'media': [
        'product-detail', 'categories', 'trust-badges'
    ],

    # LAYOUT category (layout containers)
    'layout': [
        'search'
    ],

    # WIDGET category (small widgets)
    'widget': [
        'wp-plugin'
    ],

    # PAGE category (full page templates)
    'page': [],

    # MISC category (uncategorized)
    'misc': []
}

# Reverse mapping: specific type -> broad category
SPECIFIC_TO_BROAD = {}
for broad, specifics in CLASS_GROUPS.items():
    for specific in specifics:
        SPECIFIC_TO_BROAD[specific] = broad


def group_labels(labels: list) -> list:
    """Convert specific labels to broad categories."""
    return [SPECIFIC_TO_BROAD.get(label, 'misc') for label in labels]


def get_broad_category(specific_type: str) -> str:
    """Get broad category for a specific component type."""
    return SPECIFIC_TO_BROAD.get(specific_type, 'misc')


# Heuristic refinement rules: broad -> specific
REFINEMENT_RULES = {
    'card': [
        # If has form inputs -> checkout/address-form
        {'pattern': 'has_form_inputs', 'result': 'checkout'},
        # If has wallet/money keywords -> wallet-balance
        {'pattern': 'has_wallet_keywords', 'result': 'wallet-balance'},
        # If has star rating -> review-list
        {'pattern': 'has_star_rating', 'result': 'review-list'},
        # Default: product-card
        {'pattern': 'default', 'result': 'product-card'}
    ],
    'form': [
        # If has shipping keywords -> shipping-form
        {'pattern': 'has_shipping_keywords', 'result': 'shipping-form'},
        # If has payment keywords -> payment-methods
        {'pattern': 'has_payment_keywords', 'result': 'payment-methods'},
        # Default: checkout
        {'pattern': 'default', 'result': 'checkout'}
    ],
    'list': [
        # If has product classes -> product-grid
        {'pattern': 'has_product_classes', 'result': 'product-grid'},
        # If has wishlist keywords -> wishlist-grid
        {'pattern': 'has_wishlist_keywords', 'result': 'wishlist-grid'},
        # Default: product-grid
        {'pattern': 'default', 'result': 'product-grid'}
    ],
    'navigation': [
        # If at top -> header
        {'pattern': 'position_top', 'result': 'header'},
        # If at bottom -> footer
        {'pattern': 'position_bottom', 'result': 'footer'},
        # If has breadcrumb separator -> breadcrumb
        {'pattern': 'has_breadcrumb_separator', 'result': 'breadcrumb'},
        # Default: header
        {'pattern': 'default', 'result': 'header'}
    ],
    'hero': [
        # If has countdown -> flash-sale
        {'pattern': 'has_countdown', 'result': 'flash-sale'},
        # Default: hero
        {'pattern': 'default', 'result': 'hero'}
    ]
}


def refine_prediction(broad_category: str, component: dict) -> str:
    """
    Refine broad category to specific type using heuristic rules.

    Args:
        broad_category: Broad category from ML classifier
        component: Component dict with html, classes, text

    Returns:
        Specific component type
    """
    if broad_category not in REFINEMENT_RULES:
        return broad_category

    rules = REFINEMENT_RULES[broad_category]

    for rule in rules:
        pattern = rule['pattern']

        if pattern == 'default':
            return rule['result']

        # Check pattern
        if _matches_pattern(pattern, component):
            return rule['result']

    # Fallback to broad category
    return broad_category


def _matches_pattern(pattern: str, component: dict) -> bool:
    """Check if component matches a refinement pattern."""
    html = component.get('html', '').lower()
    text = component.get('text', '').lower()
    classes = ' '.join(component.get('classes', [])).lower()

    if pattern == 'has_form_inputs':
        return 'input' in html or 'form' in html

    elif pattern == 'has_wallet_keywords':
        return 'wallet' in text or 'balance' in text or 'point' in text

    elif pattern == 'has_star_rating':
        return 'star' in classes or 'rating' in text

    elif pattern == 'has_shipping_keywords':
        return 'shipping' in text or 'delivery' in text or 'address' in text

    elif pattern == 'has_payment_keywords':
        return 'payment' in text or 'card' in text or 'bank' in text

    elif pattern == 'has_product_classes':
        return 'product' in classes or 'wz-product' in classes

    elif pattern == 'has_wishlist_keywords':
        return 'wishlist' in text or 'favorite' in text

    elif pattern == 'position_top':
        return component.get('location', {}).get('depth', 10) < 3

    elif pattern == 'position_bottom':
        return 'footer' in classes

    elif pattern == 'has_breadcrumb_separator':
        return '/' in text or '>' in text or '›' in text

    elif pattern == 'has_countdown':
        return 'countdown' in classes or 'timer' in text

    return False