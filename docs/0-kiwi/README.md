# Kiwi Docs — Priority Roadmap

## Status: R0-R8 DONE → Commercial + R9-R27 pending

---

## Folder Structure (theo thứ tự ưu tiên code)

```
0-kiwi/
├── done-R0-R8/                    ← ĐÃ HOÀN THÀNH (không cần đọc lại)
│   ├── agent-reasoning.md         # Tổng quan kiến trúc
│   ├── agent-code.md              # Template engine plan
│   └── agent-reasoning-R0→R8.md   # 9 phases đã implement
│
├── A-commercial-foundation/       ← ƯU TIÊN #1 (không có → không bán được)
│   ├── KIWI-CORE-PLUGIN-SEPARATION.md  # Core/Plugin tách, FAQ 1-10
│   ├── KIWI-COMMERCIAL-PLAN.md         # Business model, pricing, GTM
│   └── KIWI-INSTALLATION-GUIDE.md      # npm/VS Code/pip install flow
│
├── B-intelligence-core/           ← ƯU TIÊN #2 (Kiwi thông minh hơn)
│   └── agent-reasoning-ROADMAP-R9-R15.md  # R9-R15 plans
│
├── C-extension/                   ← ƯU TIÊN #3 (distribution channel)
│   └── KIWI-VSCODE-EXTENSION-PLAN.md     # 5 phases extension
│
├── D-senior-reasoning/            ← ƯU TIÊN #4 (nâng chất lượng)
│   └── agent-reasoning-ROADMAP-R16-R20.md # R16-R21 plans
│
└── E-staff-level/                 ← ƯU TIÊN #5 (nice-to-have)
    └── agent-reasoning-ROADMAP-R22-R27.md # R22-R27 plans
```

---

## Thứ tự code (29 tasks)

### NHÓM A: Nền tảng thương mại (~19 days)

**Nguyên tắc bảo vệ IP xuyên suốt:**
```
Source (GitHub Private) → Compile (Nuitka) → Encrypt lessons → Ship binary
User KHÔNG BAO GIỜ thấy: source Python, lessons .md, reasoning logic
User CHỈ nhận: compiled binary + encrypted lessons DB + license check
```

| # | Task | Effort | IP Protection |
|---|------|--------|---------------|
| 1 | Core/Plugin Separation | 5 days | Tách rõ public vs private code |
| 2 | Classify 740 Lessons (universal vs wezone) | 2 days | Xác định gì ship, gì giữ |
| 3 | Generic Plugin + 400+ starter lessons | 2 days | Universal lessons = ship, Wezone = giữ |
| 4 | Usage Tracking + Dashboard | 3 days | Metrics local, không gửi ra ngoài |
| 5 | Freemium Gating | 2 days | License tier enforcement |
| 6 | CLI Packaging (kiwi init/serve/dashboard) | 3 days | Entry point cho user |
| 7 | Build Pipeline: Compile + Encrypt + License | 2 days | **GATE CUỐI: mã hóa mọi thứ trước khi ship** |

**Khi đến tay user:**
```
npm install -g @kiwi-ai/cli
├── kiwi.exe              ← Compiled binary (không decompile được)
├── lessons.kiwi          ← Encrypted DB (không đọc được)
└── License check         ← 1 key = 1 máy, heartbeat 7 ngày
```

### NHÓM B: Intelligence Core (~5 weeks)
| # | Task | Effort |
|---|------|--------|
| 6 | R9 — Reflective Learning | 1 week |
| 7 | R13 — Autonomous Fix Loop | 3 days |
| 8 | R11 — Predictive Prefetch | 3 days |
| 9 | R15 — Teaching Mode | 3 days |
| 10 | R12 — Cross-Project Transfer | 1 week |
| 11 | R10 — Multi-Model Routing | 1 week |
| 12 | R14 — Spec Synthesis | 1 week |

### NHÓM C: Extension + Universal Support (~4.5 weeks)
| # | Task | Effort |
|---|------|--------|
| 13 | LSP Server: Universal Agent Support (mọi IDE/agent) | 1 week |
| 14 | Extension Phase 1: Dashboard Panel | 1 week |
| 15 | Extension Phase 2: Inline Warnings | 1 week |
| 16 | Extension Phase 3: Code Actions | 1 week |
| 17 | Extension Phase 4: Trust Indicators | 3 days |

### NHÓM D: Senior Reasoning (~5 weeks)
| # | Task | Effort |
|---|------|--------|
| 17 | R16 — Task Decomposition | 1 week |
| 18 | R20 — Autonomous Failure Learning | 1 week |
| 19 | R21 — Learning from the Senior | 1 week |
| 20 | R17 — Edge Case Reasoning | 1 week |
| 21 | R18 — Creative Alternatives | 1 week |
| 22 | R19 — Requirement Inference | 3 days |

### NHÓM E: Staff Level (~5 weeks)
| # | Task | Effort |
|---|------|--------|
| 23 | R22 — Real-time Learning | 3 days |
| 24 | R23 — Code Review Mode | 1 week |
| 25 | R24 — Architecture Reasoning | 1 week |
| 26 | R25 — Test Strategy | 3 days |
| 27 | R26 — Multi-Agent Collaboration | 1 week |
| 28 | R27 — Intent Prediction | 3 days |

---

## Target

```
$50K ARR = chỉ cần NHÓM A + B + C (~3 tháng)
$1M ARR  = full A + B + C + D + E (~5.5 tháng)
```

## Thành tựu khi hoàn thành

```
R0-R8 (done):  Token 10,000 → 3,000/session, local 30%
After A+B+C:   Token → 1,000/session, local 80%, $50K ARR possible
After D+E:     Token → 300/session, local 92%, staff-level intelligence
```