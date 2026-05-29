# KIWI CONTEXT RELIABILITY PLAN

> Kế hoạch fix 3 hạn chế của `kiwi_context`. Trọng tâm: biến việc "rớt chế độ" thành **quan sát được**, và giảm phụ thuộc vào khớp-keyword chính xác.

**Trạng thái:** PENDING
**Phạm vi sửa:** `.claude/kiwi/agent/context.py` (chính) + `.claude/kiwi/mcp_server.py` (mô tả tool) + `.claude/kiwi/hooks/pre_edit.py` (tùy chọn)
**Lưu ý:** `.claude/kiwi` là git submodule — mọi thay đổi commit trong submodule, sau đó bump ở repo cha.
**Không phá API:** chỉ thêm field `degraded` vào dict trả về và mở rộng tham số `files`/`target_file`. Các caller cũ vẫn chạy.

---

## Bối cảnh — 3 hạn chế hiện tại

| # | Hạn chế | Vị trí |
|---|---------|--------|
| 1 | Semantic/embedding, contextual rules, learned conventions, db_scores, anomalies đều bọc `try/except` và **fail im lặng** (chỉ log stderr). Thiếu model hay DB lỗi → `kiwi_context` rớt về chấm điểm cơ bản nhưng **không báo** người dùng. | [context.py:245](../../agent/context.py#L245), [context.py:310](../../agent/context.py#L310), [context.py:396](../../agent/context.py#L396), [context.py:217](../../agent/context.py#L217), [context.py:342](../../agent/context.py#L342) |
| 2 | Chất lượng phụ thuộc lesson viết đúng + `_TASK_CATEGORY_MAP` có keyword. Task mơ hồ / từ chưa map → `task_categories` rỗng → **rớt về severity-only**, kém liên quan. | [context.py:12](../../agent/context.py#L12), [context.py:141](../../agent/context.py#L141) |
| 3 | Deep signal (+30 điểm) chỉ chạy khi truyền `target_file`. Gọi chỉ với `task` → **mất boost khớp nội dung**. | [context.py:493](../../agent/context.py#L493), [context.py:185](../../agent/context.py#L185) |

---

## FIX 1 — Fail im lặng → báo chế độ giảm

### 1.1 Thêm class `_Health` (đầu context.py)

```python
class _Health:
    """Track subsystem status so degradation is visible, not silent."""
    def __init__(self):
        self.subsystems = {}
    def ok(self, name):               self.subsystems[name] = {"status": "ok"}
    def degraded(self, name, why):    self.subsystems[name] = {"status": "degraded", "reason": why}
    def unavailable(self, name, why): self.subsystems[name] = {"status": "unavailable", "reason": why}
    def report(self):
        return [{"name": k, **v} for k, v in self.subsystems.items() if v["status"] != "ok"]
```

### 1.2 Mỗi helper nhận `health=None`, phân biệt 3 trạng thái

Áp cho: `_get_semantic_scores`, `_get_contextual_rules`, `_get_learned_conventions`, `_get_db_scores`, `_get_pending_anomalies`.

```python
def _get_semantic_scores(task, patterns, health=None):
    if not task or len(task) < 5:
        if health: health.degraded("semantic", "task quá ngắn (<5 ký tự)")
        return {}
    try:
        from learning.embeddings import embed_pattern, semantic_similarity, ...
        ...  # logic cũ giữ nguyên
        if health: health.ok("semantic")
        return scores
    except ImportError as e:
        if health: health.unavailable("semantic", f"thiếu deps embedding: {e}")
        return {}
    except Exception as e:
        if health: health.degraded("semantic", str(e))
        return {}
```

**Mấu chốt:** `unavailable` (thiếu thư viện/DB) ≠ `ok` trả rỗng (không có match). Đây là điều output hiện tại không phân biệt được.

### 1.3 build_context: tạo health, truyền vào, thêm vào dict trả về

```python
health = _Health()
# ... truyền health=health vào từng helper ...
return {
    ...,
    "degraded": health.report(),   # field MỚI
}
```

### 1.4 Surface lên ĐẦU output (cả 2 formatter)

Thêm vào đầu [_format_full](../../agent/context.py#L597) và [_format_compact](../../agent/context.py#L567):

```python
if ctx.get("degraded"):
    lines.append("⚠️ **Kiwi chạy chế độ giảm** — một số tín hiệu không khả dụng:")
    for d in ctx["degraded"]:
        lines.append(f"  - {d['name']}: {d['status']} ({d.get('reason','')})")
    lines.append("")
```

**Kết quả:** thiếu `sentence-transformers` hay DB lỗi → output ghi rõ, Claude biết đang thiếu tín hiệu nào.

---

## FIX 2 — Task mơ hồ / keyword chưa map

Ba lớp phòng thủ, áp trong [build_context](../../agent/context.py#L490) sau khi có `task_categories` + `semantic_scores`.

### 2a. Backfill category từ semantic khi keyword map trượt

```python
if task and not task_categories and semantic_scores:
    sem_cats = {}
    for p in patterns:
        if p["id"] in semantic_scores:
            sem_cats[p["category"]] = sem_cats.get(p["category"], 0) + semantic_scores[p["id"]]
    task_categories = {c for c, _ in sorted(sem_cats.items(), key=lambda x: -x[1])[:3]}
    if task_categories:
        health.degraded("task_mapping", "không khớp keyword — category suy từ semantic")
```

### 2b. Map keyword động từ tags (lesson mới tự mở rộng coverage)

```python
def _build_dynamic_category_map(patterns):
    m = {}
    for p in patterns:
        for tag in (p.get("tags") or []):
            m.setdefault(tag.lower(), set()).add(p["category"])
    return m
```

Gộp kết quả vào [_map_task_to_categories](../../agent/context.py#L141) — không còn phụ thuộc 100% dict hardcode.

### 2c. Cảnh báo rõ khi cả hai trượt

```python
if task and not task_categories:
    health.degraded("task_mapping",
        "task khớp 0 category & 0 semantic — chỉ xếp theo severity; "
        "nên mô tả rõ hơn hoặc truyền files=/target_file=")
```

---

## FIX 3 — Không có target_file → mất +30 signal

Hiện `files` chỉ dùng [lọc extension](../../agent/context.py#L682). Cho phép `target_file` **và** `files` (đường dẫn thật) chạy [_detect_signals_deep](../../agent/context.py#L185).

```python
import os
signal_files = [f for f in ([target_file] + (files or [])) if f and os.path.exists(f)]
relevant_ids = {}
for sf in signal_files:
    relevant_ids.update(_detect_signals_deep(sf, patterns))
relevant_ids = relevant_ids or None

if not signal_files:
    health.degraded("deep_signal",
        "không có file thật — mất +30 boost khớp nội dung; "
        "truyền target_file= khi sửa code có sẵn")
```

### Bổ trợ
- Siết mô tả tool trong [mcp_server.py:2178](../../mcp_server.py#L2178): nhắc luôn truyền `target_file` khi edit file tồn tại.
- (Tùy chọn) [pre_edit.py](../../hooks/pre_edit.py) đã biết `file_path` → ghi vào state để MCP tự suy `target_file` khi bị bỏ trống.

---

## FIX 4 — Lesson có hợp dự án không? (project-signature filtering) — trả lời Q2

### Vấn đề
[_matches_platform](../../scanner/loader.py#L70) + [_matches_scope_type](../../scanner/loader.py#L94) chỉ lọc theo `platform` (wp/nextjs) và `scope` (theme/plugin). **Không kiểm tra dự án có thực sự dùng Wezone Commerce hay không.** Hệ quả: WP shop dùng WooCommerce vẫn bị nạp `wezone-api` + `woocommerce-migration` → cảnh báo sai hàng loạt (vd "dùng `wz_get_product` thay `wc_get_product`" trên dự án cố tình dùng WooCommerce).

Trong 611 lessons: ~450 universal (php-security, performance, nextjs-react, python...) áp mọi dự án; ~290 Wezone-specific chỉ đúng cho dự án Wezone.

### Giải pháp — Project Fingerprint + `requires:` frontmatter

**4.1 Detector dấu hiệu dự án** — file mới `scanner/project_profile.py`:
```python
def detect_stack(project_path):
    """Trả về set 'capabilities' dự án thực sự có."""
    caps = set()
    # composer.json deps
    comp = _read_json(project_path, "composer.json")
    if "woocommerce/woocommerce" in _deps(comp): caps.add("woocommerce")
    # function prefix trong code (grep nhanh, cap số file)
    if _grep_any(project_path, r"\bwz_[a-z_]+\("): caps.add("wezone-commerce")
    if _grep_any(project_path, r"\bwc_[a-z_]+\(|WC\(\)"): caps.add("woocommerce")
    # package.json deps
    pkg = _read_json(project_path, "package.json")
    deps = _deps(pkg)
    if "next" in deps: caps.add("nextjs")
    if "@supabase/supabase-js" in deps: caps.add("supabase")
    if "react" in deps: caps.add("react")
    return caps  # cache vào .kiwi/project_profile.json, TTL theo mtime
```

**4.2 Frontmatter `requires:` cho lesson** (optional, mặc định = universal):
```yaml
# lessons/wezone-api/LES-004.md
requires: wezone-commerce        # chỉ load khi dự án có wezone-commerce
conflicts: woocommerce           # bỏ nếu dự án dùng woocommerce
```
Lesson **không** có `requires:` → universal, luôn load (giữ nguyên hành vi cũ → không phá gì).

**4.3 Loader lọc theo caps** — sửa [load_patterns](../../scanner/loader.py#L170):
```python
caps = detect_stack(project_path) if project_path else None
...
if caps is not None:
    req = fm.get("requires")
    if req and req not in caps:        # cần capability mà dự án không có
        continue
    conf = fm.get("conflicts")
    if conf and conf in caps:          # xung đột với stack dự án
        continue
```

**4.4 Báo cho user khi lọc lớn** (nối vào `_Health` của Fix 1):
```python
if caps is not None:
    health.ok("project_filter")  # + ghi log: "Loaded 318/611 lessons for stack: {caps}"
```

### Phân loại để classify (one-off task)
Chạy script gắn `requires:`/`conflicts:` cho ~290 lesson Wezone-specific. Bảng phân loại đầy đủ đã có ở [A2-CLASSIFY-LESSONS.md](./A-commercial-foundation/A2-CLASSIFY-LESSONS.md). Universal giữ nguyên (không cần đụng).

---

## FIX 5 — Nạp đủ lesson dự án khi chạy lần đầu (first-run onboarding) — trả lời Q3

### Vấn đề
3 nguồn làm `kiwi_context` "thông minh theo dự án" — [db_scores](../../agent/context.py#L217), [project_profile](../../agent/context.py#L425), [learned_conventions](../../agent/context.py#L396) — đều **rỗng cho tới khi user scan/learn vài lần**. Lần đầu, `kiwi_context` chỉ dựa category map + severity + semantic → chưa có tín hiệu riêng dự án. Hiện chưa có 1 lệnh gộp.

### Giải pháp — 1 lệnh `kiwi init` (hoặc 1 nút "Initialize")

Pipeline tuần tự, hiển thị tiến độ (khớp luồng đã mô tả ở [KIWI-INSTALLATION-GUIDE.md](./A-commercial-foundation/KIWI-INSTALLATION-GUIDE.md)):

| Bước | Gọi | Tạo ra dữ liệu cho |
|------|-----|-------------------|
| 1. Detect stack | `detect_stack()` (Fix 4) | project_profile + bộ lọc caps |
| 2. Học pattern dự án | [kiwi_learn_from_folder](../../mcp_server.py) `auto_approve=false` | lesson đặc thù dự án |
| 3. Duyệt đề xuất | `kiwi_review_suggestions` → `kiwi_approve_suggestion` | chốt lesson (lọc rác) |
| 4. Scan seed | `kiwi_scan` 1 vòng | `db_scores` + `project_profile` history |
| 5. Bật học phiên | `kiwi_learn_session` (định kỳ) | `learned_conventions` (style/binding) |
| 6. Ghi anchor + hook | Fix 7 | agent luôn gọi `kiwi_context` |

**5.1 Báo trạng thái "cold vs warm"** — thêm vào output `kiwi_context` (qua `_Health`):
```
ℹ️ Kiwi mới khởi tạo (cold start): chưa có lịch sử vi phạm / convention dự án.
   Đang xếp hạng theo: category + severity + semantic.
   Chạy "Initialize Kiwi" (nút sidebar) để nạp đủ → tăng độ chính xác.
```
→ Đây chính là phần Fix 1 surface "chế độ giảm", nay phân biệt thêm *cold-start* (chưa onboard) vs *degraded* (lỗi subsystem).

**5.2 Idempotent** — chạy lại `kiwi init` không nhân đôi lesson (dedup theo pattern hash), không ghi trùng anchor.

---

## FIX 6 — Mọi lệnh chỉ cần nút bấm trong extension (button-only UX)

Mục tiêu: **user không bao giờ phải gõ CLI/MCP**. Mọi tool có 1 nút tương ứng. Mở rộng [C2-USER-FRIENDLY-UX-PLAN.md](./C-extension/C2-USER-FRIENDLY-UX-PLAN.md).

### 6.1 Ánh xạ lệnh → nút (bổ sung các nút còn thiếu)

| Tác vụ (CLI/MCP) | Nút trong extension | Vị trí |
|------------------|---------------------|--------|
| `kiwi init` / onboarding (Fix 5) | **"Initialize Kiwi"** (nút lớn khi chưa init) | Sidebar welcome view |
| `kiwi_context` | *(không cần nút — agent tự gọi, xem Fix 7)* | — |
| `kiwi_scan` | "Scan Project" | Status bar + sidebar |
| `kiwi_check` | tự chạy on-save | (ambient) |
| `kiwi_fix` apply | "Apply Fix" CodeLens | trên dòng vi phạm |
| `kiwi_fix` preview | "Preview" CodeLens → diff editor | trên dòng vi phạm |
| `kiwi_learn_from_folder` | "Learn from Codebase" | sidebar (trong wizard init) |
| `kiwi_review_suggestions` + approve/reject | **"Review Suggestions"** (tree có nút ✓/✗ mỗi item) | sidebar view mới |
| `kiwi_dismiss` | "Dismiss" (right-click diagnostic) | context menu |
| `kiwi_trends` | "Trends" panel | sidebar |
| `kiwi_deploy` | "Deploy" quickpick (target/mode) | command palette + status bar |
| `kiwi_add` | "Add Lesson from Selection" | right-click |
| Bật/tắt project filter (Fix 4) | toggle "Stack filter: ON" | status bar |

### 6.2 Welcome View khi chưa init
Khi `.kiwi/` chưa tồn tại → sidebar hiện 1 nút lớn **"Initialize Kiwi"** + 3 dòng mô tả. Click → chạy Fix 5 pipeline trong `withProgress`. Xong → tự chuyển sang violations tree.

### 6.3 Review Suggestions view (mới — quan trọng cho Q3)
View thứ 3 trong activity bar Kiwi: `kiwiSuggestions`.
- Tree mỗi item = 1 suggested lesson (title + severity + occurrences).
- Inline button ✓ (approve → `kiwi_approve_suggestion`) / ✗ (reject → `kiwi_reject_suggestion`).
- Approve → `bridge.invalidate_patterns()` + refresh.
- LSP endpoint mới: `kiwi/listSuggestions`, `kiwi/approveSuggestion`, `kiwi/rejectSuggestion`.

File mới: `vscode/src/providers/suggestionsTree.ts`, sửa [server.py](../../lsp/server.py) + [bridge.py](../../lsp/bridge.py).

### 6.4 Nguyên tắc
- Mọi nút có default hợp lý → 1 click là chạy, không hỏi nhiều bước (trừ destructive: deploy production, reset → confirm 1 lần).
- Tác vụ chạy lâu → `withProgress` + cancel token.
- Không có nút nào dẫn user ra terminal.

---

## FIX 7 — Agent ưu tiên đọc Kiwi đầu tiên, không quên gọi `kiwi_context`

### Vấn đề
Hiện chỉ dựa "smart detection" (Claude tự nhớ) + PostToolUse scan *sau khi đã ghi*. [pre_edit.py](../../hooks/pre_edit.py) có logic **chặn trước** nhưng **không được đăng ký** trong [settings.local.json](../../../settings.local.json#L115) → thực tế không chặn. Cần cơ chế cứng + đa lớp, hoạt động cả với agent không phải Claude Code.

### Giải pháp — 4 lớp (defense in depth)

**Lớp 1 — Anchor trong CLAUDE.md / AGENTS.md (context-level, mạnh nhất).**
`kiwi init` tự chèn 1 block đánh dấu vào đầu CLAUDE.md của dự án (tạo AGENTS.md nếu chưa có CLAUDE.md):
```markdown
<!-- KIWI:BEGIN (auto-managed, do not edit) -->
## ⛔ Kiwi Gate — đọc trước khi code
Trước khi Write/Edit bất kỳ file .php/.css/.js/.ts/.tsx/.jsx:
→ BẮT BUỘC gọi `kiwi_context(task=..., target_file=...)` TRƯỚC.
Bỏ qua = code bị PreToolUse hook chặn.
<!-- KIWI:END -->
```
- Idempotent: tìm marker `KIWI:BEGIN/END`, replace; không có thì chèn đầu file.
- Vì CLAUDE.md/AGENTS.md được nạp vào context mỗi phiên → agent thấy luật này trước tiên.

**Lớp 2 — PreToolUse hard gate (đăng ký [pre_edit.py](../../hooks/pre_edit.py)).**
`kiwi init` ghi vào `.claude/settings.json` của dự án:
```json
"hooks": {
  "PreToolUse": [{
    "matcher": "Write|Edit",
    "hooks": [{ "type": "command",
      "command": "python .kiwi/hooks/pre_edit.py" }]
  }]
}
```
Sửa [pre_edit.py](../../hooks/pre_edit.py) cho khớp state file thật:
- Hiện đọc `.context_state.json` nhưng tracker ghi `.kiwi_context_state.{conv}.json` ([track_kiwi_context.py:52](../../hooks/track_kiwi_context.py#L52)) → **bug: 2 file khác nhau**. Phải thống nhất: pre_edit đọc đúng file per-conversation.
- Cho qua file không phải code; chặn file code khi chưa gọi `kiwi_context` trong phiên → trả message hướng dẫn.
- Có TTL (vd state cũ > 1h coi như hết hạn) để tránh "đã gọi 1 lần rồi free cả ngày".

**Lớp 3 — Cross-agent rule files.**
`kiwi init` ghi thêm (nếu phát hiện agent tương ứng):
- `.cursor/rules/kiwi.mdc` (Cursor)
- `.windsurfrules` (Windsurf)
- `AGENTS.md` (chuẩn chung nhiều agent) — cùng nội dung anchor Lớp 1.

**Lớp 4 — MCP tool description + naming.**
Giữ mô tả [kiwi_context](../../mcp_server.py#L2178) mở đầu bằng "DÙNG TRƯỚC KHI CODE" + bổ sung nhắc truyền `target_file`. (Yếu nhất, chỉ là gợi ý — không dựa vào lớp này một mình.)

### Bảng hiệu lực

| Lớp | Cơ chế | Cứng/Mềm | Agent áp dụng |
|-----|--------|----------|---------------|
| 1 | Anchor CLAUDE.md/AGENTS.md | Mềm (context) | Mọi agent đọc context |
| 2 | PreToolUse block | **Cứng (chặn ghi)** | Claude Code |
| 3 | Cursor/Windsurf rules | Mềm | Cursor, Windsurf |
| 4 | MCP description | Mềm | Mọi MCP client |

→ Lớp 2 là bảo hiểm cứng cho Claude Code; Lớp 1+3 phủ agent khác; cả 4 cùng chạy nên quên ở lớp này thì lớp khác bắt.

---

## Thứ tự triển khai

1. **Fix 1** — `_Health` + sửa 5 helper + build_context + 2 formatter. (Nền tảng, các fix sau dùng `health`.)
2. **Fix 2** — backfill semantic + dynamic map + cảnh báo.
3. **Fix 3** — mở rộng signal_files + cảnh báo + sửa mô tả tool.
4. **Fix 7** — anchor writer + đăng ký + sửa bug state file [pre_edit.py](../../hooks/pre_edit.py) (độc lập, làm sớm vì giá trị cao).
5. **Fix 4** — `project_profile.py` + `requires:`/`conflicts:` + lọc loader + classify 290 lesson.
6. **Fix 5** — pipeline `kiwi init` gộp + cold-start banner (phụ thuộc Fix 4 + Fix 7).
7. **Fix 6** — nút extension + welcome view + suggestions tree (phụ thuộc Fix 5 có pipeline để gọi).

## Verify

```powershell
$env:PYTHONUTF8=1; cd .claude/kiwi; python -m pytest tests/test_context_upgrade.py -v
```

- [ ] Caller cũ (chỉ `task`) vẫn chạy, không lỗi.
- [ ] Thiếu embedding deps → output có dòng `⚠️ Kiwi chạy chế độ giảm` ghi `semantic: unavailable`.
- [ ] Task lạ ("làm cái nút bấm") không map keyword → vẫn ra category qua semantic HOẶC cảnh báo task_mapping.
- [ ] Truyền `files=` đường dẫn thật → `signals_detected > 0`.
- [ ] `degraded` rỗng khi mọi subsystem ok.

## Ước lượng

| Fix | Effort |
|-----|--------|
| 1 — Health + observability | ~2h |
| 2 — Task mapping resilience | ~2h |
| 3 — Signal từ files | ~1h |
| 7 — Anchor writer + PreToolUse gate + sửa bug state file | ~4h |
| 4 — project_profile + requires/conflicts + lọc loader | ~4h |
| 4b — Classify ~290 lesson (one-off) | ~6h |
| 5 — Pipeline `kiwi init` + cold-start banner | ~5h |
| 6 — Nút extension + welcome view + suggestions tree | ~3 ngày |
| Test + bump submodule | ~2h |
| **Tổng (chưa kể Fix 6)** | **~26h** |

---

## Hạn chế còn lại & cách đo hiệu quả

> Plan này KHÔNG làm Kiwi "hoàn hảo". Nó đưa Kiwi từ *"mạnh khi ấm, lặng lẽ rớt khi lạnh"* sang *"mạnh khi ấm, rớt CÓ BÁO khi lạnh, và khó quên hơn"*. Mục này liệt kê thẳng phần plan KHÔNG giải quyết, để không tự lừa mình.

### Hạn chế plan KHÔNG đóng được

| # | Hạn chế còn lại | Vì sao plan không giải | Hướng xử lý thật |
|---|-----------------|------------------------|------------------|
| R1 | **Enforcement đa-agent vẫn mềm.** Chỉ Lớp 2 (PreToolUse) chặn cứng, và CHỈ cho Claude Code. Cursor/Windsurf chỉ có rule file → vẫn ghi file được mà không gọi `kiwi_context`. | Các agent ngoài Claude Code không có cơ chế hook chặn ghi tương đương. | Chấp nhận: mục tiêu "không bao giờ quên" chỉ đảm bảo cho Claude Code. Agent khác = best-effort. Cần nói rõ trong doc cho user. |
| R2 | **Hard gate kiểm "đã gọi trong phiên", không phải "đã gọi cho file/task này".** Gọi 1 lần cho task A → mở khoá ghi mọi file. | Siết theo file/task gây ma sát lớn (chặn mọi edit → agent loop, hỏng UX). | Cân nhắc gate theo (file_path → đã có trong `relevant_ids` của lần `kiwi_context` gần nhất chưa). Đánh đổi UX, cần thử nghiệm. |
| R3 | **Lọc theo stack ≠ lesson chính xác.** Fix 4 làm lesson *liên quan* hơn, nhưng lesson vẫn là regex → vẫn false-positive nội bộ. | Độ chính xác lesson là vấn đề chất lượng lesson, không phải lọc. | Dựa vào [kiwi_confidence](../../mcp_server.py) auto-demote lesson noisy + AST-verified lessons (đã có 1 số). Đo FP rate (xem dưới). |
| R4 | **Classify ~290 lesson là thủ công, không validate.** Gắn sai `requires:` → lesson biến mất âm thầm. | Không có ground-truth để verify tự động. | Sau classify: chạy scan dự án Wezone (phải giữ nguyên số violation) + 1 dự án WooCommerce mẫu (phải giảm). Regression test 2 chiều. |
| R5 | **Tự sửa CLAUDE.md user (Fix 7 Lớp 1) là xâm lấn.** Ghi marker vào file user sở hữu → git noise, rủi ro đụng nội dung. | Đánh đổi cố hữu giữa "agent thấy luật" vs "không động vào file user". | Idempotent + chỉ ghi block có marker + hỏi xác nhận lần đầu. Cho phép opt-out qua config. |
| R6 | **Phụ thuộc embedding nặng.** Fix 1 báo "degraded" trung thực, nhưng `sentence-transformers` là dep lớn → nhiều máy chạy thiếu vĩnh viễn. | Báo cáo trung thực ≠ tính năng còn hoạt động. | Cân nhắc fallback embedding nhẹ (hash/tf-idf) khi thiếu model, để semantic không "tắt hẳn". |
| R7 | **Cold-start vẫn yếu dù có banner.** Lần đầu chưa có history/convention → ranking kém hơn. Banner chỉ *báo*, không *sửa*. | `db_scores`/`learned_conventions` cần dữ liệu tích luỹ. | `kiwi init` (Fix 5) rút ngắn cold-start, nhưng vài phiên đầu vẫn dưới mức tối ưu. Đây là bản chất, không né được. |

### Cách đo "có hiệu quả không" (bắt buộc trước khi gọi là xong)

Không có số đo thì "hoàn hảo" vô nghĩa. 4 metric cần thu thập:

| Metric | Đo thế nào | Mục tiêu |
|--------|-----------|----------|
| **False-positive rate** | Đếm `kiwi_dismiss` / tổng violation trên 1 dự án thật, trước vs sau Fix 4. | Giảm rõ rệt trên dự án không-Wezone. |
| **Tỉ lệ agent gọi `kiwi_context`** | Log từ [track_kiwi_context.py](../../hooks/track_kiwi_context.py): số phiên có gọi / số phiên có Write-Edit code. | Tiến tới ~100% với Claude Code (Lớp 2 cứng). |
| **Degraded silent rate** | Đếm số lần `kiwi_context` chạy ở chế độ giảm MÀ không có dòng cảnh báo (phải = 0 sau Fix 1). | = 0. |
| **Cold→warm time** | Số phiên từ `kiwi init` đến khi `db_scores`/`learned_conventions` có dữ liệu. | Càng ngắn càng tốt; `kiwi init` nên rút về ~1 phiên. |

### Regression guard (Fix 4 — không được làm hỏng Wezone)
```powershell
# Trước classify: ghi baseline
$env:PYTHONUTF8=1; cd .claude/kiwi; python -m scanner.cli --theme <wezone-theme> --json > baseline.json
# Sau classify: số violation Wezone PHẢI không đổi (universal + wezone đều load)
python -m scanner.cli --theme <wezone-theme> --json > after.json
# diff baseline vs after = rỗng
```

### Kết luận trung thực
- Plan đóng được: observability, task-mapping resilience, lọc theo dự án, onboarding, UX nút, chống-quên (Claude Code).
- Plan KHÔNG đóng được: enforcement cứng cho agent ngoài Claude Code (R1), gate theo file/task (R2), độ chính xác regex (R3), validate classify tự động (R4).
- Thước đo đúng: **triển khai → đo 4 metric → lặp lại.** Không tuyên bố "hoàn hảo" trước khi có số.