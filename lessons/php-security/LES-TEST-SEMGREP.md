---
id: LES-TEST-SEMGREP
title: Test Semgrep Integration - wp_mail without nonce
severity: CRITICAL
category: php-security
platform: wp
tags: [plugin, theme]
scan:
  type: semgrep
  pattern: wp_mail(...)
  languages: [php]
  regex_fallback: 'wp_mail\s*\('
---

## Bad

```php
function send_email() {
    wp_mail('test@example.com', 'Subject', 'Body');
}
```

## Good

```php
function send_email() {
    if (!wp_verify_nonce($_POST['nonce'], 'send_email')) {
        return;
    }
    wp_mail('test@example.com', 'Subject', 'Body');
}
```

## Why

Test lesson for Semgrep integration.
