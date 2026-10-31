# UI / UX Specification

## 1. Design Principles

1. **Transparent agents:** always show who is doing what and why.
2. **User in control:** approvals, edits, and cancel are one click away.
3. **Calm and professional:** a friendly "Agent Office" feel without being gimmicky.
4. **Fast feedback:** streaming, optimistic UI, skeleton loaders.
5. **Accessible by default:** WCAG 2.1 AA, keyboard navigable, reduced-motion support.

## 2. Frontend Stack

- Next.js App Router, React Server Components where useful, TypeScript
- Tailwind CSS + shadcn/ui (Radix primitives), lucide-react icons
- TanStack Query for server state, Zustand for UI state
- SSE client for agent events, `react-hook-form` + Zod for forms
- FullCalendar (or custom) for calendar, Recharts for analytics
- Framer Motion for subtle agent animations (respect `prefers-reduced-motion`)

## 3. Design Tokens

| Token | Light | Dark |
|---|---|---|
| `--bg` | #FAFAFB | #0E1016 |
| `--surface` | #FFFFFF | #161922 |
| `--border` | #E5E7EB | #262A36 |
| `--text` | #111827 | #E7E9EE |
| `--muted` | #6B7280 | #9AA1B2 |
| `--primary` | #6D5EF5 | #8B7FFF |

**Agent colors:** Master `#6D5EF5` · Researcher `#0EA5E9` · Creator `#F59E0B` · Scheduler `#10B981` · Analytics `#EC4899`

**Status colors:** draft (gray), pending approval (amber), scheduled (blue), published (green), failed (red).

Typography: Inter (UI), JetBrains Mono (code/IDs). Radius: 12px cards, 8px inputs. Spacing scale 4px.

## 4. Information Architecture and Routes

```
/login, /signup
/onboarding                         # workspace + first campaign
/[campaignId]/overview
/[campaignId]/agents
/[campaignId]/agents/[agentId]      # full-page chat (optional deep link)
/[campaignId]/posts
/[campaignId]/posts/new
/[campaignId]/posts/[postId]
/[campaignId]/calendar
/[campaignId]/analytics
/settings/workspace | /settings/accounts | /settings/billing | /settings/team
```

## 5. Global Layout

```
┌────────────┬──────────────────────────────────────────────┐
│  Sidebar   │  Header: [Search]        [Create Post] [User]│
│ (floating, ├──────────────────────────────────────────────┤
│ collapsible)│                                              │
│ Campaign ▾ │                Page content                  │
│ Overview   │                                              │
│ AI Agent   │                                              │
│ Posts      │                                              │
│ Calendar   │                                              │
│ Analytics  │                                              │
│ Settings   │                                              │
└────────────┴──────────────────────────────────────────────┘
```

### Sidebar
- Floating card style, collapsible to icon-only; colorful icons per module.
- **Campaign Switcher** (dropdown with search, "New campaign").
- Active route highlighted; tooltips when collapsed.

### Header
- Global search (posts, campaigns, agents) with `⌘K` command palette.
- **Create Post** primary button → opens creation wizard.
- Notification bell with unread badge (approvals needed, failures).
- User menu (profile, theme toggle, sign out).

## 6. Pages

### 6.1 Overview
- **Campaign status card:** name, goal, connected platforms, next scheduled post, approval mode.
- **KPI strip:** posts this week, scheduled, published, engagement trend.
- **Agent Office preview:** compact office scene with 5 agent avatars/desks, each with a status chip and current-task bubble. Clicking opens the Agent Drawer.
- **Upcoming posts:** next 5 posts. *Empty state:* illustration + "No upcoming posts. Ask your agents to create some." with CTA.
- **Needs your attention:** pending approvals, failed posts, disconnected accounts.

### 6.2 AI Agent Page (Agent Office)
- Left: **office canvas** listing Master, Researcher, Creator, Scheduler, Analytics with live status.
- Center/right: **Master Agent chat** with:
  - Message list (user, agent, system events).
  - **Plan card** (steps with live status ticks) before execution.
  - **Task timeline** (which agent ran what, duration).
  - Inline **post preview cards** with Approve / Edit / Reject.
  - Composer with suggestions chips ("Create 2 Instagram posts about…", "Weekly performance report").
- Per-agent tabs: **Chat · History · Settings** (tone, tools enabled, limits).

### 6.3 Agent Drawer (Popover to Side-Drawer)
- Opens from Overview or any page; contains the same chat, scoped to a single agent.
- Hover on avatar shows quick status popover; click opens drawer.

### 6.4 Posts
- Table/grid toggle with filters: status, platform, creator (user/agent), date.
- Columns: thumbnail, caption snippet, platforms, status chip, scheduled time, created by.
- Bulk actions: approve, reschedule, delete.
- Row click opens Post Detail (side sheet).

### 6.5 Create Post Wizard
Step 1: **Choose mode**
- **Manual:** title, caption (character counter per platform), hashtags (chips), media upload, platforms, date/time.
- **AI-Assisted:** prompt box + options (platforms, count, tone, topic or "use latest research"). Submits to Master Agent and redirects to chat with live progress.

Step 2: **Preview** per platform (Instagram, X, LinkedIn mockups).
Step 3: **Schedule:** now, pick time, or "suggest best time".

### 6.6 Edit Image Dialog (ImageKit)
- Canvas preview + controls: crop (aspect presets 1:1, 4:5, 9:16, 16:9), resize, rotate, text overlay, background removal/blur, brightness/contrast, filters.
- "Ask Creator Agent" input (e.g., "make background brighter").
- Save creates new transformation record; original preserved; undo/redo.

### 6.7 Calendar
- Month / Week / List views; color-coded by platform/status.
- Drag-and-drop to reschedule (confirm dialog if < 15 min from now).
- Click empty slot → quick-create; click event → post detail sheet.

### 6.8 Analytics
- Filters: date range, platform, campaign.
- KPI cards: impressions, reach, engagement rate, followers, best post.
- Charts: engagement over time, platform comparison, post-type performance, best time heatmap.
- **AI Insights panel** from Analytics Agent with recommendations and "Apply suggestion" buttons (e.g., "Schedule more carousels").
- Top/bottom posts table. Export CSV.

### 6.9 Settings
- Accounts: connect/disconnect platforms with status badges.
- Campaign: brand voice, audience, timezone, approval mode toggle (**Require approval** default).
- Team and billing (post-MVP stubs).

## 7. Key Components

| Component | Notes |
|---|---|
| `AppSidebar`, `CampaignSwitcher`, `Header`, `CommandPalette` | Shell |
| `AgentOffice`, `AgentAvatar`, `AgentStatusChip`, `AgentDrawer` | Office visuals and live status |
| `ChatPanel`, `MessageBubble`, `PlanCard`, `TaskTimeline`, `ToolCallChip` | Agent chat |
| `PostCard`, `PostTable`, `PostPreview`, `ApprovalBar` | Posts |
| `PostWizard`, `PlatformPreview`, `HashtagInput`, `MediaUploader` | Creation |
| `ImageEditorDialog` | ImageKit editing |
| `CalendarView`, `EventChip` | Scheduling |
| `KpiCard`, `TimeSeriesChart`, `InsightsPanel` | Analytics |
| `EmptyState`, `ErrorState`, `Skeleton`, `ConfirmDialog`, `Toast` | Shared states |

## 8. Agent Status Model (UI)

| Status | Visual |
|---|---|
| `idle` | Gray dot, avatar at rest |
| `thinking` | Pulsing ring |
| `working` | Animated typing/tools indicator with current task text |
| `waiting_approval` | Amber badge, bell notification |
| `error` | Red badge with retry |
| `done` | Green check (transient, 3 s) |

## 9. Real-Time Behavior

- SSE connection per active run; reconnect with backoff and `Last-Event-ID`.
- Optimistic updates for approve/reject/reschedule with rollback on error.
- Token streaming in chat; plan and task cards update in place.
- Fallback to polling every 5 s if SSE is unavailable.

## 10. States and Edge Cases

- **Loading:** skeletons, never blank screens.
- **Empty:** every list has a helpful empty state with a primary action.
- **Errors:** inline error with retry; run failures show agent, step, and "Retry step".
- **Disconnected account:** banner on Overview and blocking inline warning when scheduling.
- **Quota reached:** non-blocking banner, agent actions disabled with explanation.
- **Offline:** toast and read-only mode.

## 11. Responsive Behavior

| Breakpoint | Behavior |
|---|---|
| ≥ 1280 | Full sidebar, office + chat side by side |
| 768-1279 | Collapsed sidebar (icons), drawer for chat |
| < 768 | Bottom nav (Overview, Agents, Posts, Calendar, Analytics), full-screen chat, simplified office list |

## 12. Accessibility

- Semantic landmarks, focus-visible rings, skip link.
- All interactive elements keyboard reachable; drag-and-drop has keyboard alternative on Calendar.
- Live regions (`aria-live="polite"`) for agent status and streaming messages.
- Color contrast ≥ 4.5:1; status never conveyed by color alone (icon + label).
- Respect `prefers-reduced-motion` and `prefers-color-scheme`.

## 13. Copy and Tone

- Agents speak in a friendly, concise, professional voice; first-person ("I found 5 trending topics").
- Always explain *why* for recommendations.
- Destructive actions use explicit verbs ("Delete post", not "OK").
