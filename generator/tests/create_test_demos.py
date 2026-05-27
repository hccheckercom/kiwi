"""Create Test Demo for Integration Testing"""

from pathlib import Path
import shutil

def create_test_demo(demo_name: str = "test-demo-1"):
    """Create a test demo folder with realistic HTML."""

    demo_path = Path(f"themes/test-demos/{demo_name}")
    demo_path.mkdir(parents=True, exist_ok=True)

    # Create realistic HTML with multiple components
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test E-commerce Theme</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
    tailwind.config = {
        theme: {
            extend: {
                colors: {
                    primary: '#2563eb',
                    secondary: '#7c3aed',
                    accent: '#f59e0b',
                    success: '#10b981',
                    danger: '#ef4444',
                    dark: '#1f2937',
                    light: '#f3f4f6'
                },
                fontFamily: {
                    sans: ['Inter', 'system-ui', 'sans-serif'],
                    heading: ['Poppins', 'sans-serif']
                },
                fontSize: {
                    'xs': '0.75rem',
                    'sm': '0.875rem',
                    'base': '1rem',
                    'lg': '1.125rem',
                    'xl': '1.25rem',
                    '2xl': '1.5rem',
                    '3xl': '1.875rem',
                    '4xl': '2.25rem',
                    '5xl': '3rem'
                },
                spacing: {
                    'section': '80px',
                    'container': '1200px'
                },
                borderRadius: {
                    'sm': '4px',
                    'md': '8px',
                    'lg': '12px',
                    'xl': '16px'
                }
            }
        }
    };
    </script>
</head>
<body class="font-sans text-dark bg-light">
    <!-- Header -->
    <header class="header bg-white shadow-md sticky top-0 z-50">
        <div class="container mx-auto px-4">
            <nav class="navbar flex items-center justify-between py-4">
                <a href="/" class="logo text-2xl font-heading font-bold text-primary">
                    ShopLogo
                </a>
                <ul class="nav-menu hidden md:flex items-center gap-8">
                    <li><a href="/shop" class="hover:text-primary transition">Shop</a></li>
                    <li><a href="/about" class="hover:text-primary transition">About</a></li>
                    <li><a href="/contact" class="hover:text-primary transition">Contact</a></li>
                </ul>
                <div class="nav-actions flex items-center gap-4">
                    <button class="btn-icon">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
                        </svg>
                    </button>
                    <button class="btn-icon relative">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z"></path>
                        </svg>
                        <span class="badge absolute -top-2 -right-2 bg-danger text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">3</span>
                    </button>
                </div>
            </nav>
        </div>
    </header>

    <!-- Hero Section -->
    <section class="hero bg-gradient-to-r from-primary to-secondary text-white py-20">
        <div class="container mx-auto px-4">
            <div class="grid md:grid-cols-2 gap-12 items-center">
                <div class="hero-content">
                    <h1 class="text-5xl font-heading font-bold mb-6">
                        Summer Collection 2026
                    </h1>
                    <p class="text-xl mb-8 opacity-90">
                        Discover the latest trends in fashion. Up to 50% off on selected items.
                    </p>
                    <div class="flex gap-4">
                        <button class="btn bg-white text-primary px-8 py-3 rounded-lg font-semibold hover:bg-opacity-90 transition">
                            Shop Now
                        </button>
                        <button class="btn border-2 border-white text-white px-8 py-3 rounded-lg font-semibold hover:bg-white hover:text-primary transition">
                            Learn More
                        </button>
                    </div>
                </div>
                <div class="hero-image">
                    <img src="/images/hero-banner.jpg" alt="Summer Collection" class="rounded-xl shadow-2xl">
                </div>
            </div>
        </div>
    </section>

    <!-- Features Section -->
    <section class="features py-16 bg-white">
        <div class="container mx-auto px-4">
            <div class="grid md:grid-cols-3 gap-8">
                <div class="feature-card text-center p-6">
                    <div class="icon w-16 h-16 bg-primary bg-opacity-10 rounded-full flex items-center justify-center mx-auto mb-4">
                        <svg class="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                        </svg>
                    </div>
                    <h3 class="text-xl font-heading font-bold mb-2">Free Shipping</h3>
                    <p class="text-gray-600">On orders over $50</p>
                </div>
                <div class="feature-card text-center p-6">
                    <div class="icon w-16 h-16 bg-secondary bg-opacity-10 rounded-full flex items-center justify-center mx-auto mb-4">
                        <svg class="w-8 h-8 text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                    </div>
                    <h3 class="text-xl font-heading font-bold mb-2">24/7 Support</h3>
                    <p class="text-gray-600">Always here to help</p>
                </div>
                <div class="feature-card text-center p-6">
                    <div class="icon w-16 h-16 bg-accent bg-opacity-10 rounded-full flex items-center justify-center mx-auto mb-4">
                        <svg class="w-8 h-8 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                    </div>
                    <h3 class="text-xl font-heading font-bold mb-2">Secure Payment</h3>
                    <p class="text-gray-600">100% secure transactions</p>
                </div>
            </div>
        </div>
    </section>

    <!-- Product Grid -->
    <section class="products py-16 bg-light">
        <div class="container mx-auto px-4">
            <h2 class="text-4xl font-heading font-bold text-center mb-12">Featured Products</h2>
            <div class="grid md:grid-cols-4 gap-6">
                <!-- Product Card 1 -->
                <div class="product-card bg-white rounded-lg shadow hover:shadow-xl transition">
                    <div class="product-image relative overflow-hidden rounded-t-lg">
                        <img src="/images/product-1.jpg" alt="Product 1" class="w-full h-64 object-cover">
                        <span class="badge absolute top-4 right-4 bg-danger text-white px-3 py-1 rounded-full text-sm font-semibold">-30%</span>
                    </div>
                    <div class="product-info p-4">
                        <h3 class="font-semibold mb-2">Summer Dress</h3>
                        <div class="flex items-center gap-2 mb-2">
                            <span class="text-lg font-bold text-primary">$49.99</span>
                            <span class="text-sm text-gray-500 line-through">$69.99</span>
                        </div>
                        <button class="btn w-full bg-primary text-white py-2 rounded-lg hover:bg-opacity-90 transition">
                            Add to Cart
                        </button>
                    </div>
                </div>
                <!-- Repeat for 3 more products -->
                <div class="product-card bg-white rounded-lg shadow hover:shadow-xl transition">
                    <div class="product-image relative overflow-hidden rounded-t-lg">
                        <img src="/images/product-2.jpg" alt="Product 2" class="w-full h-64 object-cover">
                    </div>
                    <div class="product-info p-4">
                        <h3 class="font-semibold mb-2">Casual Shirt</h3>
                        <div class="flex items-center gap-2 mb-2">
                            <span class="text-lg font-bold text-primary">$39.99</span>
                        </div>
                        <button class="btn w-full bg-primary text-white py-2 rounded-lg hover:bg-opacity-90 transition">
                            Add to Cart
                        </button>
                    </div>
                </div>
                <div class="product-card bg-white rounded-lg shadow hover:shadow-xl transition">
                    <div class="product-image relative overflow-hidden rounded-t-lg">
                        <img src="/images/product-3.jpg" alt="Product 3" class="w-full h-64 object-cover">
                        <span class="badge absolute top-4 right-4 bg-success text-white px-3 py-1 rounded-full text-sm font-semibold">New</span>
                    </div>
                    <div class="product-info p-4">
                        <h3 class="font-semibold mb-2">Denim Jeans</h3>
                        <div class="flex items-center gap-2 mb-2">
                            <span class="text-lg font-bold text-primary">$59.99</span>
                        </div>
                        <button class="btn w-full bg-primary text-white py-2 rounded-lg hover:bg-opacity-90 transition">
                            Add to Cart
                        </button>
                    </div>
                </div>
                <div class="product-card bg-white rounded-lg shadow hover:shadow-xl transition">
                    <div class="product-image relative overflow-hidden rounded-t-lg">
                        <img src="/images/product-4.jpg" alt="Product 4" class="w-full h-64 object-cover">
                    </div>
                    <div class="product-info p-4">
                        <h3 class="font-semibold mb-2">Sneakers</h3>
                        <div class="flex items-center gap-2 mb-2">
                            <span class="text-lg font-bold text-primary">$79.99</span>
                        </div>
                        <button class="btn w-full bg-primary text-white py-2 rounded-lg hover:bg-opacity-90 transition">
                            Add to Cart
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- Footer -->
    <footer class="footer bg-dark text-white py-12">
        <div class="container mx-auto px-4">
            <div class="grid md:grid-cols-4 gap-8 mb-8">
                <div>
                    <h4 class="font-heading font-bold text-xl mb-4">About Us</h4>
                    <p class="text-gray-400">Your trusted online fashion destination since 2020.</p>
                </div>
                <div>
                    <h4 class="font-heading font-bold text-xl mb-4">Quick Links</h4>
                    <ul class="space-y-2 text-gray-400">
                        <li><a href="/shop" class="hover:text-white transition">Shop</a></li>
                        <li><a href="/about" class="hover:text-white transition">About</a></li>
                        <li><a href="/contact" class="hover:text-white transition">Contact</a></li>
                    </ul>
                </div>
                <div>
                    <h4 class="font-heading font-bold text-xl mb-4">Customer Service</h4>
                    <ul class="space-y-2 text-gray-400">
                        <li><a href="/shipping" class="hover:text-white transition">Shipping Info</a></li>
                        <li><a href="/returns" class="hover:text-white transition">Returns</a></li>
                        <li><a href="/faq" class="hover:text-white transition">FAQ</a></li>
                    </ul>
                </div>
                <div>
                    <h4 class="font-heading font-bold text-xl mb-4">Newsletter</h4>
                    <p class="text-gray-400 mb-4">Subscribe for exclusive offers</p>
                    <form class="flex gap-2">
                        <input type="email" placeholder="Your email" class="flex-1 px-4 py-2 rounded-lg text-dark">
                        <button class="btn bg-primary px-6 py-2 rounded-lg hover:bg-opacity-90 transition">
                            Subscribe
                        </button>
                    </form>
                </div>
            </div>
            <div class="border-t border-gray-700 pt-8 text-center text-gray-400">
                <p>&copy; 2026 ShopLogo. All rights reserved.</p>
            </div>
        </div>
    </footer>
</body>
</html>"""

    # Create DESIGN.md
    design_content = """---
colors:
  primary: '#2563eb'
  secondary: '#7c3aed'
  accent: '#f59e0b'
  success: '#10b981'
  danger: '#ef4444'
typography:
  fontFamily: 'Inter, system-ui, sans-serif'
  headingFamily: 'Poppins, sans-serif'
  fontSize:
    base: '16px'
    lg: '18px'
    xl: '20px'
spacing:
  section: '80px'
  container: '1200px'
borderRadius:
  sm: '4px'
  md: '8px'
  lg: '12px'
---

# Test E-commerce Theme

A modern e-commerce theme with clean design and responsive layout.

## Features
- Responsive header with cart badge
- Hero section with CTA buttons
- Feature cards with icons
- Product grid with sale badges
- Newsletter footer

## Target Audience
Fashion e-commerce stores
"""

    (demo_path / "code.html").write_text(html_content, encoding="utf-8")
    (demo_path / "DESIGN.md").write_text(design_content, encoding="utf-8")

    print(f"Created test demo at: {demo_path}")
    return str(demo_path)


if __name__ == "__main__":
    # Create 3 test demos
    for i in range(1, 4):
        create_test_demo(f"test-demo-{i}")

    print("\nTest demos created successfully!")
    print("Run generation with:")
    print("  kiwi_generate_from_demo({demo_path: 'themes/test-demos/test-demo-1', theme_name: 'test-theme-1', mode: 'foundation'})")