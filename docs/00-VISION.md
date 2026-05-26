# Kiwi Agent — Vision

## Tại sao cần Agent?

Kiwi hiện tại là **passive scanner** — nó chỉ biết tìm pattern khi được gọi. Như một cuốn sổ luật: hữu ích, nhưng cần người đọc và thực thi.

Agent thật sự = sổ luật + thẩm phán + thợ sửa + bộ nhớ.

## Trước vs Sau

| Khía cạnh | Scanner (hiện tại) | Agent (mục tiêu) |
|-----------|-------------------|-------------------|
| **Khi nào chạy** | Khi user gọi CLI/skill | Tự chạy khi file thay đổi, khi deploy, khi cần |
| **Output** | Danh sách violations | Phân tích + đề xuất fix + lý do + priority |
| **Fix** | Không — chỉ detect | Tự fix (replace/template) hoặc đề xuất (llm) |
| **Học hỏi** | Không — static lessons | Track false positives, adjust confidence, suggest new lessons |
| **Giao tiếp** | Text report | Giải thích context, hỏi user khi không chắc |
| **Interface** | CLI subprocess | MCP tools — gọi từ Claude Code, Claude Desktop, CI |
| **Trạng thái** | Stateless | Nhớ scan history, fix outcomes, user preferences |

## 4 Phase Tiến Hóa

```
Phase 1: MCP Server          Phase 2: Auto-Fix
  ┌─────────────┐              ┌─────────────┐
  │ Kiwi thành  │              │ Lesson có   │
  │ MCP tools   │──────────────│ fix field   │
  │ 7 tools     │              │ 3 fix types │
  └─────────────┘              └─────────────┘
         │                            │
         ▼                            ▼
Phase 3: Agent Loop           Phase 4: Learning
  ┌─────────────┐              ┌─────────────┐
  │ Observe →   │              │ SQLite DB   │
  │ Think →     │──────────────│ Confidence  │
  │ Act →       │              │ Trends      │
  │ Verify      │              │ Auto-suggest│
  └─────────────┘              └─────────────┘
```

### Phase 1: MCP Server Foundation
Biến Kiwi thành 7 MCP tools (scan, query, lesson, add, stats, fix, template). Claude Code gọi trực tiếp, không cần skill wrapper hay subprocess. Follow pattern `wezone-rag` server đã có.

**Giá trị:** Kiwi trở thành first-class tool. Mọi MCP client đều dùng được.

### Phase 2: Auto-Fix Engine
Mỗi lesson thêm `fix` field — không chỉ detect mà còn biết cách sửa. 3 cấp: replace (regex), template (inject code), llm (Claude reasoning cho case phức tạp).

**Giá trị:** Từ "đây là lỗi" sang "đây là lỗi, đây là cách sửa, sửa không?"

### Phase 3: Agent Loop
Vòng lặp tự trị: Observe → Think → Act → Verify. Dùng Claude API làm "não", Kiwi tools làm "tay". 3 modes: review (chỉ phân tích), interactive (hỏi trước khi fix), auto (fix hết rồi báo).

**Giá trị:** Kiwi tự chạy, tự fix, tự verify — không cần user điều khiển từng bước.

### Phase 4: Learning & Memory
SQLite lưu scan history, false positives, fix outcomes. Confidence scoring tự động giảm noise. Trend analysis phát hiện regression. Auto-suggest lessons từ fix patterns.

**Giá trị:** Kiwi càng dùng càng thông minh — ít false positives, pattern mới tự đề xuất.

## Nguyên tắc thiết kế

1. **Backward compatible** — CLI, skills, hooks hiện tại vẫn hoạt động 100%
2. **Incremental value** — Mỗi phase ship được độc lập, có giá trị ngay
3. **Reuse > Rewrite** — MCP server gọi code hiện có, không viết lại scanner
4. **Token efficient** — Agent dùng Sonnet cho routine, Opus cho reasoning phức tạp
5. **Safe by default** — Dry-run trước, git stash backup, max fixes per run