AGENT: Nexedi RAG Frontend
================================

MISSION
-------
- Provide a conversational UI for Nexedi’s Retrieval-Augmented Generation experience.
- Surface chat history, quick creation, and theme toggling directly in the sidebar.
- Deliver a modern prompt composer with autosizing input, contextual actions, and in-flight status handling.

SYSTEM OVERVIEW
---------------
1. **Vue 3 + Vite stack**
   - Entry point `src/main.ts` mounts `App.vue`.
   - Global styling via Tailwind 4 (utility classes) and theme tokens in `src/style.css`.
   - Vue Router (`src/router/index.ts`) coordinates the landing (`/`) and chat (`/chat`) experiences.

2. **Layout shell**
   - `App.vue` wraps the page in `SidebarProvider` (from shadcn-vue) which manages sidebar state, keyboard toggle, and responsive behaviour.
   - `AppSidebar.vue` renders the left rail (header, content, footer) and consumes `useSidebar` to adjust UI based on expansion state.
   - Main pane renders the active route; when collapsed, a floating `SidebarTrigger` appears within the content area.

3. **Page flows**
   - `LandingView.vue` presents the hero prompt composer and routes to `/chat` with the typed draft.
   - `ChatView.vue` hosts the transcript, stick-to-bottom container, and composer anchored at the bottom.

4. **Component kits**
   - shadcn-vue (ported) components power the sidebar, buttons, dropdown, tooltip, switch, etc.
   - Custom prompt kit conversion (`src/components/prompt/*`) reproduces Prompt Kit’s React “prompt-input” API for Vue.
   - Custom chat container (`src/components/chat/*`) ports Prompt Kit’s stick-to-bottom transcript behaviour.
   - Tailwind utility classes glue the visual language.

SIDEBAR DESIGN
--------------
```
Sidebar (AppSidebar.vue)
├─ Header
│  ├─ Title (“Nexedi RAG”) + inline SidebarTrigger (hidden when collapsed)
│  └─ “New chat” button styled with SidebarMenuButton
├─ Content
│  └─ Session list (ordered by `lastActivity`)
│     ├─ Session title row with dropdown menu (rename/delete)
│     └─ Fallback hint when empty
└─ Footer
   └─ Theme switch (light/dark) persists preference in localStorage
```
- Local chat session data stored in a `ref<ChatSession[]>`; helper methods add, rename, delete.
- Ordering derived via computed getter (`orderedSessions`).
- `isDarkMode` toggles document `classList` and writes `rag-ui-theme` key.

PROMPT INPUT DESIGN
-------------------
```
PromptInput (context provider)
├─ TooltipProvider wrapper
├─ Autosize textarea (PromptInputTextarea)
│  ├─ Controlled via provided `value`/`setValue`
│  ├─ Autosizes up to `maxHeight` (default 240px)
│  └─ Enter submits (Shift+Enter inserts newline)
└─ Actions row (PromptInputActions)
   └─ Tooltip-backed buttons (PromptInputAction)
```
- Context stored via Vue provide/inject for composable access (value, submit, loading state).
- `PromptInputTextarea` leverages new `Textarea` wrapper under `src/components/ui/textarea`.
- Views own their prompt state: landing forwards the draft via router query, chat appends turns and simulates assistant latency.
- Attach button (ghost variant) and Send button (primary) use lucide icons (`Paperclip`, `Send`).

CHAT CONTAINER DESIGN
---------------------
```
ChatContainerRoot
├─ Provides stick-to-bottom behaviour driven by scroll heuristics
├─ Offers context to ChatContainerContent and ScrollAnchor
└─ Auto-scrolls only when the user is already near the bottom
```
- Ported from Prompt Kit into Vue using ResizeObserver + scroll listeners (`src/components/chat/*`).
- Chat messages supply content/role/timestamps; timestamps formatted with `Intl.DateTimeFormat`.

STATE & EVENTS
--------------
- **Sidebar**
  - `useSidebar` exposes `state` for conditional trigger rendering.
  - `handleCreateNewChat`, `renameSession`, `deleteSession` mutate `chatSessions`.
- **Theme**
  - `initialiseTheme()` reads localStorage or prefers system.
  - `watch(isDarkMode)` to update DOM + storage.
- **Prompt**
  - `PromptInput` emits `update:modelValue` and `submit`.
  - `LandingView` pushes to `/chat` with the outgoing prompt while disabling controls during navigation.
  - `ChatView` consumes the prompt query, appends a user turn, and simulates an assistant reply via timeout.

FILES TO KNOW
-------------
- `src/App.vue`: Shell layout, sidebar provider, collapsed trigger logic.
- `src/router/index.ts`: Landing/chat route configuration.
- `src/views/LandingView.vue`: Hero prompt experience + navigation.
- `src/views/ChatView.vue`: Chat transcript, mock assistant responses, bottom composer.
- `src/components/AppSidebar.vue`: Sidebar UI, session store, theme toggle.
- `src/components/prompt/*`: Prompt component suite (Vue port of Prompt Kit).
- `src/components/chat/*`: Stick-to-bottom chat container suite.
- `src/components/ui/*`: Wrapper components for shadcn-vue (button, dropdown, tooltip, textarea, etc.).
- `src/style.css`: Tailwind theme variables, dark mode tokens.

EXTENSION HOOKS
---------------
- Replace simulated assistant timeout in `ChatView` with real RAG inference (stream tokens into chat history).
- Persist chat sessions (IndexedDB or backend) and bind rename/delete to service endpoints.
- Support multi-agent personas by extending sidebar groups (e.g., “Pinned”, “Shared”).
- Add attachments workflow: integrate file picker + upload indicator within `PromptInputActions`.

TESTING NOTES
-------------
- Build via `npm run build` (fails under read-only sandbox; ensure writable workspace).
- Key interactive checks:
  - Autosize + Enter submit behaviour.
  - Theme toggle persistence across reload.
  - Sidebar collapse/expand triggers (keyboard shortcut `Ctrl/Cmd + B`).
  - Landing prompt submission navigates to `/chat` and seeds the first user message.
