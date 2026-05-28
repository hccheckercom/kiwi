# Kiwi — Bug/Lesson Index

> Auto-generated. Do NOT edit manually. Run `python tools/rebuild_index.py`.

**Total: 598** | CRITICAL: 146 | HIGH: 356 | INFO: 18 | MEDIUM: 3 | SUGGEST: 75

## accessibility

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-674 | CRIT | `<button[^>]*(?:className)[^>]*>(?:\s*<(?...` | Interactive element missing accessible name |
| LES-678 | CRIT | `className="[^"]*(?:text-red|text-green|b...` | Color-only state indication without text/icon alternative |
| LES-679 | CRIT | `focus-visible:|focus:` | Interactive elements missing focus-visible styles |
| LES-675 | HIGH | `<(?:img|Image)\b[^>]*(?<!alt="[^"]*")[^>...` | Image missing alt attribute |
| LES-676 | HIGH | `<input[^>]*(?:type="(?:text|email|passwo...` | Form input without associated label |
| LES-677 | HIGH | `<div[^>]*onClick[^>]*(?<!role="button")(...` | Click handler on non-interactive element without keyboard su |
| LES-680 | HIGH | `<main|role="main"` | Page missing landmark roles (main/nav/header/footer) |
| LES-681 | HIGH | `<h[3-6]` | Heading hierarchy skip (h1 followed by h3, no h2) |
| LES-682 | HIGH | `<(div|span)[^>]*onClick(?![^>]*role=)` | Click handlers on div/span without role='button' and tabInde |
| LES-683 | HIGH | `text-red-[4-7]00|text-green-[4-7]00|bg-r...` | Color-only state indication (no icon/aria for errors) |
| LES-685 | HIGH | `skip.*content|skip.*main|#main-content|s...` | WP template missing skip-nav link |
| LES-686 | HIGH | `<input[^>]*type="(text|email|tel|passwor...` | WP form inputs missing associated labels (for= attribute) |
| LES-684 | SUGG | `skip.*content|skip.*main|#main-content` | Skip-to-content link missing at page top |

## ads-compliance

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-217 | CRIT | `(?:trong|within|in)\s*(?:24h|24 giờ|24 h...` | Absolute time guarantee without conditions — Google Ads misr |
| LES-218 | CRIT | `(?:trọn đời|lifetime|vĩnh viễn|mãi mãi|f...` | Lifetime/indefinite service promise — unrealistic guarantee |
| LES-219 | CRIT | `(?:4\.[5-9]|5\.0)\s*★|★\s*(?:4\.[5-9]|5\...` | Unverified rating/review displayed without source — misrepre |
| LES-220 | CRIT | `(?:line-through|lineThrough|text-decorat...` | Inflated strikethrough pricing without basis — deceptive pri |
| LES-233 | CRIT | `(?:href="[^"]*(?:#TODO|#placeholder|java...` | Broken links or 404 pages on ad landing path — destination r |
| LES-611 | CRIT | `(?:cookie.?consent|gdpr.?banner|consent....` | Missing cookie consent banner — GDPR/CCPA violation, Google  |
| LES-221 | HIGH | `(?:tăng|increase|boost|cao hơn|higher)\s...` | Unsubstantiated performance claim — conversion/traffic/ranki |
| LES-222 | HIGH | `(?:Google Analytics|GA4|gtag|Meta Pixel|...` | Missing Privacy Policy disclosure for tracking pixels — GA4/ |
| LES-223 | HIGH | `(?:MST|mã số thuế|tax.?id|ĐKKD|đăng ký k...` | Missing business identity — no tax ID, registration number,  |
| LES-224 | HIGH | `(?:chi phí duy trì|recurring|hàng năm|pe...` | Hidden recurring costs — hosting/domain/maintenance not disc |
| LES-225 | HIGH | `(?:100%|số 1|#1|tốt nhất|best|hàng đầu|l...` | Absolute superlative without qualification — '100%', 'số 1', |
| LES-226 | HIGH | `(?:tránh.*(?:suspend|ban|từ chối|reject)...` | Implying control over third-party platform decisions — Googl |
| LES-227 | HIGH | `(?:hoàn tiền|refund|đổi trả|cancellation...` | Missing refund/cancellation policy — required for paid servi |
| LES-228 | HIGH | `(?:cookie.*consent|consent.*cookie|Cooki...` | Missing cookie consent mechanism — GDPR/tracking compliance |
| LES-229 | HIGH | `(?:thời gian lưu trữ|retention|lưu trữ.*...` | Missing data retention period in privacy policy — GDPR requi |
| LES-231 | HIGH | `(?:overflow-x:\s*hidden|position:\s*fixe...` | Landing page not mobile-optimized — Google Ads quality score |
| LES-232 | HIGH | `(?:<img[^>]*(?!.*(?:width|height|sizes|l...` | Poor Core Web Vitals on landing page — LCP/CLS/INP affecting |
| LES-234 | HIGH | `(?:tag.*(?:bạn bè|friend)|share.*(?:để|t...` | Engagement bait tactics — Meta policy violation for clickbai |
| LES-235 | HIGH | `(?:WooCommerce|Shopify|WordPress\.com|Ha...` | Trademark/copyright infringement in content — using brand na |
| LES-236 | HIGH | `(?:exit.?intent|ExitIntent|onbeforeunloa...` | Intrusive interstitial or popup blocking content — Google la |
| LES-294 | HIGH | `window\.dataLayer` | Missing dataLayer initialization — GA4/GTM events will not f |
| LES-295 | HIGH | `view_item` | Missing view_item event — product page visits not tracked in |
| LES-296 | HIGH | `['"]add_to_cart['"]` | Missing add_to_cart event tracking — cart interactions invis |
| LES-297 | HIGH | `fbq\(` | Missing Facebook Pixel implementation — Meta Ads cannot trac |
| LES-298 | HIGH | `sessionStorage|localStorage|wz_order_tra...` | Missing purchase event dedup — thank-you page reload causes  |
| LES-299 | HIGH | `cookie.?consent|consent.?cookie|wz_conse...` | Missing cookie consent UI — tracking fires without user cons |

## ai-safety

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-194 | CRIT | `\$\{.*(?:input|query|message|content|tex...` | User input passed directly to AI prompt — prompt injection v |
| LES-195 | CRIT | `max_tokens|maxTokens|token.*limit|cost.*...` | AI API call without cost control — unbounded spend on user a |
| LES-200 | CRIT | `moderate|moderation|filter|nsfw|safe.*se...` | AI image generation without content moderation — inappropria |
| LES-196 | HIGH | `anthropic\.messages\.create|generateCont...` | AI API call without timeout — request hangs indefinitely |
| LES-197 | HIGH | `fallback|retry|catch.*try|backup.*provid...` | AI provider failure without fallback — feature completely br |
| LES-198 | HIGH | `JSON\.parse\(.*(?:content|text|response)...` | AI response used without validation — malformed output break |
| LES-199 | HIGH | `(?:password|secret|token|api_key|credit_...` | Sensitive data sent to AI API — PII/secrets in prompts |

## code-quality

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-650 | SUGG | `print\(f?["\x27](DEBUG|ERROR|WARN)` | print() for Debugging — Use logging Module |
| LES-658 | SUGG | `^\s{4,}(import|from)\s+` | Nested Import Inside Function Body |
| LES-664 | SUGG | `from \w+ import \*` | Wildcard Import — Namespace Pollution |

## component-pattern

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-687 | HIGH | `loading|skeleton|spinner|Skeleton|Loadin...` | Loading state missing — content jumps on data fetch |
| LES-688 | HIGH | `error|Error|isError|ErrorBoundary|error\...` | Error state missing — failed fetch shows blank or crashes |
| LES-689 | HIGH | `empty|Empty|no.*found|không.*có|length\s...` | Empty state missing — zero items shows blank area |
| LES-693 | HIGH | `(?:w-[3-6] h-[3-6]|size=['"]?(?:1[2-9]|2...` | Mixed icon sizes in same toolbar/nav (w-4 h-4 vs w-5 h-5) |
| LES-695 | SUGG | `shadow-lg|shadow-xl|shadow-2xl` | Mixed shadow scales in same page section |

## concurrency

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-184 | CRIT | `idempotency|idempotent|processed_webhook...` | Payment webhook handler not idempotent — double charge on re |
| LES-185 | CRIT | `stock.*-=|quantity.*-=|inventory.*-.*1|u...` | Inventory update without atomic check — overselling on concu |
| LES-186 | CRIT | `usage_count.*\+.*1|used_count.*\+.*1|inc...` | Coupon usage increment not atomic — coupon used beyond limit |
| LES-190 | CRIT | `update.*status.*(?:paid|shipped|delivere...` | Order status transition without optimistic locking — lost up |
| LES-193 | CRIT | `supabase\.from\(['"]orders['"]\)\.insert...` | Database transaction missing for multi-table checkout operat |
| LES-187 | HIGH | `new Date\(\)|Date\.now\(\)|getTime\(\).*...` | Flash sale time check in application code — clock skew bypas |
| LES-188 | HIGH | `disabled|submitting|isSubmitting|isPendi...` | Concurrent form submission — double order creation |
| LES-189 | HIGH | `supabase\.channel\(|subscribe\(|on\('pos...` | Supabase realtime subscription not cleaned up — memory leak |
| LES-191 | HIGH | `lock|mutex|advisory|pg_try_advisory|last...` | Cron job not idempotent — duplicate processing on overlappin |
| LES-192 | HIGH | `cart.*update|updateCart|set.*cart|cart.*...` | Cart update race condition — stale quantity after concurrent |

## css-tokens

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-020 | CRIT | `(?:sm|md|lg|xl|2xl):[a-z][a-z0-9_-]+` | Tailwind CSS compiled file stale — missing responsive utilit |
| LES-021 | CRIT | `preflight:\s*false` | preflight: false mà thiếu image reset → images vỡ layout |
| LES-293 | CRIT | `--text-base:\s*clamp\([^,]*0\.8[0-9]*rem` | --text-base min value below 15px — Vietnamese body text too  |
| LES-006 | HIGH | `rgba?\(|#[0-9a-fA-F]{3,8}` | rgba() hardcode trong partial CSS thay vì var(--token) |
| LES-007 | HIGH | `@media[^{]*max-width` | @media max-width vi phạm mobile-first |
| LES-018 | HIGH | `grid-cols-[34]` | Mobile layout dùng grid khi spec yêu cầu horizontal scroll |
| LES-022 | HIGH | `hide-scrollbar` | hide-scrollbar utility dùng trong template nhưng chưa define |
| LES-027 | HIGH | `alt=""` | Product images trong loop thiếu alt text (empty alt="") |
| LES-028 | HIGH | `(?<!aria-hidden="true" )class="[^"]*mate...` | Decorative icons (Material Symbols) thiếu aria-hidden="true" |
| LES-029 | HIGH | `aria-label="Breadcrumb"` | Breadcrumb active item thiếu aria-current="page" |
| LES-044 | HIGH | `<img[^>]*(?!.*width=)[^>]*(?!.*height=)[...` | Lazy-loaded img without width/height — causes CLS layout shi |
| LES-048 | HIGH | `<input[^>]*type="(text|email|tel|passwor...` | Form input without label or aria-label — WCAG a11y violation |
| LES-061 | HIGH | `list-style:\s*none|list-none` | Breadcrumb `<ol>` hiển thị số thứ tự (1. 2. 3.) vì thiếu lis |
| LES-063 | HIGH | `max-w-\\[480px\\]` | Account page content card bị max-w-[480px] — không fullwidth |
| LES-068 | HIGH | `preflight:\\s*false` | Form input overflow khi preflight: false — thiếu box-sizing  |
| LES-069 | HIGH | `login_enqueue_scripts` | Login page không dùng theme DNA tokens — giao diện mặc định  |
| LES-266 | HIGH | `(?:background|background-color):\s*#fff(...` | Hardcoded #fff/#000 in inline style — breaks dark mode |
| LES-267 | HIGH | `(?:^|;|\{)\s*color:\s*#(?:[0-9a-fA-F]{3}...` | Hardcoded text color in inline <style> — breaks dark mode |
| LES-289 | HIGH | `style="[^"]*font-size:\s*\d+px` | Hardcoded font-size in inline styles — bypasses typography t |
| LES-290 | HIGH | `text-\[\d+px\]` | Arbitrary Tailwind text-[Npx] bypasses typography token syst |
| LES-292 | HIGH | `--text-5xl` | Missing --text-5xl token — incomplete typography scale per b |
| LES-019 | INFO | `gradient.*var\(--wz-(primary|secondary)\...` | Gradient/color dùng sai semantic token (ví dụ secondary vs s |
| LES-291 | SUGG | `\['\d+px'` | Tailwind config fontSize uses hardcoded px instead of CSS va |

## d3

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-534 | CRIT | `d3\.forceSimulation\([^)]*\).*\.data\([^...` | D3 force simulation nodes without initial x/y positions â€”  |

## dark-mode

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-701 | HIGH | `ring-gray-[23]00|ring-blue-[23]00|outlin...` | Ring/outline colors missing dark variants |
| LES-702 | HIGH | `style=.*(?:background|color).*(?:#fff|#f...` | Hardcoded white/black in inline styles without dark check |
| LES-703 | SUGG | `placeholder-gray-[45]00(?!.*dark:placeho...` | Placeholder text color missing dark variant |

## db-schema

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-385 | CRIT | `register_table\(` | Junction table without PRIMARY KEY or UNIQUE composite — all |
| LES-386 | CRIT | `'order_number'\s*=>` | order_number column without UNIQUE index — duplicate order n |
| LES-415 | CRIT | `'email'\s*=>\s*'varchar\([^)]+\)\s+NOT N...` | Missing UNIQUE Constraint on Email Column |
| LES-387 | HIGH | `'slug'\s*=>\s*'varchar` | Slug column with prefix index instead of UNIQUE — duplicate  |
| LES-388 | HIGH | `'(?:product_id|variation_id|user_id)'\s*...` | FK column in detail table without index — full table scan on |
| LES-389 | HIGH | `'secret'\s*=>\s*"varchar.*DEFAULT\s*''` | Webhook/API secret column defaults to empty string — unsigne |
| LES-390 | HIGH | `'user_id'\s*=>\s*'bigint.*DEFAULT NULL'` | Customer user_id column without UNIQUE — one WP user maps to |
| LES-391 | HIGH | `'idx_user'\s*=>\s*'user_id'` | Missing composite index for high-frequency query pattern — i |
| LES-420 | HIGH | `wpdb->query\([^)]*UPDATE[^)]*SET\s+\w*(?...` | Race condition in sold_count updates without atomic incremen |
| LES-421 | HIGH | `wpdb->delete\(` | Delete + bulk insert without transaction loses data on failu |
| LES-437 | HIGH | `function (import|migrate|seed)_` | Batch migration creates partial state without transaction |

## deployment

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-462 | HIGH | `demos/` | Deploy nested directory causes duplicate path segments in UR |

## edge-cases

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-278 | CRIT | `body\s*\{[^}]*overflow-x\s*:\s*hidden` | overflow-x:hidden trên body — PHẢI đặt trên html (gây bug iO |
| LES-268 | HIGH | `onerror` | Image tag thiếu onerror fallback — ảnh lỗi sẽ hiện broken ic |
| LES-269 | HIGH | `number_format\(\s*\$sold` | Sold count hiển thị raw number — thiếu abbreviation (>9999 p |
| LES-270 | HIGH | `\.line-clamp-4` | Thiếu .line-clamp-4 CSS utility — cần cho review text previe |
| LES-272 | HIGH | `esc_html.*\$.*count|\(string\).*\$.*coun...` | Review count hiển thị raw — thiếu abbreviation (>9999 phải = |
| LES-273 | HIGH | `99\+|> 99|>99|Math\.min.*99|min\(\s*99` | Cart badge thiếu overflow cap — >99 phải hiển thị 99+ |
| LES-275 | HIGH | `array_slice|\[:20\]|->take\(20\)|limit.*...` | Flash sale thiếu cap max 20 items — horizontal scroll quá dà |
| LES-276 | HIGH | `swiper|slider|carousel|splide|scroll-sna...` | Related products thiếu slider/carousel khi > 4 items |
| LES-277 | HIGH | `load.more|loadMore|load_more|pagination|...` | Reviews thiếu load-more pagination (5 per batch theo bluepri |
| LES-423 | HIGH | `current_time\(\s*['"]mysql['"]` | Time-based features using current_time() without timezone ha |
| LES-439 | HIGH | `WEZONE_[A-Z_]+_URL|WEZONE_[A-Z_]+_VERSIO...` | Plugin constants must have defined() guard before use |
| LES-443 | HIGH | `return\s+\$wpdb->get_results\s*\(` | $wpdb->get_results() returned directly without null guard —  |
| LES-271 | SUGG | `empty.*\.svg|/img/empty/|/images/empty` | Empty state dùng Material icon thay vì illustration SVG theo |
| LES-274 | SUGG | `placeholder\.(jpg|png|jpeg)` | Placeholder image helper trả về .jpg — blueprint yêu cầu .sv |
| LES-405 | SUGG | `!\s*\$[a-z_]+\s*&&\s*!\s*\$[a-z_]+\s*&&\...` | wz_format_dimensions() loose type coercion — string '0' trea |

## error-handling

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-530 | HIGH | `except Exception:\s*(pass|return)` | Silent Exception Handling Without Logging |
| LES-632 | HIGH | `except\s*(Exception\s*)?:\s*$` | Bare except swallowing errors silently |

## fastapi

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-522 | CRIT | `@app\.post\(.*\)\s*\n\s*(async\s+)?def\s...` | Missing Request Validation with Pydantic Models |
| LES-524 | CRIT | `CORSMiddleware|add_middleware.*CORS` | Missing CORS Configuration in FastAPI |
| LES-527 | CRIT | `Depends\((get_current_user|verify_token|...` | Missing Authentication Dependency in Protected Endpoints |
| LES-529 | CRIT | `def\s+get_db\(\):\s*\n\s+db\s*=.*\n\s+re...` | Missing Database Session Cleanup |
| LES-534 | CRIT | `@app\.(post|put|patch)\(.*\)\s*\n\s*asyn...` | Missing Input Validation on User Data |
| LES-525 | HIGH | `async\s+def\s+\w+.*:\s*\n.*await\s+(send...` | Background Task Not Using BackgroundTasks |
| LES-528 | HIGH | `async\s+def\s+\w+.*:\s*\n.*(requests\.|t...` | Blocking I/O in Async Endpoint |
| LES-532 | HIGH | `uvicorn\.run\s*\([^)]*port\s*=\s*\d+[^)]...` | FastAPI uvicorn.run without port availability check â€” cras |
| LES-533 | HIGH | `@app\.websocket.*\n.*async def.*websocke...` | WebSocket connection without confirmation message â€” client |
| LES-541 | HIGH | `allow_origins\s*=\s*\[.*localhost.*\]` | FastAPI CORS allow_origins hardcoded localhost ports |
| LES-521 | INFO | `@app\.(get|post|put|delete|patch)\(.*\)\...` | Missing Dependency Injection in FastAPI Endpoint |
| LES-523 | INFO | `@app\.(get|post|put|delete)\([^)]*\)\s*\...` | Missing Response Model in FastAPI Endpoint |
| LES-530 | SUGG | `@limiter\.limit|RateLimiter|slowapi` | Missing Rate Limiting on Public Endpoints |
| LES-535 | INFO | `@app\.websocket\(` | Missing WebSocket Connection Cleanup |
| LES-538 | SUGG | `X-Request-ID|request_id|correlation_id` | Missing Request ID for Tracing |
| LES-540 | INFO | `@app\.websocket|async\s+def\s+\w+.*WebSo...` | FastAPI WebSocket endpoint missing WebSocketDisconnect handl |

## feature-suggest

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| FEA-028 | HIGH | `"name"|"price"|"slug"` | Theme thiếu demo data package (onboarding requirement) |
| FEA-029 | HIGH | `setup.wizard|setup_wizard|SetupWizard|We...` | Theme thiếu setup wizard (onboarding requirement) |
| FEA-030 | HIGH | `import.demo|import_demo|wezone/v1/import` | Theme thiếu import-demo REST API endpoint (onboarding requir |
| LES-300 | HIGH | `exit.?intent|wz.?exit.?popup|clientY\s*<...` | Missing exit-intent popup — losing 70% cart abandoners witho |
| LES-301 | HIGH | `wz.?waitlist|waitlist.?form|waitlist.?su...` | Missing out-of-stock waitlist form — dead-end UX loses poten |
| LES-302 | HIGH | `exit_intent_shown|cart_recovered|exit_in...` | Missing cart recovery dataLayer events — abandonment funnel  |
| LES-304 | HIGH | `wz_get_product_bundle|wz_get_frequently_...` | Product page thiếu bundle offer — mất 5-10% AOV từ frequentl |
| LES-305 | HIGH | `wz_get_products\(|wz_query_products\(` | Related products không filter price range — gợi ý sản phẩm k |
| LES-306 | HIGH | `orderby['"]?\s*=>\s*['"]rand['"]` | Recommendations dùng random orderby — không personalized, lo |
| FEA-001 | SUGG | `wzRunFilter|wz_filter_products` | Realtime AJAX Filter — Bộ lọc sản phẩm không reload trang |
| FEA-002 | SUGG | `wz_get_filter_attributes` | Dynamic Product Attributes Filter — Bộ lọc thuộc tính từ DB |
| FEA-003 | SUGG | `quickEditId|openQuickEdit` | Quick Edit Inline — Chỉnh sửa nhanh sản phẩm ngay trên dashb |
| FEA-004 | SUGG | `WEZONE_ADMIN_UI_VERSION.*1\.0\.0` | Admin UI Build Cache — WEZONE_ADMIN_UI_VERSION cần bump sau  |
| FEA-005 | SUGG | `wz_collect_voucher|wz_user_vouchers|wz-c...` | Voucher Collect System — Thẻ mã giảm giá có thể thu thập |
| FEA-006 | SUGG | `wezone-voucher-template|VoucherTemplateA...` | Admin Voucher Template Picker — Chọn mẫu thẻ giảm giá trực q |
| FEA-007 | SUGG | `template === 4|template === 5|preview_lu...` | 5 Voucher Card Templates — Shopee/Gift/Sale/Luxury/Minimal d |
| FEA-008 | SUGG | `wz_voucher_colors|voucher-colors|get_vou...` | Voucher Color Customizer — Tùy chỉnh màu sắc thẻ giảm giá tr |
| FEA-009 | SUGG | `data-theme-toggle|data-theme|theme-toggl...` | Dark Mode Toggle — data-theme switch + localStorage persiste |
| FEA-010 | SUGG | `localStorage\.getItem\(['"]theme['"]\)|p...` | Dark Mode No-Flash Script — Inline theme detection in <head> |
| FEA-011 | SUGG | `skip-link|skip-to-content|#main-content` | Skip-to-Content Link — Accessibility keyboard navigation |
| FEA-012 | SUGG | `:focus-visible` | Focus Indicators — :focus-visible outline cho interactive el |
| FEA-013 | SUGG | `fetchpriority|srcset` | Performance Images — fetchpriority + srcset/sizes responsive |
| FEA-014 | SUGG | `font-display:\s*swap` | Critical CSS Inline + font-display:swap — Render-blocking op |
| FEA-015 | SUGG | `clamp\(|--text-base|--text-xl|--text-2xl` | Fluid Typography — clamp() responsive font sizes |
| FEA-016 | SUGG | `application/ld\+json|schema\.org` | JSON-LD Schema Markup — Product, BreadcrumbList, Organizatio |
| FEA-017 | SUGG | `og:title|og:image|og:description` | Open Graph Meta Tags — Social sharing preview |
| FEA-018 | SUGG | `empty-state|empty_state|giỏ hàng trống|C...` | Empty States — Friendly UI khi không có data |
| FEA-019 | SUGG | `skeleton|skeleton-pulse|skeleton__` | Skeleton Loading — Placeholder animation trước khi data load |
| FEA-020 | SUGG | `aria-label|aria-live|aria-modal` | ARIA Labels + Touch Targets — Accessible interactive element |
| FEA-021 | SUGG | `aspect-ratio|width=.*height=` | CLS Prevention — width/height + aspect-ratio on all images |
| FEA-022 | SUGG | `rel="canonical"|rel='canonical'|noindex` | Canonical URL + Robots Noindex — SEO duplicate prevention |
| FEA-023 | SUGG | `<h1[^>]*>.*<h1[^>]*>` | Heading Hierarchy — Single H1 + no skipped levels |
| FEA-024 | SUGG | `onerror|placeholder\.svg|placeholder/pro...` | Image Fallback — onerror placeholder + broken image handling |
| FEA-025 | SUGG | `abbreviate_number|format_short_number|wz...` | Thiếu helper wz_abbreviate_number() cho overflow display (99 |
| FEA-026 | SUGG | `skeleton|loading-placeholder|data-skelet...` | Thiếu skeleton loading component cho product grids |
| FEA-027 | SUGG | `error-state|error_state|ErrorState|netwo...` | Thiếu error state component (network offline, timeout, 500) |
| LES-303 | SUGG | `wz_get_threshold_suggestions|wz-threshol...` | Cart page thiếu threshold bar — mất 8-12% conversion đạt fre |

## file-structure

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-009 | CRIT | `inc/wz-shims\.php` | functions.php thiếu include file quan trọng |
| LES-010 | CRIT | `^Template:` | style.css có dòng Template: (theme trở thành child theme) |
| LES-034 | CRIT | `EF BB BF` | PHP file has UTF-8 BOM — causes fatal error with declare(str |
| LES-053 | CRIT | `;\s*\?[^>]|;\s*\? ` | PHP closing tag bị cắt trong inline echo — Parse error fatal |
| LES-088 | CRIT | `^use\\s+[A-Z][\\w\\\\]+(?!;\\s*//\\s*ver...` | use statement import class không tồn tại — fatal Class not f |
| LES-260 | CRIT | `assets/css/partials/|@import.*partials` | Theme thiếu Tailwind pipeline — dùng CSS partials/BEM thay v |
| LES-279 | CRIT | `@import ['"]partials/([^'"]+)['"]` | Stale main.bundle.css missing new CSS partials — features in |
| LES-035 | HIGH | `return\s*\[` | store-config.php thiếu required keys hoặc sai type |
| LES-036 | HIGH | `og:title|og:type|og:url|og:site_name` | SEO meta thiếu Open Graph tags |
| LES-037 | HIGH | `is_front_page|_wz_is_front_page` | Structured data JSON-LD thiếu hoặc invalid trên front page |
| LES-087 | HIGH | `declare\s*\(\s*strict_types\s*=\s*1\s*\)` | Namespaced PHP file thiếu declare(strict_types=1) — silent t |
| LES-238 | HIGH | `application/ld\+json` | JSON-LD Product schema thiếu GMC-required fields (priceValid |
| LES-257 | HIGH | `wz_component\(|wezone_is_active\(` | Theme code sai hướng blueprint — BEM thay Tailwind, thiếu wz |
| LES-284 | HIGH | `application/ld\+json` | Missing WebSite + SearchAction schema on homepage — Google s |
| LES-285 | HIGH | `BreadcrumbList` | Missing BreadcrumbList JSON-LD on product pages — Google won |
| LES-286 | HIGH | `Store|Organization` | Store/Organization schema missing logo + sameAs — incomplete |
| LES-288 | HIGH | `rel="canonical"` | Category page 2+ canonical points to self — must point to pa |
| LES-287 | SUGG | `twitter:card.*['"]product['"]` | twitter:card set to 'product' — invalid value, must be summa |

## js-contract

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-308 | CRIT | `\$\.ajax\(|\$\.get\(|\$\.post\(|fetch\(` | WordPress REST API calls missing nonce authentication |
| LES-008 | HIGH | `\.innerHTML\s*=[^;]*\+\s*(?!escHtml\()(?...` | innerHTML assignment với server data — XSS risk |
| LES-014 | HIGH | `wzTheme\.[a-zA-Z]+` | wzTheme object thiếu property mà JS đang dùng |
| LES-015 | HIGH | `id="wz-[^"]*form"` | Form có id/class nhưng JS thiếu submit handler |
| LES-042 | HIGH | `subtotal\s*[-+]\s*discount|subtotal\s*-\...` | Theme tự tính total thay vì dùng total_raw từ cart response  |
| LES-043 | HIGH | `fetch\([^)]*\)\.then(?!.*\.catch)` | fetch() without .catch() — network failure silently breaks U |
| LES-047 | HIGH | `getElementById\([^)]+\)\.(innerHTML|text...` | getElementById result used without null check — TypeError if |
| LES-051 | HIGH | `[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõô...` | Hardcoded Vietnamese in JS — cannot rebrand when cloning the |
| LES-052 | HIGH | `overflow.*hidden|overflow-hidden` | overflow-hidden added without guaranteed cleanup — permanent |
| LES-056 | HIGH | `wz-edit-addr|wz-delete-addr|wz-default-a...` | Missing JS handler cho CRUD buttons trong account template |
| LES-310 | HIGH | `useEffect\(\s*\(\)\s*=>\s*\{[^}]*fetch[^...` | Admin SPA stale data — no refetch on window focus or after m |
| LES-315 | HIGH | `update.*\$request->get_param|wpdb->updat...` | Admin concurrent edit — no optimistic locking on shared reso |
| LES-320 | HIGH | `catch\s*\([^)]*\)\s*\{[^}]*(?:console\.(...` | Admin SPA error handling — API errors shown as raw JSON or s |

## layout-consistency

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| PW-032 | HIGH | `px-6|px-8` | Container padding inconsistency (px-4 vs px-6 in same sectio |
| PW-034 | HIGH | `max-w-screen-xl|max-w-screen-2xl` | Mixed container strategies (max-w-7xl vs max-w-screen-xl) |

## loyalty

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-506 | CRIT | `function\s+(?:earn|award|grant)_points.*...` | Points earning without duplicate check - concurrent requests |
| LES-507 | CRIT | `function\s+redeem.*?\{.*?get_balance\(.*...` | Points redemption without row lock - race condition allows n |
| LES-508 | HIGH | `function\s+expire.*?points.*?\{(?!.*clea...` | Points expiry without clearing flags - points expire multipl |

## nextjs-react

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-128 | CRIT | `catch\s*\([^)]*\)\s*\{[^}]*(?:status:\s*...` | API route catch block swallows Next.js redirect — requireAdm |
| LES-129 | CRIT | `(?<!await )revalidate(?:Path|Tag)\(` | Next.js 16 revalidateTag/revalidatePath must be awaited — bu |
| LES-164 | CRIT | `exec_mode.*cluster|instances.*[2-9]|inst...` | PM2 cluster mode with Next.js standalone — EADDRINUSE crash  |
| LES-130 | HIGH | `&&\s*[^}]*use(Callback|Memo|State|Effect...` | useCallback/useMemo inside conditional JSX — React Error #31 |
| LES-131 | HIGH | `(?:^|\n)(?:const|let|export)\s+\w+\s*=\s...` | S3/external client init at module level — credentials not lo |
| LES-132 | HIGH | `requireAdmin` | requireAdmin vs withPlatformKey vs inline auth — wrong auth  |
| LES-133 | HIGH | `AbortController|req\.signal|[,{]\s*signa...` | AI route without AbortController — user navigates away, Clau |
| LES-134 | HIGH | `create<.*Store>` | Zustand store cache not cleared on session reset — stale AI  |
| LES-135 | HIGH | `\)\s*as\s+(?:string|number|boolean)\s*[;...` | TypeScript type error blocks CI build — as cast hides incomp |
| LES-136 | HIGH | `@layer\s+base\s*\{[^}]*--(?:wz|color|fon...` | Tailwind v4 @theme directive — CSS variables must use new @t |
| LES-137 | HIGH | `persist\s*\(` | Zustand persist without partialize — hydration mismatch in S |
| LES-138 | HIGH | `useMemo\s*\(\s*\(\)\s*=>\s*createClient` | createClient() in component body without useMemo — new Supab |
| LES-139 | HIGH | `supabase\.from\s*\(` | Middleware DB query on every route — narrow matcher to auth- |
| LES-152 | HIGH | `catch\s*\([^)]*\)\s*\{[^}]*return\s+\[\s...` | AI provider fallback returns stale cache on DB error — silen |
| LES-154 | HIGH | `validateConfig|safeParse|result\.success` | Industry config not validated at runtime — invalid JSON cras |
| LES-156 | HIGH | `resend\.com/emails|sendEmail|sendOrderCo...` | Resend email without address validation — silent 422 error w |
| LES-158 | HIGH | `addEventListener.*message|onmessage` | postMessage listener without origin check — any iframe can i |
| LES-160 | HIGH | `flashSale\.(end_time|products)|sale\.(en...` | API response shape mismatch between backend and frontend — T |
| LES-161 | HIGH | `sendTelegramMessage|telegram\.org|TELEGR...` | Telegram/external notification blocks critical path — use fi |
| LES-163 | HIGH | `await\s+fetch\s*\(\s*['"`]https?://(?!ap...` | fetch() without AbortSignal.timeout — hangs indefinitely whe |
| LES-165 | HIGH | `\.select\(\s*[']\*['](?!\s*,\s*\{[^}]*he...` | Build fails with implicit any from untyped Supabase response |
| LES-167 | HIGH | `next lint|eslint.*--max-warnings` | lint step blocks deploy — make non-critical checks non-block |
| LES-168 | HIGH | `ALLOWED_TAGS|allowlist|replace.*<script|...` | HTML sanitizer regex-based — use allowlist approach to preve |
| LES-170 | HIGH | `next build|npm run build` | Stale .next cache causes build to use old code — clear befor |
| LES-173 | HIGH | `context\.params\.` | Next.js 16 async params — context.params is now a Promise, m |
| LES-174 | HIGH | `fetchPage|response\.text\(\)|html\.lengt...` | Google Ads checker decompression bomb — limit response size  |
| LES-177 | HIGH | `indexnow|IndexNow|pingIndexNow` | IndexNow ping without URL normalization — duplicate submissi |
| LES-178 | HIGH | `z\.string\(\)\.transform.*Number|parseIn...` | Zod v4 z.coerce vs z.string().transform() — coerce handles F |
| LES-179 | HIGH | `useEffect\s*\(\s*\(\)\s*=>\s*\{[^}]*fetc...` | React 19 use() hook for Suspense data — replaces useEffect+u |
| LES-201 | HIGH | `useStore\(\)|use\w+Store\(\)(?!\s*\()` | Zustand store subscription without selector — unnecessary re |
| LES-203 | HIGH | `"use server"[\s\S]*(?:insert|update|dele...` | Server action without revalidation — stale data after mutati |
| LES-204 | HIGH | `useEffect\([^)]*\[[^\]]*(?:filter|option...` | useEffect with object/array dependency — infinite re-render  |
| LES-205 | HIGH | `"use client"[\s\S]{0,500}import.*(?:supa...` | Client component importing server-only module — build fails  |
| LES-610 | HIGH | `` | Unhandled Promise Rejection |

## performance

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-393 | CRIT | `SELECT\s+(?:status|\*)\s+FROM\s+\{?\$wpd...` | Order transition race condition — no SELECT FOR UPDATE |
| LES-417 | CRIT | `foreach\s*\([^)]+\)\s*\{[^}]*\$wpdb->(?:...` | Bulk insert/update must use wz_bulk_insert() or temp table s |
| LES-445 | CRIT | `get_post_meta\s*\(` | get_post_meta() N+1 in foreach loop — batch with update_meta |
| LES-457 | CRIT | `` | get_post_meta() N+1 in loop — AST-verified |
| LES-049 | HIGH | `foreach.*\{[^}]*wz_get_product\s*\(` | wz_get_product() inside foreach loop — N+1 database queries |
| LES-067 | HIGH | `dbDelta|create_table_raw` | dbDelta "Duplicate key name" spam — migration re-adds existi |
| LES-080 | HIGH | `foreach[^{]*\{[\s\S]*?\$wpdb->(?:insert|...` | $wpdb->insert/update trong foreach loop — N+1 queries, dùng  |
| LES-093 | HIGH | `private\s+static\s+(?:array|\?array|stri...` | Static property mutable — state leak giữa PHPUnit tests, gây |
| LES-098 | HIGH | `wp_remote_(?:get|post|request)\s*\(` | wp_remote_get/post thiếu timeout setting — block PHP worker, |
| LES-209 | HIGH | `<img[^>]*(?<!width)[^>]*(?<!height)[^>]*...` | Image without explicit width/height — Cumulative Layout Shif |
| LES-210 | HIGH | `import\s+\w+\s+from\s+['"](?:lodash|mome...` | Large bundle import — entire library loaded for one function |
| LES-211 | HIGH | `Cache-Control|cache|CACHE_|revalidate|ne...` | API route missing Cache-Control header — every request hits  |
| LES-212 | HIGH | `import\s+(?:.*\s+from\s+)?['"](?:.*(?:ch...` | Dynamic import missing for heavy client components — blocks  |
| LES-262 | HIGH | `style="[^"]*(?:aspect-ratio|object-fit)[...` | Product image in PHP template missing width/height — CLS ris |
| LES-263 | HIGH | `loading="eager"` | LCP hero image missing fetchpriority=high — slower LCP |
| LES-264 | HIGH | `'wezone-[^']*-(animations|spec-compariso...` | JS module enqueued on all pages without conditional check |
| LES-265 | HIGH | `^@import\s+['"]` | @import in CSS file — render-blocking chain |
| LES-281 | HIGH | `<img\s[^>]*src=[^>]*(?!.*\bwidth\s*=)[^>...` | img tag missing width/height attributes — CLS risk |
| LES-282 | HIGH | `font-display:\s*block` | font-display: block causes invisible text during font load ( |
| LES-283 | HIGH | `fetchpriority` | Hero/LCP image missing fetchpriority=high — delays largest p |
| LES-316 | HIGH | `get_results\([^)]*\)[\s\S]*?(?:fputcsv|c...` | Admin export without streaming — memory exhaustion on large  |
| LES-336 | HIGH | `get_user_meta\s*\(\s*\$user->ID\s*,\s*'` | N+1 get_user_meta() in customer normalize — 18 calls per use |
| LES-340 | HIGH | `get_results\s*\(\s*[^)]*wz_categories\s+...` | getCategories() raw SQL without object cache — fires every p |
| LES-351 | HIGH | `get_comment_meta\s*\(\s*\$comment->comme...` | N+1 queries in review listing — get_comment_meta + get_post  |
| LES-358 | HIGH | `ON DUPLICATE KEY UPDATE` | Atomic counter increment must use INSERT ON DUPLICATE KEY UP |
| LES-363 | HIGH | `DELETE.*LIMIT|batch.*delete|chunk.*delet...` | DELETE cleanup must use LIMIT to prevent table lock |
| LES-364 | HIGH | `LIMIT %d|LIMIT \d+|->export_all\s*\(` | REST export endpoint must limit rows to prevent memory exhau |
| LES-375 | HIGH | `private\s+\?array\s+\$cached_cart|\$this...` | CartEngine read methods each call get() separately — N+1 DB  |
| LES-397 | HIGH | `START\s+TRANSACTION` | Status update + history insert not wrapped in transaction |
| LES-398 | HIGH | `wp_cache_delete` | OrderStateMachine::transition() doesn't invalidate order cac |
| LES-418 | HIGH | `foreach.*\$wpdb->insert\(` | Seed import loops should use wz_bulk_insert() instead of N+1 |
| LES-425 | HIGH | `get_theme_tokens\s*\(` | CSS tokens rebuilt on every request without cache |
| LES-435 | HIGH | `foreach.*\{[\s\S]*?wpdb->update` | N+1 UPDATE queries in reorder loop |
| LES-446 | HIGH | `get_page_by_path\s*\(` | get_page_by_path() in loop — each call is a DB query |
| LES-447 | HIGH | `wp_schedule_single_event\s*\(\s*time\s*\...` | wp_schedule_single_event() race — multiple admin users trigg |
| LES-448 | HIGH | `set_transient\s*\(\s*['"]wz_` | Transient cache without invalidation hook — stale data after |
| LES-452 | HIGH | `SHOW TABLES LIKE` | SHOW TABLES query in hot-path loop — cache table existence c |
| LES-453 | HIGH | `\$wpdb->get_var.*foreach|foreach.*\$wpdb...` | N+1 $wpdb->get_var inside foreach — batch into single aggreg |
| LES-493 | HIGH | `export.*\(\s*\)\s*:\s*[^{]+\{[^}]*foreac...` | REST export endpoint must limit rows to prevent memory exhau |
| LES-511 | HIGH | `function\s+export_(?:products|posts|orde...` | Export endpoint thiáº¿u configurable LIMIT â€” memory exhaus |
| LES-379 | MEDI | `validateRow\s*\(\s*\$coupon_row|validate...` | resolveDiscount calls validate(code) after getByCode — valid |
| LES-380 | MEDI | `ON\s+DUPLICATE\s+KEY\s+UPDATE|INSERT.*ON...` | Cart save() uses REPLACE (DELETE+INSERT) — race condition on |
| LES-422 | SUGG | `do_action\(\s*['"][\w/_-]*cache[_-]?inva...` | Cache invalidation hook without specific cache keys |
| LES-424 | SUGG | `fonts\.googleapis\.com.*display=swap` | External font request on every login page load |
| LES-652 | SUGG | `\+= [\x27"]` | String Concatenation in Loop — Use join() |

## php-architecture

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-515 | CRIT | `public function boot\(\)[^}]*\{(?![^}]*w...` | Plugin Boot Missing wz_config Call |
| LES-518 | HIGH | `public static function instance\(\)[^}]*...` | Singleton Pattern Without Thread Safety |
| LES-520 | HIGH | `add_action\([^,]+,[^,]+\)\s*;` | Hook Registration Without Priority Control |
| LES-525 | SUGG | `private static \$instance.*public static...` | Singleton Without Test Reset Method |

## php-db

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-473 | CRIT | `public function restore.*\([\s\S]{0,500}...` | DB restore operations must validate SQL before executing to  |
| LES-495 | CRIT | `START TRANSACTION.*?COMMIT(?!.*if\s*\(\s...` | Transaction khÃ´ng cÃ³ error handling â€” COMMIT thá»±c thi  |
| LES-469 | HIGH | `wp_delete_file\(|unlink\([\s\S]{0,200}\$...` | Delete operations must use transaction or reverse order (DB  |
| LES-476 | HIGH | `return \$wpdb->get_results\(` | $wpdb->get_results() returns array|null â€” must guard befor |
| LES-482 | HIGH | `\$\w+\s*=\s*json_decode\(` | json_decode() missing error check - silent failure |
| LES-491 | HIGH | `wp_delete_file\s*\([^)]+\)\s*;[^}]*retur...` | File delete must happen AFTER database cleanup in delete ope |
| LES-498 | HIGH | `wp_cache_set\s*\([^,]+,\s*[^,]+\s*\)` | wp_cache_set() missing cache group - conflict with other plu |
| LES-519 | HIGH | `TRUNCATE TABLE.*wz_` | Rebuild Index Without Temp Table Swap |

## php-performance

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-497 | HIGH | `get_option\s*\([^)]+\).*?(?:foreach|whil...` | get_option() called multiple times in loop/filter without ca |
| LES-516 | HIGH | `foreach\s*\([^)]+\)\s*\{[^}]*\$wpdb->ins...` | N+1 Query in Loop - Use wz_bulk_insert |
| LES-481 | SUGG | `&lt;style&gt;[\s\S]{200,}` | Inline CSS trong wp_footer â€” nÃªn enqueue stylesheet Ä‘á»ƒ |
| LES-488 | SUGG | `<script(?!.*async).*googletagmanager|<sc...` | Multiple tracking scripts loaded synchronously block page re |

## php-security

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-001 | CRIT | `is_user_logged_in` | Account template thiếu is_user_logged_in() gate |
| LES-002 | CRIT | `wz_get_order_customer|get_current_user_i...` | order-detail.php không verify order thuộc về current user |
| LES-016 | CRIT | `$_GET[...]` | Order-related page thiếu IDOR check (user_id !== current use |
| LES-017 | CRIT | `wz_get_shop_url\(|wz_get_myaccount_url\(...` | wz_* utility function gọi trực tiếp trong template không có  |
| LES-030 | CRIT | `[{'pattern': '$_POST[...]'}, {'pattern-n...` | $_POST['password'] thiếu wp_unslash() trong AJAX handler |
| LES-039 | CRIT | `fetch(...)` | Cart/Checkout REST API thiếu nonce header — mọi action bị re |
| LES-045 | CRIT | `\$_(GET|POST|REQUEST|COOKIE)\[` | Raw $_GET/$_POST without sanitization — injection risk |
| LES-055 | CRIT | `wp_ajax_wz_change_password` | AJAX handler thiếu cho custom form (wp_ajax_* chưa đăng ký) |
| LES-057 | CRIT | `^function\s+wezone_\w+` | Duplicate function declaration across multiple inc/*.php — P |
| LES-064 | CRIT | `check_ajax_referer|wp_verify_nonce` | AJAX handler đăng ký nhưng thiếu check_ajax_referer() bên tr |
| LES-071 | CRIT | `'permission_callback'\s*=>\s*'__return_t...` | Write REST endpoint (POST/PUT/DELETE) public không auth — ai |
| LES-074 | CRIT | `WP_REST_Response(...)` | REST response chứa sensitive data (password/secret/token) —  |
| LES-075 | CRIT | `WP_REST_Server::CREATABLE|WP_REST_Server...` | Write REST route thiếu nonce verify trong handler — CSRF khi |
| LES-076 | CRIT | `'$wpdb->(?:query|get_results|get_row|get...` | SQL query không dùng $wpdb->prepare() — SQL injection risk |
| LES-078 | CRIT | `DROP TABLE|TRUNCATE TABLE` | DROP/TRUNCATE TABLE ngoài migration file — data loss risk nế |
| LES-081 | CRIT | `verify_ipn|verify_signature|verify_hmac|...` | IPN/webhook handler thiếu verify signature/amount/status — f |
| LES-124 | CRIT | `` | AJAX nonce mismatch — read-only endpoint trả 403 vì JS không |
| LES-213 | CRIT | `register_rest_route(...)` | WordPress plugin REST endpoint without permission callback — |
| LES-214 | CRIT | `$wpdb->(?:query|get_results|get_row|get_...` | wpdb query without prepare — SQL injection vulnerability |
| LES-309 | CRIT | `foreach.*$ids.*{[sS]*?$wpdb->(?:update|d...` | Admin bulk action without DB transaction — partial state on  |
| LES-311 | CRIT | `get_option(...)` | Admin settings stored XSS — unescaped output of admin-saved  |
| LES-319 | CRIT | `move_uploaded_file|wp_handle_upload|medi...` | Admin file upload MIME type bypass — extension check only |
| LES-325 | CRIT | `setcookie|set_cookie|wp_set_auth_cookie|...` | Admin session fixation — cookie scope too broad or missing s |
| LES-330 | CRIT | `if\s*\(\s*''\s*===\s*\$current_password\...` | REST API password endpoint must reject empty current_passwor |
| LES-345 | CRIT | `sanitize_textarea_field.*\$_POST|sanitiz...` | sanitize_textarea_field() trên JSON payload làm hỏng dữ liệu |
| LES-372 | CRIT | `max\s*\(\s*0.*\$.*rate|abs\s*\(\s*\$.*ra...` | Cart shipping rate must validate non-negative — negative rat |
| LES-373 | CRIT | `MAX_CART|max_items|cart_limit|count\s*\(...` | Cart must enforce max items/qty limit — unbounded cart is Do |
| LES-392 | CRIT | `[{'pattern': 'bwezone_is_active(...)'}, ...` | wezone_is_active() must be wrapped in function_exists() — fa |
| LES-395 | CRIT | `'note'\s*=>\s*\$note` | OrderHistory note stored without sanitization — stored XSS |
| LES-400 | CRIT | `validate\(\s*\$code\s*,\s*\$subtotal\s*\...` | wz_apply_coupon() must forward user_id to validate() — per-u |
| LES-401 | CRIT | `\$coupon_row\s*=\s*\$engine->getByCode` | wz_apply_coupon() TOCTOU — getByCode() can return null betwe |
| LES-417 | CRIT | `public function __construct\([^)]*string...` | Constructor path parameters need sanitization to prevent pat |
| LES-458 | CRIT | `` | echo/print unescaped variable — XSS risk (AST-verified) |
| LES-459 | CRIT | `` | $wpdb->query() without prepare() — SQL injection risk (AST-v |
| LES-460 | CRIT | `` | AJAX handler function missing nonce verification (AST-verifi |
| LES-461 | CRIT | `` | Direct $_GET/$_POST/$_REQUEST usage without sanitization (AS |
| LES-463 | CRIT | `FROM\s+\{\$\w+_table\}|JOIN\s+\{\$\w+_ta...` | SQL table prefix interpolation in prepared statements |
| LES-468 | CRIT | `class.*Controller.*\{[\s\S]{0,500}public...` | REST controller methods must verify current_user_can() even  |
| LES-472 | CRIT | `get_option\([^)]*secret|get_option\([^)]...` | S3/API secrets must use constants or encryption, not plainte |
| LES-475 | CRIT | `public function __construct\([^)]*string...` | Constructor path parameters must validate with realpath() to |
| LES-484 | CRIT | `echos+wp_kses_post(...)` | Tracking plugin custom code allows script injection via admi |
| LES-509 | CRIT | `functions+sideload(...)` | Image sideload thiáº¿u file type validation â€” arbitrary fi |
| LES-510 | CRIT | `functions+add(...)` | Redirect add() thiáº¿u URL validation â€” open redirect vuln |
| LES-514 | CRIT | `register_rest_route(...)` | REST API Missing Permission Callback |
| LES-517 | CRIT | `class \w+Admin[^{]*\{(?:(?!current_user_...` | Admin Handler Missing Capability Check |
| LES-521 | CRIT | `permission_callback.*__return_true` | REST API Public Endpoint Without Rate Limiting |
| LES-TEST-SEMGREP | CRIT | `wp_mail(...)` | Test Semgrep Integration - wp_mail without nonce |
| LES-031 | HIGH | `[{'pattern': 'wp_mail(...)'}, {'pattern-...` | wp_mail() hardcoded subject/body không dùng wz_config() |
| LES-050 | HIGH | `new WP_Query` | WP_Query without wp_reset_postdata — corrupts global post da |
| LES-066 | HIGH | `'defined\s*\(\s*[''']WEZONE_"` | Plugin constants `define()` thiếu `defined()` guard — Warnin |
| LES-070 | HIGH | `register_rest_route(...)` | REST route string arg thiếu sanitize_callback — raw user inp |
| LES-072 | HIGH | `ApiRateLimit|rate_limit|throttle|X-RateL...` | Public REST endpoint thiếu rate limit — DDoS/brute-force ris |
| LES-073 | HIGH | `$request->get_param(...)` | REST get_param() dùng raw không cast type — type confusion r |
| LES-077 | HIGH | `'$wpdb->prepare(...)` | $wpdb->prepare() nhưng interpolate variable trong format str |
| LES-079 | HIGH | `$wpdb->(?:insert|update|delete|replace|q...` | DB operation có thể thiếu $wpdb->prefix — multisite broken |
| LES-085 | HIGH | `(?:redirect|return_url|callback_url|ipn_...` | Payment redirect URL không esc_url() — open redirect risk sa |
| LES-094 | HIGH | `catch(...)` | Empty catch block — exception bị nuốt, bug ẩn không debug đư |
| LES-215 | HIGH | `check_ajax_referer|wp_verify_nonce|verif...` | AJAX handler without nonce verification — CSRF attack vector |
| LES-312 | HIGH | `wp_create_nonce|wp_localize_script.*nonc...` | Admin SPA nonce expires after 24h — silent 403 on long sessi |
| LES-314 | HIGH | `LIKE\s*['"]%.*\$|LIKE.*\$wpdb->prepare.*...` | Admin LIKE query injection — search input with % and _ wildc |
| LES-323 | HIGH | `permission_callback.*manage_options` | Admin capability check too broad — manage_options for all ac |
| LES-324 | HIGH | `wp_mail(...)` | Admin notification rate limit missing — spam flood to custom |
| LES-326 | HIGH | `delete_option|drop_table|update.*payment...` | Admin sensitive actions without re-authentication — no 2FA/p |
| LES-328 | HIGH | `dashboard/stats|dashboard/revenue|dashbo...` | Admin dashboard widget data leak — all stats visible regardl |
| LES-331 | HIGH | `\$new_password\s*===\s*\$current_passwor...` | REST API password endpoint must reject new_password === curr |
| LES-334 | HIGH | `->exists\(\)` | REST API must guard wp_get_current_user()->exists() after re |
| LES-335 | HIGH | `wp_create_nonce` | REST API password endpoint must return fresh nonce after pas |
| LES-346 | HIGH | `check_ajax_referer(...)` | Nonce reuse — nhiều AJAX action dùng chung 1 nonce |
| LES-349 | HIGH | `\['tokens'\]\s*\?\?\s*array\(\)` | Missing type validation sau json_decode từ get_option |
| LES-362 | HIGH | `mask_email|wz_mask_email|str_repeat.*\*|...` | REST API must not expose raw customer email in response |
| LES-374 | HIGH | `cached_key\s*=\s*null` | SessionHandler destroy() must clear cached_key to prevent st |
| LES-402 | HIGH | `qty\s*<=\s*0|qty\s*<\s*1|\$qty\s*<=\s*0|...` | wz_cart_add() must reject qty <= 0 — negative qty enables pr |
| LES-403 | HIGH | `in_array\(\s*\$type|array\(\s*'info'\s*,...` | wz_add_notice() must whitelist $type — arbitrary type enable |
| LES-411 | HIGH | `public static function (enable|disable|u...` | Static utility methods modifying state must check capabiliti |
| LES-412 | HIGH | `update_option(...)` | Option name injection via unsanitized string interpolation |
| LES-434 | HIGH | `locate_template\(.*\$` | Template path traversal via locate_template() with DB-derive |
| LES-438 | HIGH | `wz_log(...)` | wz_log must mask PII (email, phone) before logging |
| LES-440 | HIGH | `'permission'\s*=>\s*'public'` | Public REST endpoints must have rate limiting for abuse prev |
| LES-441 | HIGH | `\{\$\w+\}\s*=\s*\{\$\w+\}|UPDATE.*\{\$\w...` | SQL column name must use allowlist validation, never interpo |
| LES-451 | HIGH | `'__return_true'` | Public REST endpoint __return_true without rate limiting — a |
| LES-454 | HIGH | `\$_SERVER\s*\[` | $_SERVER accessed without wp_unslash() — WPCS sanitization r |
| LES-455 | HIGH | `get_param.*per_page|per_page.*get_param` | Missing per_page bounds check in REST list endpoint — allows |
| LES-470 | HIGH | `strtotime\([^)]*get_option\(|strtotime\(...` | strtotime() with user input needs validation to prevent comm |
| LES-485 | HIGH | `\$_COOKIE\[[^\]]+\]\s*\?\?` | $_COOKIE direct access without sanitization in consent check |
| LES-486 | HIGH | `isset(...)` | GDPR consent bypass via unsanitized $_GET parameter |
| LES-500 | HIGH | `permission_callback.*__return_true` | REST API public endpoint without rate limiting or nonce |
| LES-503 | HIGH | `$w+s*=s*[^?]*s*json_decode(...)` | JSON decode without error check causes silent data loss |
| LES-512 | HIGH | `functions+check_redirect(...)` | Redirect check thiáº¿u rate limiting â€” DoS via redirect ta |
| LES-513 | HIGH | `functions+import_(?:products|posts)(...)` | Import batch size khÃ´ng validate â€” memory exhaustion via  |
| LES-523 | HIGH | `wp_remote_(get|post)\([^)]+\)(?![^;]*tim...` | HTTP Request Without Timeout |
| LES-524 | HIGH | `$w+s*=s*[^?]*file_get_contents(...)` | file_get_contents Without Size/Existence Check |
| LES-341 | SUGG | `extract(...)` | extract() in email template render — variable shadowing risk |
| LES-381 | MEDI | `wz_rate_limit|throttle|rate_limit.*cart` | Public GET /cart endpoint needs rate limiting — abuse vector |
| LES-420 | INFO | `add_action\([^,]+,\s*array\(\s*\$this,\s...` | Hook callbacks don't need nonce checks (false positive exclu |
| LES-444 | SUGG | `setcookie(...)` | Cookie set with httpOnly=false — accessible to XSS scripts |

## placeholder

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-011 | HIGH | `(?<!\{)\{theme[-_][^}]*\}(?!\})` | Single-brace placeholder thay vì double-brace |

## portability

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-639 | INFO | `C:[/\\]Users[/\\]\w+|/home/\w+/` | Hardcoded User Path — Not Portable |
| LES-643 | INFO | `\.replace\s*\(\s*["\\x27]~["\\x27]` | Path Tilde Expansion via str.replace — Use os.path.expanduse |
| LES-647 | SUGG | `sys\.path\.insert\(0` | sys.path.insert — Fragile Import Hack |
| LES-651 | SUGG | `open\([^)]+\)` | open() Without Encoding — Platform-Dependent Behavior |
| LES-672 | SUGG | `["\x27]\d+\.\d+\.\d+\.\d+["\x27]` | Hardcoded IP Address — Use Config |

## python

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-511 | CRIT | `except\s*:` | Bare Except Clause Swallows All Exceptions |
| LES-512 | CRIT | `(?<!await\s)async\s+def\s+\w+\s*\([^)]*\...` | Async Function Not Awaited |
| LES-616 | CRIT | `except\s*:` | Bare except clause swallows all errors silently |
| LES-617 | CRIT | `def\s+\w+\s*\([^)]*(?:=\s*\[\]|=\s*\{\}|...` | Mutable default argument in function definition |
| LES-514 | HIGH | `def\s+\w+\([^)]*=\s*(\[\]|\{\}|set\(\))` | Mutable Default Argument |
| LES-537 | HIGH | `(requests\.(get|post)|httpx\.(get|post))...` | Missing Timeout on External HTTP Requests |
| LES-622 | HIGH | `(?:os\.path\.join|Path)\s*\([^)]*\)\s*.*...` | Hardcoded Windows path separator instead of os.path or Path |
| LES-627 | HIGH | `get_connection\(\)` | SQLite connection not closed in finally/with block |
| LES-630 | HIGH | `C:/Users/\w+|C:\\\\Users\\\\` | Hardcoded Windows user path |
| LES-631 | HIGH | `args\.get\(\s*"[^"]*"\s*,\s*\d+\s*\)` | MCP/API args not cast to expected type |
| LES-634 | HIGH | `except\s*:\s*$` | Bare except without exception type |
| LES-727 | HIGH | `\.get\([\x27"]pattern[\x27"]\s*,\s*[\x27...` | Pattern field from YAML frontmatter may be list, not string |
| LES-510 | SUGG | `def\s+\w+\s*\([^)]*\)\s*:` | Missing Type Hints in Function Signatures |
| LES-513 | INFO | `(open\(|connect\(|acquire\().*\n(?!.*wit...` | Context Manager Not Used for Resource Cleanup |
| LES-517 | SUGG | `try:\s*\n\s+\w+\[.*\]\s*\n\s+except\s+Ke...` | Dictionary Key Check with `in` Instead of Exception Handling |
| LES-518 | SUGG | `@staticmethod\s*\n\s+def\s+\w+` | Using `@staticmethod` Without Clear Benefit |
| LES-519 | SUGG | `if\s+len\(\w+\)\s*(==|!=|>|<)\s*0` | Using `len()` to Check Empty Sequence |
| LES-520 | SUGG | `os\.path\.(join|exists|isfile|isdir|dirn...` | Not Using `pathlib` for File Path Operations |
| LES-531 | INFO | `print\(` | Using `print()` Instead of Logging |
| LES-536 | INFO | `global\s+\w+` | Global Variable Mutation in Function |
| LES-543 | INFO | `sys\.path\.insert\(0,.*\)(?!.*if.*not in...` | sys.path.insert without duplicate check |
| LES-544 | SUGG | `^_\w+\s*=\s*\w+Manager\(\)|^_\w+\s*=\s*\...` | Global singleton manager instance not thread-safe |
| LES-618 | SUGG | `^\s*global\s+\w` | Global variable mutation via global statement |
| LES-619 | INFO | `open\s*\([^)]*\)\s*(?!.*encoding)` | open() without explicit encoding on Windows |
| LES-620 | SUGG | `except\s+Exception\s*:` | Broad except Exception catches too many error types |
| LES-621 | SUGG | `sys\.path\.insert\s*\(\s*0` | sys.path.insert(0) makes imports fragile and order-dependent |
| LES-623 | INFO | `^\s*print\s*\(` | print() used for logging instead of proper logger |
| LES-624 | SUGG | `for\s+\w+\s+in\s+.*:\s*\n\s+\w+\s*\+=\s*...` | String concatenation in loop instead of join() |
| LES-625 | SUGG | `^\s{4,}import\s+\w` | Nested import inside function body (non-lazy) |
| LES-626 | SUGG | `logger?\.\w+\s*\(\s*f["\x27]` | f-string or format() in logging call (defeats lazy evaluatio |
| LES-633 | SUGG | `\.replace\s*\(\s*["\x27]~["\x27]` | Manual tilde expansion instead of os.path.expanduser |

## python-windows

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-612 | CRIT | `subprocess\.run\([^)]*text\s*=\s*True(?!...` | subprocess.run on Windows must set encoding utf-8 |

## react

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-531 | CRIT | `renderGraph\s*\([^)]*\)` | React useEffect race condition - renderGraph called before S |
| LES-536 | HIGH | `useEffect.*\[\].*loadGraph|useEffect.*We...` | React useEffect infinite loop on WebSocket reconnect |
| LES-537 | HIGH | `useEffect.*\[\].*load|useEffect.*async.*...` | useEffect infinite loading on WebSocket reconnect |
| LES-539 | HIGH | `setInterval.*async\s+function|setInterva...` | setInterval polling async function without mounted guard |

## reliability

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-642 | HIGH | `assert\s+(isinstance|len|type)` | assert for Input Validation — Stripped in -O Mode |
| LES-648 | HIGH | `global_dict\[key\] = value` | Global Dict Mutation Without Lock — Thread Unsafe |
| LES-657 | HIGH | `def \w+\([^)]*=\s*[\[\{]` | Mutable Default Argument — Shared State Bug |
| LES-661 | HIGH | `requests\.(get|post|put|delete)\([^)]*\)` | requests.get/post Without Timeout — Hangs Forever |
| LES-673 | HIGH | `signal\.signal\(` | signal.signal in Thread — Only Works in Main Thread |
| LES-646 | SUGG | `tempfile\.\w+\(` | tempfile Without Context Manager — Resource Leak |
| LES-649 | SUGG | `datetime\.now\(\)` | datetime.now() Without Timezone — Ambiguous Timestamps |
| LES-653 | SUGG | `\.write\(` | File Write Without Flush — Data Loss on Crash |
| LES-665 | SUGG | `^\s*raise$` | raise Without Exception Type |

## resource-management

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-528 | HIGH | `open\([^)]+\)(?!\s*as\s)` | File Handle Leak - Missing Context Manager |

## responsive

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-718 | CRIT | `grid-cols` | Grid missing tablet breakpoint (grid-cols-2 lg:grid-cols-4,  |
| LES-719 | CRIT | `md:hidden|lg:hidden` | md:hidden on body/main blocking desktop content |
| LES-725 | CRIT | `grid-cols` | WP theme grid missing tablet breakpoint |
| LES-715 | HIGH | `className="[^"]*\bw-\[(?:[4-9]\d{2}|[1-9...` | Fixed width on container causes horizontal scroll on mobile |
| LES-717 | HIGH | `className="[^"]*\bflex\b[^"]*\bflex-row\...` | Flex row without wrap causes overflow on mobile |
| LES-720 | HIGH | `flex-row|flex-col` | Flex layout missing responsive stack (no flex-col on mobile) |
| LES-721 | HIGH | `md:hidden|lg:hidden` | Bottom nav visible on desktop (missing md:hidden) |
| LES-722 | HIGH | `hidden lg:block|hidden md:block` | Sidebar filters visible on mobile (missing responsive hide) |
| LES-723 | HIGH | `text-(xl|2xl|3xl|4xl|5xl)` | Text size has lg: variant but no base mobile size |
| LES-726 | HIGH | `hidden lg:block|hidden md:block|lg:block...` | WP sidebar visible on mobile without responsive hide |
| LES-724 | SUGG | `p[xytblr]?-|m[xytblr]?-` | Padding/margin jumps without intermediate breakpoint |

## security

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-628 | CRIT | `subprocess\.(run|call|Popen)\([^)]*shell...` | Command injection via subprocess shell=True |
| LES-629 | CRIT | `[^_]eval\s*\(` | Unsafe eval() on external data |
| LES-635 | CRIT | `pickle\.(load|loads)\s*\(` | pickle.load — Arbitrary Code Execution Risk |
| LES-637 | CRIT | `\bos\.system\s*\(` | os.system() — Use subprocess Instead |
| LES-638 | CRIT | `(password|secret|api_key|token)\s*=\s*["...` | Hardcoded Credentials in Python Source |
| LES-641 | CRIT | `(execute|executemany)\s*\(\s*f["\x27](?!...` | SQL Injection via String Formatting |
| LES-644 | CRIT | `subprocess\.\w+\(.*shell\s*=\s*True` | subprocess shell=True — Command Injection Risk |
| LES-655 | CRIT | `\bexec\s*\(` | exec() Usage — Arbitrary Code Execution |
| LES-656 | CRIT | `yaml\.load\(` | yaml.load() Without SafeLoader — Code Execution Risk |
| LES-666 | CRIT | `chmod.*0o?777` | chmod 0o777 — World-Writable Permissions |
| LES-667 | CRIT | `jwt\.decode.*verify.*False` | JWT Decode Without Verification |
| LES-645 | HIGH | `__import__\s*\(` | Dynamic __import__() — Use importlib Instead |
| LES-654 | HIGH | `redirect\(request\.` | Unvalidated Redirect — Open Redirect Risk |
| LES-659 | HIGH | `hashlib\.(md5|sha1)\s*\(` | MD5/SHA1 for Security — Use SHA256+ |
| LES-660 | HIGH | `random\.(randint|choice|randrange)\(` | random Module for Security — Use secrets Instead |
| LES-662 | HIGH | `verify\s*=\s*False` | requests verify=False — SSL Bypass |
| LES-663 | HIGH | `DEBUG\s*=\s*True` | DEBUG=True in Production Config |
| LES-668 | HIGH | `(ElementTree|minidom|lxml)\.(parse|froms...` | XML Parsing — XXE Vulnerability Risk |
| LES-669 | HIGH | `re\.(match|search).*\(\.[*+]\)+` | Regex with Catastrophic Backtracking Risk |
| LES-670 | HIGH | `(log|print).*password` | Logging Sensitive Data (password, token, secret) |
| LES-671 | HIGH | `X-Forwarded-For` | Client IP from X-Forwarded-For — Spoofable |
| LES-526 | INFO | `subprocess\.(run|call|Popen).*shell=True` | Shell Injection via subprocess shell=True |
| LES-527 | INFO | `subprocess\.(run|call|Popen)\([^)]*shell...` | Shell Injection via subprocess shell=True (duplicate) |
| LES-529 | INFO | `subprocess\.(run|call|Popen)(?!.*timeout...` | Missing Subprocess Timeout |
| LES-636 | INFO | `\beval\s*\(` | eval() Usage — Code Injection Risk |

## supabase

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-171 | CRIT | `fetch\s*\(\s*(?:url|rawUrl|targetUrl|use...` | User-supplied URL fetched server-side without SSRF protectio |
| LES-141 | HIGH | `gmc_business_id|NOTIFY pgrst` | Supabase schema cache stale after migration — insert fails w |
| LES-142 | HIGH | `\.eq\s*\(\s*['"]store_id['"]` | Platform store data leak — missing store_id filter in multi- |
| LES-143 | HIGH | `\.eq\s*\(\s*['"]status['"],\s*['"]pendin...` | Webhook optimistic lock missing — concurrent webhooks double |
| LES-144 | HIGH | `transferAmount|amount.*===|amount.*!==` | Payment amount comparison with == on floats — rounding cause |
| LES-145 | HIGH | `postMessage|WZ_APPLY_COLORS|setProperty` | Color CSS injection via postMessage — validate color values  |
| LES-146 | HIGH | `ilike.*search|search.*ilike` | Search query ilike injection — user input with % or _ wildca |
| LES-147 | HIGH | `corsHeaders\s*\(\s*\)` | CORS corsHeaders() without req — allows all origins instead  |
| LES-148 | HIGH | `supabase\s*\.\s*channel\s*\(|\.on\s*\(\s...` | Realtime subscription without cleanup — channel leak on comp |
| LES-149 | HIGH | `^\d{3}_` | Migration duplicate numbering — schema drift between environ |
| LES-150 | HIGH | `from\(['"](?:stores|demo_stores)['"]\)` | Query references non-existent table — demo_stores vs stores  |
| LES-151 | HIGH | `supabase\.from\(['"]orders['"]\)\.insert` | RPC function vs direct insert — bypass PostgREST schema cach |
| LES-153 | HIGH | `\.catch\s*\(|fire.and.forget|void\s+send` | Email send blocks webhook response — use fire-and-forget wit |
| LES-155 | HIGH | `api_key.*insert|insert.*api_key` | API key stored in plaintext — encrypt at rest with AES-256-G |
| LES-157 | HIGH | `verifyVnpay|vnp_SecureHash.*verify|verif...` | VNPay callback without signature verify — attacker can fake  |
| LES-159 | HIGH | `checkRateLimit|rate.limit|rateLimit` | Platform API key validation without rate limit — brute-force |
| LES-162 | HIGH | `supabase\.rpc\s*\(|\.rpc\(` | RPC function for atomic operations — avoid partial state fro |
| LES-166 | HIGH | `x-sepay-token|SEPAY_WEBHOOK_SECRET|timin...` | SePay webhook signature must use timing-safe comparison — pr |
| LES-169 | HIGH | `CACHE_LONG|CACHE_MEDIUM|CACHE_SHORT|CACH...` | API response missing Cache-Control — CDN caches sensitive da |
| LES-172 | HIGH | `zip\.file.*\.env|generateEnvFile` | Platform export ZIP includes API key in .env — must be .env. |
| LES-175 | HIGH | `new Map.*RateLimit|checkRateLimit|rate.l...` | In-process rate limiter leaks memory without cleanup — Map g |
| LES-176 | HIGH | `rate_limits|scan_count|RATE_LIMITS` | DB-backed rate limit with daily window — proper pattern for  |
| LES-180 | HIGH | `store\.id` | Platform CRUD validation — required fields, type coercion, a |
| LES-206 | HIGH | `DROP TABLE|ALTER TABLE.*DROP|ALTER TABLE...` | Migration missing down/rollback — cannot undo schema change |
| LES-208 | HIGH | `supabase\.from\([^)]+\)\.select\([^)]*\)...` | Supabase query without pagination — memory exhaustion on lar |

## websocket

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-535 | HIGH | `@app\.websocket.*\n.*async def.*:.*\n.*a...` | WebSocket server accepts connection but sends no handshake m |
| LES-536 | HIGH | `useEffect\(\s*\(\)\s*=>\s*\{[^}]*new\s+W...` | WebSocket reconnection missing tab visibility handling |
| LES-542 | HIGH | `async\s+def\s+broadcast.*:.*for.*active_...` | WebSocket broadcast catches send errors but doesn't remove d |

## wezone-api

| ID | Sev | Pattern | Summary |
|----|-----|---------|---------|
| LES-004 | CRIT | `wc_|WC_|WC\(\)|woocommerce_` | wc_* reference còn sót trong template |
| LES-012 | CRIT | `wz_[a-z_]+\(` | Template gọi wz_*() nhưng shim chưa khai báo function đó |
| LES-013 | CRIT | `wz_[a-z_]+\(` | wz_*() signature mismatch — caller truyền array nhưng shim n |
| LES-023 | CRIT | `wezone-templates/shop/archive\.php` | Thiếu wezone-templates/shop/archive.php — trang /shop trả 40 |
| LES-024 | CRIT | `wz_get_categories\s*\(\s*\[` | wz_get_categories() nhận array options thay vì ?int parent_i |
| LES-025 | CRIT | `wezone-templates/shop/category\.php` | Thiếu wezone-templates/shop/category.php — trang /category/{ |
| LES-033 | CRIT | `\$item\['quantity'\](?!.*\?\?)` | Cart item dùng key 'quantity' thay vì 'qty' — qty=0, subtota |
| LES-058 | CRIT | `(?:provinces|districts|wards)\s*=\s*\[` | Địa chỉ không chọn được tỉnh/quận/xã — dữ liệu địa chính cũ  |
| LES-059 | CRIT | `allowed_sections` | Router $allowed_sections thiếu section → account sub-page fa |
| LES-060 | CRIT | `wz_router_rewrite_flushed` | Router thiếu flush_rewrite_rules → /my-account/orders/{id}/  |
| LES-062 | CRIT | `\\$order\\['user_id'\\]` | order-detail check user_id nhưng OrderEngine trả customer_id |
| LES-065 | CRIT | `flush_rewrite_rules|add_rewrite_rule|get...` | WordPress function thiếu `\` prefix trong namespaced class — |
| LES-086 | CRIT | `^namespace\s+WeZone` | WordPress function thiếu \ prefix trong namespace — fatal er |
| LES-090 | CRIT | `'add_action\s*\(\s*['''][^'"]+['"]\s*,\s...` | add_action/add_filter callback method không tồn tại trong cl |
| LES-091 | CRIT | `wz_config\s*\(` | Plugin boot() thiếu wz_config() — config không load, mọi set |
| LES-095 | CRIT | `wp_die\s*\(` | wp_die() trong REST/AJAX handler — trả HTML thay JSON, front |
| LES-106 | CRIT | `'home_url\s*\(\s*[''']/?\?cat="` | wz_get_product_categories() tạo URL dạng query param `/?cat= |
| LES-108 | CRIT | `add_rewrite_rule.*category|class_exists....` | Theme thiếu category routing shim khi wezone-core Router khô |
| LES-127 | CRIT | `get_results|get_var|get_row` | Deploy thiếu DB migration — template silently returns empty, |
| LES-258 | CRIT | `\$product->(?:get_|is_|has_)` | Product dùng object syntax ($product->method()) thay vì arra |
| LES-259 | CRIT | `is_singular\(['"]product['"]\)|post_type...` | CPT slug sai — dùng 'product' thay vì 'wz_product' |
| LES-307 | CRIT | `wz_icon\(\s*['"][^'\"]+['"]\s*,\s*['"][^...` | wz_icon() called with string instead of array — fatal TypeEr |
| LES-313 | CRIT | `update.*status|set_status|change_status` | Order status invalid transition — no state machine validatio |
| LES-317 | CRIT | `price.*\$request->get_param|get_param.*p...` | Admin product price validation missing — negative/zero/NaN p |
| LES-327 | CRIT | `fgetcsv|str_getcsv|csv.*import|import.*c...` | Admin batch import CSV without validation — malformed data c |
| LES-357 | CRIT | `\$inserted\s*=\s*\$wpdb->insert|if\s*\(\...` | wpdb->insert() must check return before deleting transients |
| LES-394 | CRIT | `^\s*\$wpdb->update\s*\(` | completePayment() unchecked DB update result |
| LES-483 | CRIT | `public function boot\(\):` | Plugin boot() missing wz_config() call |
| LES-005 | HIGH | `^function wz_(?!shim_)` | wz_shim function thiếu function_exists() guard |
| LES-026 | HIGH | `>= \d{5,}|\? 0 : \d{4,}|wz_format_price\...` | Hardcoded business values thay vì wz_config() |
| LES-032 | HIGH | `'free_ship_threshold'\s*=>\s*0|'default'...` | store-config.php chứa placeholder/zero values sau clone |
| LES-038 | HIGH | `wz_shim_cart_response` | wz_shim_cart_response() thiếu required keys — JS UI broken |
| LES-040 | HIGH | `\$_GET\['product_id'\]|\$_GET\['category...` | Template đọc data qua $_GET/$_POST thay vì get_query_var('wz |
| LES-041 | HIGH | `wz_shim_rest_checkout|OrderEngine.*creat...` | Checkout form thiếu required billing fields — OrderEngine tr |
| LES-054 | HIGH | `'get_query_var\s*\(\s*[''']wz_tpl_order_...` | Template đọc wz_tpl_order_id thay vì wz_order_id — order det |
| LES-082 | HIGH | `'get_option\s*\(\s*['''].*(?:secret|key|...` | Payment gateway secret key từ get_option() không check empty |
| LES-083 | HIGH | `==\s*\$.*(?:amount|total|vnp_Amount)|\$....` | Payment amount so sánh float bằng == — sai khi có rounding,  |
| LES-084 | HIGH | `update_order_status|order_status.*=|stat...` | Order status change thiếu wz_log() — không có audit trail kh |
| LES-089 | HIGH | `public\s+function\s+\w+\s*\([^)]*\)\s*(?...` | Public method thiếu return type — strict_types không enforce |
| LES-092 | HIGH | `'add_action\s*\(\s*[''']init['"]\s*,.*,\...` | Plugin hook init priority 0 — conflict với wezone-core, race |
| LES-096 | HIGH | `error_log\s*\(` | Dùng error_log() thay vì wz_log() — log không structured, kh |
| LES-097 | HIGH | `throw\s+new\s+\\?(?:Exception|RuntimeExc...` | Exception thrown không có message — stack trace vô nghĩa khi |
| LES-099 | HIGH | `wp_remote_(?:get|post|request)\s*\(` | wp_remote_* response không check is_wp_error() hoặc status c |
| LES-100 | HIGH | `https?://(?:api\.ghn\.vn|services\.giaoh...` | Shipping API URL hardcode trong method — không switch được s |
| LES-101 | HIGH | `calculate_fee|get_shipping_rate` | Shipping rate calculation thiếu validate weight/dimensions — |
| LES-102 | HIGH | `(?<!wp_)json_encode\s*\(` | json_encode() thiếu JSON_UNESCAPED_UNICODE — Vietnamese text |
| LES-104 | HIGH | `wp-content/plugins/|ABSPATH.*wp-content` | Hardcode wp-content/plugins/ path — broken khi custom WP_CON |
| LES-105 | HIGH | `define\s*\([^,]+,\s*(?:get_option|\\get_...` | define() với get_option() ở file load — chạy trước DB ready, |
| LES-107 | HIGH | `\$materials\s*=\s*\[` | Sidebar filter hardcode mockup data thay vì query từ DB |
| LES-237 | HIGH | `wz_config\(\s*'(?:shop_name|name)',\s*'[...` | wz_config() fallback chứa brand-specific text — phá clone-re |
| LES-261 | HIGH | `\$nav_items\s*=\s*array|home_url\(['"]/(...` | Hardcode navigation/content tĩnh thay vì đọc từ wz_config()  |
| LES-318 | HIGH | `wpdb->(?:update|delete|insert)\s*\([^)]*...` | Admin audit trail missing — no log of who changed what and w |
| LES-321 | HIGH | `insert.*coupon|create.*coupon|save.*coup...` | Admin coupon code collision — no uniqueness check before sav |
| LES-322 | HIGH | `start_time|end_time|start_at|end_at|star...` | Admin flash sale time validation — end_time before start_tim |
| LES-332 | HIGH | `update_user_meta\s*\([^)]*['"](?:billing...` | User meta keys must use wezone_ prefix (not billing_/shippin |
| LES-333 | HIGH | `wp_update_user|update_user_meta` | REST API must fire action hooks after update (profile_update |
| LES-337 | HIGH | `wz_product_repo\(\)|wz_variation_repo\(\...` | Adapter duplicate code — WZ_Product and WZ_ProductRelations  |
| LES-342 | HIGH | `updatePrice.*regular_price.*=>.*price.*=...` | updatePrice() does not clear sale_price — causes price incon |
| LES-347 | HIGH | `wp_add_inline_script.*nonce|wzDesignInli...` | Duplicate data exposure — wp_localize_script + wp_add_inline |
| LES-348 | HIGH | `wp_send_json_(success|error).*\n.*return...` | Dead code — return sau wp_send_json_success/error |
| LES-352 | HIGH | `'orders_count'\s*=>\s*0` | Customer list returns hardcoded orders_count=0, total_spent= |
| LES-353 | HIGH | `get_option\s*\(\s*'wezone_sku_counter'` | SKU counter race condition — concurrent generate_sku can pro |
| LES-354 | HIGH | `add_submenu_page\s*\(\s*'wezone-admin'\s...` | Duplicate submenu registration — AdminPage and VoucherTempla |
| LES-355 | HIGH | `p\.image\s+AS\s+product_image` | ReturnController get_items references wrong column p.image — |
| LES-359 | HIGH | `tracked_views|did_action|\$this->tracked...` | Event tracker must not double-count with overlapping hooks |
| LES-360 | HIGH | `SELECT.*products.*WHERE.*date|SELECT COU...` | Aggregate product stats must check existing before bulk inse |
| LES-361 | HIGH | `wezone_is_active` | Plugin boot() must call wezone_is_active() guard |
| LES-376 | HIGH | `\$price\s*<=\s*0|\$price\s*===\s*0\.0|pr...` | CartEngine resolvePrice returns 0.0 for non-existent product |
| LES-377 | HIGH | `stock_quantity|wz_check_stock|in_stock.*...` | Cart merge() must check stock — combined qty can exceed avai |
| LES-378 | HIGH | `fresh_price.*resolvePrice|resolvePrice.*...` | Cart recalculate() must refresh prices from DB — stale price |
| LES-399 | HIGH | `current_time\s*\(\s*'mysql'` | Inconsistent timestamp functions across Order classes |
| LES-404 | HIGH | `new\s+CouponEngine\(\)` | wz_coupon_engine() must use Container::make() — inconsistent |
| LES-414 | HIGH | `'default'\s*=>\s*'#[0-9a-fA-F]{3,6}'` | Config Array Hardcoded Colors |
| LES-436 | HIGH | `get_json_params\(\).*\['(?:ids|items|ord...` | REST endpoint accepts unbounded array without size limit |
| LES-442 | HIGH | `JOIN\s+[\{$]*wpdb->posts.*product` | JOIN on wp_posts to get product name — Wezone Commer product |
| LES-467 | HIGH | `get_option.*hour.*max.*min.*strtotime` | Cron schedule option type validation missing |
| LES-487 | HIGH | `document\.cookie\s*=.*consent.*(?!nonce)` | Consent banner JS modifies cookies without nonce â€” CSRF ri |
| LES-494 | HIGH | `public function boot\(\s*\)\s*:\s*void\s...` | Plugin boot() must call wezone_is_active() guard before init |
| LES-338 | SUGG | `implements\s+\w+Interface` | Adapter class missing interface contract — breaks Liskov sub |
| LES-339 | SUGG | `function\s+email\s*\(` | AdapterManager missing lazy accessors for Email, ProductRela |
| LES-343 | SUGG | `^require\s+__DIR__\s*\.\s*'/functions/` | Adapter functions.php uses require instead of require_once f |
| LES-344 | SUGG | `sprintf\s*\(\s*'Thanh toan` | WZ_Gateway hardcoded Vietnamese string without __() i18n |
| LES-406 | SUGG | `static\s+\$[a-z_]+\s*=\s*null` | Helper singleton functions not resettable — breaks unit test |
