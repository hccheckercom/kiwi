# Kiwi Dashboard Handoff — 2026-05-24

## Status: Codebase Documentation Complete + Bug Fixes

### Session 2: Codebase Documentation (2026-05-24 Evening)

**Completed:**
- ✅ Fixed tab-switching infinite loading bug (LES-537)
- ✅ Created 7 lessons documenting Kiwi web dashboard patterns
- ✅ Rebuilt Kiwi README index (473 entries)

**Lessons Created:**
1. **LES-537**: useEffect infinite loading on WebSocket reconnect
2. **LES-538**: Hardcoded localhost API URLs in React components
3. **LES-539**: setInterval polling async function without mounted guard
4. **LES-540**: FastAPI WebSocket endpoint missing WebSocketDisconnect handler
5. **LES-541**: FastAPI CORS allow_origins hardcoded localhost ports
6. **LES-542**: WebSocket broadcast catches send errors but doesn't remove dead connections
7. **LES-543**: sys.path.insert without duplicate check
8. **LES-544**: Global singleton manager instance not thread-safe

**Files Analyzed:**
- [api.py](d:\projects\wezone\.claude\kiwi\web\api.py) — FastAPI backend
- [DependencyGraph.tsx](d:\projects\wezone\.claude\kiwi\web\frontend\src\components\DependencyGraph.tsx) — D3 graph component
- [RiskHeatmap.tsx](d:\projects\wezone\.claude\kiwi\web\frontend\src\components\RiskHeatmap.tsx) — Risk visualization
- [ApprovalWorkflow.tsx](d:\projects\wezone\.claude\kiwi\web\frontend\src\components\ApprovalWorkflow.tsx) — Checkpoint approval UI
- [useWebSocket.ts](d:\projects\wezone\.claude\kiwi\web\frontend\src\hooks\useWebSocket.ts) — WebSocket hook
- [App.tsx](d:\projects\wezone\.claude\kiwi\web\frontend\src\App.tsx) — Main app
- [explainability.py](d:\projects\wezone\.claude\kiwi\web\explainability.py) — Violation explainer
- [checkpoint.py](d:\projects\wezone\.claude\kiwi\web\checkpoint.py) — Checkpoint manager

**Bug Fixed:**
- **Tab-switching infinite loading**: Added `hasLoadedRef` to prevent `loadGraph()` from being called again when WebSocket reconnects after tab visibility changes
- Fix location: [DependencyGraph.tsx:7-16](d:\projects\wezone\.claude\kiwi\web\frontend\src\components\DependencyGraph.tsx#L7-L16)

---

## Session 1: D3 Graph Nodes Not Visible (RESOLVED)

### What Works
- ✅ FastAPI backend running on http://localhost:8000
- ✅ React frontend running on http://localhost:5173
- ✅ `/api/plan` endpoint returns mock data successfully (3 nodes)
- ✅ Frontend fetches data without errors
- ✅ `renderGraph()` function executes
- ✅ SVG has valid dimensions (328x498)
- ✅ Console logs confirm: "renderGraph called with 3 nodes"

### Current Issue
**D3 graph nodes are not visible in browser despite successful data loading.**

Console output shows:
```
DependencyGraph.tsx:31 API response: Object
DependencyGraph.tsx:33 Nodes: Array(3)
DependencyGraph.tsx:34 Links: Array(0)
DependencyGraph.tsx:53 renderGraph called with 3 nodes
DependencyGraph.tsx:63 SVG dimensions: 328 x 498
```

But no colored circles (red/orange/blue) appear in the UI.

### Root Cause Found
**Bug in data binding:** Node and label selections were binding to `nodes` array instead of `nodesWithPositions` array.

D3 simulation requires nodes to have `x` and `y` properties. The code created `nodesWithPositions` with initial positions but then bound the original `nodes` array (without positions) to the circle and text elements.

### Fix Applied (Not Yet Tested)
Changed in [DependencyGraph.tsx:97-119](d:\projects\wezone\.claude\kiwi\web\frontend\src\components\DependencyGraph.tsx#L97-L119):

```typescript
// BEFORE (wrong)
.data(nodes)  // Missing x/y properties

// AFTER (correct)
.data(nodesWithPositions)  // Has x/y properties
```

Also added debug logging to verify:
- Node selection size
- Node data content
- Tick events firing
- Position updates

### Next Steps
1. **Refresh browser** to load updated code
2. **Check console** for new debug logs:
   - "Node selection size: 3"
   - "Node data: [...]"
   - "Tick fired, node count: 3, first node pos: {...}"
3. **Verify nodes appear** as colored circles (red/orange/blue)
4. **If still not visible:** Inspect DOM in DevTools to check if `<circle>` elements exist but are hidden by CSS

### Files Modified
- [api.py:150-234](d:\projects\wezone\.claude\kiwi\web\api.py#L150-L234) — Replaced real scanner with mock data (3 tasks: CRITICAL/HIGH/SUGGEST)
- [DependencyGraph.tsx:23-29](d:\projects\wezone\.claude\kiwi\web\frontend\src\components\DependencyGraph.tsx#L23-L29) — Reduced timeout to 60s, max_fixes to 3
- [DependencyGraph.tsx:97-119](d:\projects\wezone\.claude\kiwi\web\frontend\src\components\DependencyGraph.tsx#L97-L119) — Fixed data binding bug (nodes → nodesWithPositions)
- [DependencyGraph.tsx:122-140](d:\projects\wezone\.claude\kiwi\web\frontend\src\components\DependencyGraph.tsx#L122-L140) — Added debug logging

### Mock Data Structure
```json
{
  "tasks": [
    {"id": "task_0", "lesson_id": "LES-001", "severity": "CRITICAL", "file": "header.php", "line": 42},
    {"id": "task_1", "lesson_id": "LES-015", "severity": "HIGH", "file": "footer.php", "line": 18},
    {"id": "task_2", "lesson_id": "LES-023", "severity": "SUGGEST", "file": "style.css", "line": 105}
  ],
  "dependency_graph": {
    "nodes": [
      {"id": "task_0", "label": "LES-001:42", "severity": "CRITICAL", ...},
      {"id": "task_1", "label": "LES-015:18", "severity": "HIGH", ...},
      {"id": "task_2", "label": "LES-023:105", "severity": "SUGGEST", ...}
    ],
    "links": []
  }
}
```

### Color Mapping
- CRITICAL → Red (#ef4444)
- HIGH → Orange (#f59e0b)
- SUGGEST → Blue (#3b82f6)

### Backend Running
Task ID: `b3pjfvcf2` (started with PowerShell, not Bash)
```powershell
cd d:\projects\wezone\.claude\kiwi\web
python api.py
```

### Frontend Running
Vite dev server on http://localhost:5173

### After Fix Verification
Once nodes are visible:
1. Test drag interaction (nodes should be draggable)
2. Verify colors match severity levels
3. Switch back to real data scanning (revert api.py mock data)
4. Optimize scan performance (smaller folder, caching, or progress indicators)

### Known Issues
- Real data scan timeout (120+ seconds for themes/sfvn)
- Need to implement scan caching or incremental scanning
- No links between nodes yet (dependency analysis not implemented)

### Context
User requested: "thử chạy folder thật xem" (try running with real folder)
After timeout issues, switched to mock data to verify UI first.
User then requested: "nên tạo handoff sang session mới thực hiện" (create handoff to new session)
