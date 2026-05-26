# LES-472 Migration Plan — Move Payment Gateway Secrets to Constants

## Current State

5 payment gateway files store secrets in `wp_options`:
- [MoMo.php:102](../../wezone-plugins/packages/wezone-checkout/src/Gateways/MoMo.php#L102)
- [VNPay.php](../../wezone-plugins/packages/wezone-checkout/src/Gateways/VNPay.php)
- [ZaloPay.php](../../wezone-plugins/packages/wezone-checkout/src/Gateways/ZaloPay.php)
- [SePay.php](../../wezone-plugins/packages/wezone-checkout/src/Gateways/SePay.php)
- [WZ_ShippingTest.php:53](../../wezone-plugins/packages/wezone-core/tests/Adapter/WZ_ShippingTest.php#L53) (test file)

## Security Risk

**Severity:** MEDIUM (not CRITICAL)
- wp_options visible in DB dumps
- Accessible to any plugin with DB access
- Not encrypted at rest

**Why not CRITICAL:**
- Requires DB access (already compromised)
- No direct user input injection
- Standard practice for WP payment gateways

## Migration Options

### Option 1: Constants in wp-config.php (Recommended)

**Pros:**
- Not in DB dumps
- Not accessible to plugins
- Standard WP practice

**Cons:**
- Requires manual wp-config.php edit per site
- Not portable across environments

**Implementation:**
```php
// wp-config.php
define( 'WEZONE_MOMO_PARTNER_CODE', 'xxx' );
define( 'WEZONE_MOMO_ACCESS_KEY', 'xxx' );
define( 'WEZONE_MOMO_SECRET_KEY', 'xxx' );

// MoMo.php
private function get_secret(): string {
    return defined( 'WEZONE_MOMO_SECRET_KEY' ) 
        ? WEZONE_MOMO_SECRET_KEY 
        : $this->get_option( 'secret_key' ); // fallback
}
```

### Option 2: Encrypt before storing

**Pros:**
- No wp-config.php changes needed
- Portable across environments

**Cons:**
- Encryption key must be stored somewhere (back to square one)
- Performance overhead
- Complex key rotation

**Implementation:**
```php
private function get_secret(): string {
    $encrypted = $this->get_option( 'secret_key_encrypted' );
    return $this->decrypt( $encrypted, WEZONE_ENCRYPTION_KEY );
}
```

### Option 3: Environment variables

**Pros:**
- 12-factor app compliant
- Not in codebase or DB

**Cons:**
- Requires server-level config
- Not standard for WP

## Recommendation

**Use Option 1 (Constants)** with fallback to wp_options for backward compatibility.

## Migration Steps

1. **Add constants support** (backward compatible):
   ```php
   private function get_secret_key(): string {
       if ( defined( 'WEZONE_MOMO_SECRET_KEY' ) ) {
           return WEZONE_MOMO_SECRET_KEY;
       }
       return $this->get_option( 'secret_key', '' );
   }
   ```

2. **Update admin UI** to show:
   - "Using constant from wp-config.php" if defined
   - Input field (disabled) if constant defined
   - Editable input if not defined

3. **Documentation** in README:
   ```markdown
   ## Security: Payment Gateway Secrets
   
   For production, define secrets in wp-config.php:
   
   ```php
   define( 'WEZONE_MOMO_SECRET_KEY', 'your-secret' );
   define( 'WEZONE_VNPAY_HASH_SECRET', 'your-secret' );
   ```
   
   Fallback: secrets stored in wp_options (less secure).
   ```

4. **No breaking changes** — existing sites continue working

## Timeline

- **Priority:** LOW
- **Effort:** 2-3 hours
- **Risk:** LOW (backward compatible)
- **When:** Next security sprint

## Related

- [[LES-472]] — Original lesson
- [[LES-199]] — AI API secrets (similar pattern)
