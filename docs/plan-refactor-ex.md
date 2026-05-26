# Kiwi VSCode Extension: Chat Interface Refactor Plan

## Context

The current Kiwi VSCode Extension uses a traditional form-based UI with a two-column layout (400px form section + flexible results section). User feedback indicates this interface is "very difficult to use" and requests a complete refactor to match Claude Code's chat-based interface.

**User Requirements:**
- 100% like Claude Code chat interface
- Feature selection buttons, command buttons, path selection buttons in chat frame format
- Copy buttons directly in scan results (not requiring extra clicks)
- More intuitive, conversational workflow

**Why This Change:**
- Current form-based UI requires multiple clicks and form field navigation
- Results are stateless - each action clears previous context
- No conversation history or multi-turn interaction support
- Difficult to perform follow-up actions on results
- Copy functionality buried in menus instead of inline

**Current Architecture Strengths to Preserve:**
- Solid MCP client integration (mcpClient.ts) - no changes needed
- Message passing infrastructure (webviewProvider.ts) - minimal changes
- VSCode theme integration working well
- Backend command handlers functioning correctly

---

## Implementation Strategy

### Phase 1: New Chat Component Architecture

Create new chat-focused components that replace the form-based UI:

**1. ChatContainer.tsx** - Main chat layout
- Single-column layout replacing two-column grid
- Manages scroll behavior (auto-scroll to latest message)
- Coordinates MessageList and ChatInput
- Maintains conversation context

**2. MessageList.tsx** - Scrollable conversation history
- Renders array of MessageBubble components
- Auto-scroll to bottom on new messages
- Groups messages by timestamp

**3. MessageBubble.tsx** - Individual message display
- Role-based styling: user (right-aligned, blue) vs assistant (left-aligned, gray)
- Supports multiple content types: text, scan results, context output, lesson cards, deploy status, errors
- Embeds inline action buttons within message content

**4. ChatInput.tsx** - Input bar with quick actions
- Text input supporting slash commands and natural language
- Quick action buttons above input: [Scan] [Context] [Fix] [Check] [Query] [Lesson] [Deploy]
- Inline path autocomplete dropdown
- Submit on Enter, Shift+Enter for newline

**5. InlineActions.tsx** - Reusable action buttons
- Copy button (for code, violations, commands)
- View button (open file in editor)
- Fix button (preview/apply fix)
- Dismiss button (mark as false positive)
- Consistent styling and loading states

### Phase 2: Message Content Components

Transform existing result viewers into message-compatible components:

**1. ScanResultMessage.tsx** (from ResultsViewer.tsx)
- Violations grouped by severity with color coding
- Each violation has inline [Copy] [View] [Fix] [Dismiss] buttons
- Collapsible violation groups
- Summary stats at top

**2. ContextMessage.tsx** (from ContextViewer.tsx)
- Lesson cards with inline [Copy] button
- Expandable code blocks
- Formatted for chat bubble display

**3. LessonMessage.tsx** (from LessonBrowser.tsx)
- Search results as expandable cards
- Inline [Copy] [Insert] buttons
- Compact display in chat flow

**4. DeployMessage.tsx** (from DeployWorkflow.tsx)
- Deploy status with color coding
- Commands with [Copy Commands] button
- Health checks as list
- Deployment URL as clickable link

**5. ErrorMessage.tsx** (new)
- Red-themed message bubble
- Error details in code block
- Retry button if applicable

### Phase 3: State Management Transformation

**1. New Hook: useConversation.ts**
```typescript
interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: MessageContent;
  timestamp: number;
  metadata?: {
    action?: KiwiAction;
    params?: any;
  };
}

interface MessageContent {
  type: 'text' | 'scan' | 'context' | 'lesson' | 'deploy' | 'error';
  data: any;
}
```

Responsibilities:
- Maintain conversation history array
- Add/remove messages
- Get context for follow-up commands (e.g., "fix the first violation" needs previous scan results)
- Optional: persist to VSCode state

**2. Update useKiwi.ts**
- Remove single `result` state, use conversation history instead
- Add `addMessage` function to append to conversation
- Keep `loading`, `error`, `progress` states
- Update `execute()` to append both user message and assistant response

**3. New Utility: inputParser.ts**
```typescript
interface ParsedInput {
  action: KiwiAction;
  path?: string;
  options: {
    severity?: Severity;
    platform?: Platform;
    scopeType?: ScopeType;
    diffOnly?: boolean;
  };
  rawText: string;
}
```

Parsing rules:
- Slash commands: `/scan themes/funilux --severity=CRITICAL`
- Natural language: "scan themes/funilux for critical bugs"
- Extract action, path, and options from input text

### Phase 4: CSS Transformation

**Remove (form-based styles):**
- `.form-section` - two-column grid
- `.results-section` - separate results panel
- `.options-form` - form container
- `.field` - form field styles
- `.path-input-group` - path input with browse button

**Add (chat-based styles):**
```css
.chat-container {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 80px);
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message-bubble {
  max-width: 85%;
  padding: 12px 16px;
  border-radius: 12px;
  word-wrap: break-word;
}

.message-bubble.user {
  align-self: flex-end;
  background: var(--vscode-button-background);
  color: white;
}

.message-bubble.assistant {
  align-self: flex-start;
  background: var(--vscode-input-background);
  border: 1px solid var(--vscode-input-border);
}

.chat-input-container {
  border-top: 1px solid var(--vscode-input-border);
  padding: 16px;
  background: var(--vscode-background);
}

.quick-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.inline-actions {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.inline-action-btn {
  padding: 4px 10px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--vscode-input-border);
  border-radius: 4px;
  cursor: pointer;
  font-size: 11px;
}

.violation-in-message {
  padding: 10px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
  border-left: 3px solid;
  margin: 8px 0;
}

.violation-in-message.critical {
  border-left-color: #f48771;
}
```

**Preserve:**
- VSCode theme variables
- Severity badge colors
- Code block formatting

### Phase 5: App.tsx Refactoring

**Current structure:**
```typescript
<div className="app">
  <header>...</header>
  <main>
    <div className="form-section">
      <ActionSelector />
      <PathInput />
      <OptionsForm />
    </div>
    <div className="results-section">
      <ResultsViewer />
    </div>
  </main>
</div>
```

**New structure:**
```typescript
<div className="app chat-mode">
  <header>
    <h1>Kiwi Scanner</h1>
    <button onClick={clearConversation}>Clear Chat</button>
  </header>
  <ChatContainer>
    <MessageList messages={conversation} />
    <ChatInput onSubmit={handleUserInput} />
  </ChatContainer>
</div>
```

**Changes:**
- Remove ActionSelector, PathInput, OptionsForm imports
- Remove two-column grid layout
- Add ChatContainer with MessageList and ChatInput
- Update state management to use conversation history from useConversation hook
- Handle parsed input from ChatInput component

### Phase 6: Copy Button Implementation

**1. Clipboard Utility (clipboard.ts)**
```typescript
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (err) {
    // Fallback for older browsers
    const textarea = document.createElement('textarea');
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    return true;
  }
}

export function formatViolationForCopy(violation: KiwiViolation): string {
  return `${violation.lesson_id}: ${violation.message}
File: ${violation.file}${violation.line ? `:${violation.line}` : ''}
Severity: ${violation.severity}`;
}
```

**2. CopyButton Component**
```typescript
interface CopyButtonProps {
  content: string;
  label?: string;
  onCopy?: () => void;
}

export function CopyButton({ content, label = 'Copy', onCopy }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);
  
  const handleCopy = async () => {
    const success = await copyToClipboard(content);
    if (success) {
      setCopied(true);
      onCopy?.();
      setTimeout(() => setCopied(false), 2000);
    }
  };
  
  return (
    <button className="inline-action-btn copy-btn" onClick={handleCopy}>
      {copied ? '✓ Copied' : `📋 ${label}`}
    </button>
  );
}
```

### Phase 7: Backend Integration

**webviewProvider.ts - Minimal Changes:**
- Message handlers remain the same (scan, context, fix, dismiss, etc.)
- Add optional conversation context support in messages
- Add new handler: `_handleGetPathSuggestions` for path autocomplete

```typescript
private async _handleGetPathSuggestions(payload: any) {
  const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  const partial = payload.partial;
  
  const files = await vscode.workspace.findFiles(
    `**/${partial}*`,
    '**/node_modules/**',
    20
  );
  
  const suggestions = files.map(uri => 
    path.relative(workspaceRoot, uri.fsPath)
  );
  
  this._postMessage({
    type: 'pathSuggestions',
    data: suggestions
  });
}
```

**mcpClient.ts - No Changes:**
MCP communication layer remains unchanged.

---

## Critical Files to Modify

### New Files to Create:
1. `webview/src/components/chat/ChatContainer.tsx`
2. `webview/src/components/chat/MessageList.tsx`
3. `webview/src/components/chat/MessageBubble.tsx`
4. `webview/src/components/chat/ChatInput.tsx`
5. `webview/src/components/chat/InlineActions.tsx`
6. `webview/src/components/chat/CopyButton.tsx`
7. `webview/src/components/chat/messages/ScanResultMessage.tsx`
8. `webview/src/components/chat/messages/ContextMessage.tsx`
9. `webview/src/components/chat/messages/LessonMessage.tsx`
10. `webview/src/components/chat/messages/DeployMessage.tsx`
11. `webview/src/components/chat/messages/ErrorMessage.tsx`
12. `webview/src/hooks/useConversation.ts`
13. `webview/src/utils/inputParser.ts`
14. `webview/src/utils/pathAutocomplete.ts`
15. `webview/src/utils/clipboard.ts`
16. `webview/src/styles/chat.css`

### Files to Modify:
1. `webview/src/App.tsx` - Major refactor to use ChatContainer
2. `webview/src/hooks/useKiwi.ts` - Update to use conversation history
3. `webview/src/styles/app.css` - Remove form styles, add chat styles
4. `webview/src/types/index.ts` - Add Message, ParsedInput types
5. `src/webviewProvider.ts` - Add path suggestions handler

### Files to Archive (move to legacy/):
1. `webview/src/components/ActionSelector.tsx`
2. `webview/src/components/PathInput.tsx`
3. `webview/src/components/OptionsForm.tsx`
4. `webview/src/components/ResultsViewer.tsx`
5. `webview/src/components/ContextViewer.tsx`
6. `webview/src/components/LessonBrowser.tsx`
7. `webview/src/components/DeployWorkflow.tsx`

---

## Implementation Sequence

### Week 1: Foundation (Days 1-2)
1. Create chat component structure (ChatContainer, MessageList, MessageBubble, ChatInput)
2. Implement useConversation hook for message history
3. Create input parser utility (slash commands + natural language)
4. Update App.tsx with feature flag for gradual migration

### Week 2: Message Components (Days 3-5)
1. Transform ResultsViewer → ScanResultMessage with inline actions
2. Transform ContextViewer → ContextMessage with copy buttons
3. Transform LessonBrowser → LessonMessage
4. Transform DeployWorkflow → DeployMessage
5. Create ErrorMessage component

### Week 3: Interactions (Days 6-8)
1. Implement inline action buttons (Copy, View, Fix, Dismiss)
2. Add copy button functionality with clipboard utility
3. Implement path autocomplete with backend handler
4. Add quick action buttons above input
5. Update CSS for chat layout (remove form styles, add chat styles)

### Week 4: Integration & Testing (Days 9-10)
1. Connect chat components to useKiwi hook
2. Test conversation flow (scan → fix → scan again)
3. Test multi-turn interactions with context
4. Test copy buttons across all message types
5. Fix bugs and polish UI

---

## Verification Steps

### 1. Layout Verification
- [ ] Single column chat layout renders correctly
- [ ] Messages align properly (user right, assistant left)
- [ ] Scroll behavior works (auto-scroll to latest)
- [ ] Input bar stays sticky at bottom
- [ ] Quick action buttons display above input

### 2. Input Parsing
- [ ] Slash commands parse correctly: `/scan themes/funilux`
- [ ] Natural language extracts action and path: "scan themes/funilux for critical bugs"
- [ ] Path autocomplete shows suggestions when typing
- [ ] Quick action buttons pre-fill input with slash command

### 3. Message Display
- [ ] Scan results render as message bubbles with violations grouped by severity
- [ ] Context output shows formatted lesson cards
- [ ] Lesson browser results display as expandable cards
- [ ] Deploy status shows with color coding
- [ ] Error messages display in red-themed bubbles

### 4. Copy Buttons
- [ ] Copy violation details to clipboard
- [ ] Copy lesson code to clipboard
- [ ] Copy deploy commands to clipboard
- [ ] Button shows "✓ Copied" feedback for 2 seconds

### 5. Conversation Context
- [ ] Follow-up commands use previous context
- [ ] "fix the first violation" resolves correctly from last scan
- [ ] "scan again" uses previous path
- [ ] Clear chat button resets conversation history

### 6. Inline Actions
- [ ] [View] button opens file at exact line in editor
- [ ] [Fix] button shows diff preview
- [ ] [Dismiss] button marks as false positive
- [ ] All actions show loading states

### 7. VSCode Integration
- [ ] Theme variables apply correctly (dark/light mode)
- [ ] Extension commands still work (scan folder, check file)
- [ ] Message passing between webview and extension works
- [ ] MCP server communication unchanged

---

## Migration Strategy

### Feature Flag Approach
Add toggle in App.tsx to switch between chat mode and legacy form mode:

```typescript
const [useChatMode, setUseChatMode] = useState(true);

return useChatMode ? (
  <ChatModeApp />
) : (
  <LegacyFormApp />
);
```

**Benefits:**
- Test chat mode without breaking existing functionality
- Easy rollback if issues found
- Gradual migration path

### Backward Compatibility
- Keep old components in `webview/src/components/legacy/` during transition
- Add setting: `kiwi.useChatInterface` (default: true)
- Remove legacy components after 2-week stabilization period

---

## Potential Challenges & Solutions

### Challenge 1: Context Management
**Problem:** "fix the first violation" needs to know which scan results to reference

**Solution:**
- Store conversation context in useConversation hook
- Each message includes metadata (action, params, results)
- Input parser checks recent messages for context
- Example: "fix the first violation" → find last scan message → extract first violation

### Challenge 2: Path Autocomplete Performance
**Problem:** File system queries might be slow for large workspaces

**Solution:**
- Debounce autocomplete requests (300ms)
- Cache suggestions for common prefixes
- Limit results to 20 items
- Show loading indicator

### Challenge 3: Message History Size
**Problem:** Long conversations might cause memory issues

**Solution:**
- Limit conversation history to 100 messages
- Add "Clear Chat" button
- Optional: persist to VSCode state

### Challenge 4: Natural Language Parsing Accuracy
**Problem:** Ambiguous input might parse incorrectly

**Solution:**
- Start with simple keyword matching
- Show parsed command preview before execution
- Add "Did you mean?" suggestions
- Allow manual correction via quick actions

---

## Success Criteria

### User Experience:
- ✅ Reduced clicks to perform common actions (scan, fix, check)
- ✅ Faster workflow with slash commands
- ✅ Better discoverability with natural language
- ✅ Improved context retention across interactions
- ✅ Copy buttons directly in results (no extra clicks)

### Technical:
- ✅ No breaking changes to backend (MCP, extension commands)
- ✅ Maintain VSCode theme compatibility
- ✅ Performance: message rendering < 100ms
- ✅ Bundle size increase < 50KB

### Verification:
- ✅ All test scenarios pass
- ✅ Feature flag allows gradual rollout
- ✅ Backward compatibility during transition
- ✅ Documentation updated with screenshots

---

## File Structure After Refactoring

```
webview/src/
├── components/
│   ├── chat/
│   │   ├── ChatContainer.tsx          [NEW]
│   │   ├── MessageList.tsx            [NEW]
│   │   ├── MessageBubble.tsx          [NEW]
│   │   ├── ChatInput.tsx              [NEW]
│   │   ├── InlineActions.tsx          [NEW]
│   │   ├── CopyButton.tsx             [NEW]
│   │   └── messages/
│   │       ├── ScanResultMessage.tsx  [NEW]
│   │       ├── ContextMessage.tsx     [NEW]
│   │       ├── LessonMessage.tsx      [NEW]
│   │       ├── DeployMessage.tsx      [NEW]
│   │       └── ErrorMessage.tsx       [NEW]
│   └── legacy/                        [ARCHIVE]
│       ├── ActionSelector.tsx
│       ├── PathInput.tsx
│       ├── OptionsForm.tsx
│       ├── ResultsViewer.tsx
│       ├── ContextViewer.tsx
│       ├── LessonBrowser.tsx
│       └── DeployWorkflow.tsx
├── hooks/
│   ├── useKiwi.ts                     [MODIFY]
│   ├── useVSCode.ts                   [NO CHANGE]
│   └── useConversation.ts             [NEW]
├── utils/
│   ├── inputParser.ts                 [NEW]
│   ├── pathAutocomplete.ts            [NEW]
│   └── clipboard.ts                   [NEW]
├── styles/
│   ├── app.css                        [MODIFY]
│   └── chat.css                       [NEW]
├── types/
│   └── index.ts                       [MODIFY]
├── App.tsx                            [MAJOR REFACTOR]
└── main.tsx                           [NO CHANGE]
```

---

## Timeline Estimate

- **Week 1 (Foundation):** 2 days
- **Week 2 (Message Components):** 3 days
- **Week 3 (Interactions):** 3 days
- **Week 4 (Integration & Testing):** 2 days

**Total:** ~10 days for complete implementation and testing
