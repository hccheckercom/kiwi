
================================================================================
Token Pipeline Performance Benchmark
================================================================================

SMALL (50 tokens)
--------------------------------------------------------------------------------
Operation            Mean       Median     P95        Min        Max       
--------------------------------------------------------------------------------
normalize                0.21ms     0.17ms     0.40ms     0.16ms     0.40ms
validate                 0.22ms     0.20ms     0.29ms     0.19ms     0.29ms
transform                0.46ms     0.45ms     0.59ms     0.41ms     0.59ms
export_css               0.03ms     0.03ms     0.07ms     0.03ms     0.07ms
export_scss              0.05ms     0.04ms     0.08ms     0.04ms     0.08ms
export_php               0.06ms     0.05ms     0.13ms     0.04ms     0.13ms
export_tailwind          0.07ms     0.06ms     0.13ms     0.06ms     0.13ms
export_all               0.21ms     0.00ms     0.00ms     0.00ms     0.00ms
total                    1.10ms     0.00ms     0.00ms     0.00ms     0.00ms

MEDIUM (150 tokens)
--------------------------------------------------------------------------------
Operation            Mean       Median     P95        Min        Max       
--------------------------------------------------------------------------------
normalize                0.49ms     0.49ms     0.61ms     0.44ms     0.61ms
validate                 0.56ms     0.56ms     0.64ms     0.51ms     0.64ms
transform                1.46ms     1.32ms     1.97ms     1.26ms     1.97ms
export_css               0.08ms     0.08ms     0.10ms     0.08ms     0.10ms
export_scss              0.11ms     0.11ms     0.12ms     0.11ms     0.12ms
export_php               0.14ms     0.14ms     0.15ms     0.14ms     0.15ms
export_tailwind          0.19ms     0.18ms     0.26ms     0.16ms     0.26ms
export_all               0.52ms     0.00ms     0.00ms     0.00ms     0.00ms
total                    3.03ms     0.00ms     0.00ms     0.00ms     0.00ms

LARGE (500 tokens)
--------------------------------------------------------------------------------
Operation            Mean       Median     P95        Min        Max       
--------------------------------------------------------------------------------
normalize                1.87ms     1.74ms     2.79ms     1.59ms     2.79ms
validate                 2.74ms     1.85ms    10.93ms     1.74ms    10.93ms
transform                4.27ms     4.03ms     5.89ms     3.88ms     5.89ms
export_css               0.27ms     0.24ms     0.48ms     0.23ms     0.48ms
export_scss              0.35ms     0.33ms     0.56ms     0.32ms     0.56ms
export_php               0.41ms     0.41ms     0.45ms     0.40ms     0.45ms
export_tailwind          0.50ms     0.49ms     0.55ms     0.48ms     0.55ms
export_all               1.54ms     0.00ms     0.00ms     0.00ms     0.00ms
total                   10.41ms     0.00ms     0.00ms     0.00ms     0.00ms

================================================================================
Summary
================================================================================

Scaling (small -> large):
  Token count: 50 -> 500 (10x)
  Total time: 1.10ms -> 10.41ms (9.45x)
  Efficiency: Linear

Bottleneck Analysis (medium size):
  normalize         0.49ms ( 16.2%)
  validate          0.56ms ( 18.5%)
  transform         1.46ms ( 48.2%)
  export_all        0.52ms ( 17.1%)

================================================================================