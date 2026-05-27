#!/usr/bin/env python3
"""
Generate synthetic demo HTML for ML training data collection.
Creates realistic ecommerce demos for different industries.
"""

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List

# Industry-specific design tokens
INDUSTRY_CONFIGS = {
    "fashion": {
        "shop_name": "Bella Fashion",
        "primary_color": "#E91E63",
        "secondary_color": "#9C27B0",
        "font_family": "Playfair Display, serif",
        "hero_title": "Spring Collection 2026",
        "hero_subtitle": "Discover the latest trends in fashion",
        "categories": ["Dresses", "Tops", "Bottoms", "Accessories"],
        "products": [
            {"name": "Floral Maxi Dress", "price": "1,290,000", "image": "dress-1.jpg"},
            {"name": "Silk Blouse", "price": "890,000", "image": "blouse-1.jpg"},
            {"name": "High-Waist Jeans", "price": "1,190,000", "image": "jeans-1.jpg"},
            {"name": "Leather Handbag", "price": "2,490,000", "image": "bag-1.jpg"},
        ]
    },
    "tech": {
        "shop_name": "TechHub Store",
        "primary_color": "#2196F3",
        "secondary_color": "#00BCD4",
        "font_family": "Inter, sans-serif",
        "hero_title": "Latest Tech Gadgets",
        "hero_subtitle": "Innovation at your fingertips",
        "categories": ["Laptops", "Phones", "Accessories", "Audio"],
        "products": [
            {"name": "Gaming Laptop Pro", "price": "25,990,000", "image": "laptop-1.jpg"},
            {"name": "Wireless Earbuds", "price": "3,490,000", "image": "earbuds-1.jpg"},
            {"name": "Smartphone X", "price": "18,990,000", "image": "phone-1.jpg"},
            {"name": "Mechanical Keyboard", "price": "2,990,000", "image": "keyboard-1.jpg"},
        ]
    },
    "food": {
        "shop_name": "Gourmet Delights",
        "primary_color": "#FF5722",
        "secondary_color": "#FFC107",
        "font_family": "Poppins, sans-serif",
        "hero_title": "Fresh & Organic",
        "hero_subtitle": "Farm to table goodness",
        "categories": ["Fruits", "Vegetables", "Dairy", "Bakery"],
        "products": [
            {"name": "Organic Strawberries", "price": "120,000", "image": "strawberry.jpg"},
            {"name": "Fresh Milk", "price": "45,000", "image": "milk.jpg"},
            {"name": "Whole Wheat Bread", "price": "35,000", "image": "bread.jpg"},
            {"name": "Greek Yogurt", "price": "65,000", "image": "yogurt.jpg"},
        ]
    },
    "furniture": {
        "shop_name": "Modern Living",
        "primary_color": "#795548",
        "secondary_color": "#FF9800",
        "font_family": "Lora, serif",
        "hero_title": "Transform Your Space",
        "hero_subtitle": "Quality furniture for modern homes",
        "categories": ["Living Room", "Bedroom", "Office", "Outdoor"],
        "products": [
            {"name": "Velvet Sofa", "price": "12,900,000", "image": "sofa-1.jpg"},
            {"name": "Oak Dining Table", "price": "8,500,000", "image": "table-1.jpg"},
            {"name": "Ergonomic Chair", "price": "3,200,000", "image": "chair-1.jpg"},
            {"name": "King Bed Frame", "price": "9,800,000", "image": "bed-1.jpg"},
        ]
    },
    "beauty": {
        "shop_name": "Glow Beauty",
        "primary_color": "#E91E63",
        "secondary_color": "#F06292",
        "font_family": "Montserrat, sans-serif",
        "hero_title": "Radiant Skin Starts Here",
        "hero_subtitle": "Premium skincare & cosmetics",
        "categories": ["Skincare", "Makeup", "Haircare", "Fragrance"],
        "products": [
            {"name": "Vitamin C Serum", "price": "890,000", "image": "serum-1.jpg"},
            {"name": "Matte Lipstick", "price": "320,000", "image": "lipstick-1.jpg"},
            {"name": "Hydrating Mask", "price": "450,000", "image": "mask-1.jpg"},
            {"name": "Perfume Set", "price": "1,290,000", "image": "perfume-1.jpg"},
        ]
    },
    "pharma": {
        "shop_name": "HealthCare Plus",
        "primary_color": "#4CAF50",
        "secondary_color": "#8BC34A",
        "font_family": "Roboto, sans-serif",
        "hero_title": "Your Health, Our Priority",
        "hero_subtitle": "Trusted medicines & supplements",
        "categories": ["Vitamins", "Pain Relief", "First Aid", "Supplements"],
        "products": [
            {"name": "Multivitamin Pack", "price": "450,000", "image": "vitamin-1.jpg"},
            {"name": "Pain Relief Gel", "price": "120,000", "image": "gel-1.jpg"},
            {"name": "First Aid Kit", "price": "280,000", "image": "firstaid-1.jpg"},
            {"name": "Omega-3 Capsules", "price": "520,000", "image": "omega3-1.jpg"},
        ]
    },
    "pet": {
        "shop_name": "Pet Paradise",
        "primary_color": "#FF9800",
        "secondary_color": "#FFC107",
        "font_family": "Nunito, sans-serif",
        "hero_title": "Everything for Your Pet",
        "hero_subtitle": "Quality products for happy pets",
        "categories": ["Dog Food", "Cat Food", "Toys", "Accessories"],
        "products": [
            {"name": "Premium Dog Food", "price": "890,000", "image": "dogfood-1.jpg"},
            {"name": "Cat Scratching Post", "price": "450,000", "image": "scratcher-1.jpg"},
            {"name": "Pet Carrier", "price": "680,000", "image": "carrier-1.jpg"},
            {"name": "Chew Toys Set", "price": "220,000", "image": "toys-1.jpg"},
        ]
    },
    "sports": {
        "shop_name": "Active Gear",
        "primary_color": "#F44336",
        "secondary_color": "#FF5722",
        "font_family": "Oswald, sans-serif",
        "hero_title": "Gear Up for Victory",
        "hero_subtitle": "Professional sports equipment",
        "categories": ["Running", "Gym", "Outdoor", "Team Sports"],
        "products": [
            {"name": "Running Shoes Pro", "price": "2,490,000", "image": "shoes-1.jpg"},
            {"name": "Yoga Mat Premium", "price": "890,000", "image": "yogamat-1.jpg"},
            {"name": "Dumbbell Set", "price": "1,890,000", "image": "dumbbell-1.jpg"},
            {"name": "Sports Backpack", "price": "1,290,000", "image": "backpack-1.jpg"},
        ]
    },
    "books": {
        "shop_name": "Book Haven",
        "primary_color": "#3F51B5",
        "secondary_color": "#5C6BC0",
        "font_family": "Merriweather, serif",
        "hero_title": "Discover Your Next Read",
        "hero_subtitle": "Curated collection of bestsellers",
        "categories": ["Fiction", "Non-Fiction", "Children", "Academic"],
        "products": [
            {"name": "The Great Novel", "price": "320,000", "image": "book-1.jpg"},
            {"name": "Business Strategy", "price": "450,000", "image": "book-2.jpg"},
            {"name": "Kids Adventure", "price": "180,000", "image": "book-3.jpg"},
            {"name": "Science Textbook", "price": "680,000", "image": "book-4.jpg"},
        ]
    },
    "jewelry": {
        "shop_name": "Luxe Jewelry",
        "primary_color": "#9C27B0",
        "secondary_color": "#BA68C8",
        "font_family": "Cormorant Garamond, serif",
        "hero_title": "Timeless Elegance",
        "hero_subtitle": "Handcrafted fine jewelry",
        "categories": ["Rings", "Necklaces", "Earrings", "Bracelets"],
        "products": [
            {"name": "Diamond Ring", "price": "45,000,000", "image": "ring-1.jpg"},
            {"name": "Gold Necklace", "price": "28,000,000", "image": "necklace-1.jpg"},
            {"name": "Pearl Earrings", "price": "12,000,000", "image": "earrings-1.jpg"},
            {"name": "Silver Bracelet", "price": "8,500,000", "image": "bracelet-1.jpg"},
        ]
    }
}


def generate_html(config: Dict) -> str:
    """Generate synthetic demo HTML from config."""

    # Build category HTML
    categories_html = "\n".join([
        f'<a href="#" class="px-6 py-3 bg-white rounded-lg shadow hover:shadow-md transition">{cat}</a>'
        for cat in config["categories"]
    ])

    # Build product grid HTML
    products_html = "\n".join([
        f'''
        <div class="bg-white rounded-lg shadow-md overflow-hidden hover:shadow-xl transition">
            <div class="aspect-square bg-gray-200 flex items-center justify-center">
                <span class="text-gray-400">{prod["image"]}</span>
            </div>
            <div class="p-4">
                <h3 class="font-semibold text-lg mb-2">{prod["name"]}</h3>
                <p class="text-xl font-bold" style="color: {config['primary_color']}">{prod["price"]}đ</p>
                <button class="mt-3 w-full py-2 rounded-lg text-white font-medium" style="background: {config['primary_color']}">
                    Add to Cart
                </button>
            </div>
        </div>
        '''
        for prod in config["products"]
    ])

    html = f'''<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{config["shop_name"]} - Homepage</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {{
            font-family: {config["font_family"]};
        }}
    </style>
</head>
<body class="bg-gray-50">
    <!-- Header -->
    <header class="bg-white shadow-sm sticky top-0 z-50">
        <div class="container mx-auto px-4 py-4 flex items-center justify-between">
            <h1 class="text-2xl font-bold" style="color: {config['primary_color']}">{config["shop_name"]}</h1>
            <nav class="hidden md:flex gap-6">
                <a href="#" class="hover:opacity-80">Home</a>
                <a href="#" class="hover:opacity-80">Shop</a>
                <a href="#" class="hover:opacity-80">About</a>
                <a href="#" class="hover:opacity-80">Contact</a>
            </nav>
            <div class="flex gap-4">
                <button class="hover:opacity-80">🔍</button>
                <button class="hover:opacity-80">🛒</button>
                <button class="hover:opacity-80">👤</button>
            </div>
        </div>
    </header>

    <!-- Hero -->
    <section class="py-20 text-center text-white" style="background: linear-gradient(135deg, {config['primary_color']}, {config['secondary_color']})">
        <div class="container mx-auto px-4">
            <h2 class="text-5xl font-bold mb-4">{config["hero_title"]}</h2>
            <p class="text-xl mb-8">{config["hero_subtitle"]}</p>
            <button class="px-8 py-3 bg-white rounded-lg font-semibold hover:shadow-lg transition" style="color: {config['primary_color']}">
                Shop Now
            </button>
        </div>
    </section>

    <!-- Categories -->
    <section class="py-12 bg-white">
        <div class="container mx-auto px-4">
            <h2 class="text-3xl font-bold text-center mb-8">Shop by Category</h2>
            <div class="flex flex-wrap justify-center gap-4">
                {categories_html}
            </div>
        </div>
    </section>

    <!-- Products -->
    <section class="py-12">
        <div class="container mx-auto px-4">
            <h2 class="text-3xl font-bold text-center mb-8">Featured Products</h2>
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                {products_html}
            </div>
        </div>
    </section>

    <!-- Footer -->
    <footer class="bg-gray-900 text-white py-12">
        <div class="container mx-auto px-4 grid grid-cols-1 md:grid-cols-3 gap-8">
            <div>
                <h3 class="text-xl font-bold mb-4">{config["shop_name"]}</h3>
                <p class="text-gray-400">Your trusted online store</p>
            </div>
            <div>
                <h4 class="font-semibold mb-4">Quick Links</h4>
                <ul class="space-y-2 text-gray-400">
                    <li><a href="#" class="hover:text-white">About Us</a></li>
                    <li><a href="#" class="hover:text-white">Contact</a></li>
                    <li><a href="#" class="hover:text-white">Privacy Policy</a></li>
                </ul>
            </div>
            <div>
                <h4 class="font-semibold mb-4">Follow Us</h4>
                <div class="flex gap-4">
                    <a href="#" class="hover:opacity-80">FB</a>
                    <a href="#" class="hover:opacity-80">IG</a>
                    <a href="#" class="hover:opacity-80">TW</a>
                </div>
            </div>
        </div>
    </footer>
</body>
</html>'''

    return html


def generate_design_md(config: Dict) -> str:
    """Generate DESIGN.md from config."""

    return f'''# Design Specification: {config["shop_name"]}

## Brand Identity
- **Shop Name:** {config["shop_name"]}
- **Industry:** Ecommerce
- **Target Audience:** Online shoppers

## Color Palette
- **Primary:** {config["primary_color"]}
- **Secondary:** {config["secondary_color"]}

## Typography
- **Font Family:** {config["font_family"]}
- **Headings:** Bold, large sizes
- **Body:** Regular weight

## Layout Structure
1. **Header:** Logo + Navigation + Icons (sticky)
2. **Hero:** Full-width banner with CTA
3. **Categories:** Horizontal scrollable cards
4. **Products:** 4-column grid (responsive)
5. **Footer:** 3-column layout with links

## Components
- Product cards with image, title, price, CTA
- Category buttons with hover effects
- Responsive navigation (mobile hamburger)
- Search, cart, account icons

## Responsive Breakpoints
- Mobile: < 640px (1 column)
- Tablet: 640px - 1024px (2 columns)
- Desktop: > 1024px (4 columns)
'''


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic demo HTML")
    parser.add_argument("--industry", required=True, choices=list(INDUSTRY_CONFIGS.keys()),
                        help="Industry type")
    parser.add_argument("--output", required=True, help="Output directory path")

    args = parser.parse_args()

    # Get config
    config = INDUSTRY_CONFIGS[args.industry]

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate files
    html_content = generate_html(config)
    design_content = generate_design_md(config)

    # Write files
    (output_dir / "code.html").write_text(html_content, encoding="utf-8")
    (output_dir / "DESIGN.md").write_text(design_content, encoding="utf-8")

    # Create placeholder screenshot
    (output_dir / "screen.png").write_text("", encoding="utf-8")

    print(f"Generated synthetic demo: {args.output}")
    print(f"   - code.html ({len(html_content)} bytes)")
    print(f"   - DESIGN.md ({len(design_content)} bytes)")
    print(f"   - screen.png (placeholder)")
    print(f"\nNext: Run generator on this demo")
    print(f"  cd .claude/kiwi/generator")
    print(f"  python demo_orchestrator.py --demo {args.output} --theme test-{args.industry} --mode foundation")


if __name__ == "__main__":
    main()
