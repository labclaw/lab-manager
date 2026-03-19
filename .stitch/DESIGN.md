# Design System — Lab Manager (Product)

**Version:** 0.1.0
**Updated:** 2026-03-19
**Inherits:** [`/.stitch/DESIGN.md`](../../.stitch/DESIGN.md) (LabClaw Ecosystem shared tokens)
**Stitch Project ID:** `11370887761312061505`

---

## Product Context

Lab Manager is a **generic, white-label lab inventory and document management SaaS**. Any laboratory can use it. It accepts documents via any input channel (photo, text, chat, email), extracts structured data with AI, and presents it for human-in-the-loop verification before committing to the inventory database.

**Core workflows:**
1. **AI Document Intake** — OCR + LLM extraction from invoices, packing slips, certificates of analysis
2. **Human-in-the-Loop Review** — Side-by-side original document vs. extracted data, field-level accept/reject
3. **Inventory Management** — Searchable, filterable inventory with categories, locations, expiry tracking
4. **Orders Tracking** — Purchase order lifecycle from request to delivery
5. **Universal Search** — Global search across documents, inventory items, orders

---

## Branding Scope

| Brand | Scope |
|-------|-------|
| **Lab Manager** | This product. All UI text, page titles, logos, onboarding copy. |
| **Shen Lab** | NEVER appears in lab-manager. Shen Lab branding exists only in `shenlab-manager` (deployment instance with config overrides). |

Deployments for specific labs override branding via instance-level configuration repositories (e.g., `shenlab-manager`). The generic product knows nothing about any specific lab.

---

## Personality: "High-Density Command"

**Vibe:** "I am here to work."

Data-dense, utilitarian, functional. Every pixel earns its place by conveying information or enabling action. No decorative illustrations, no marketing fluff inside the app. The interface respects the user's time and expertise.

**Principles:**
- **Density over whitespace** — Show more data per viewport. Scientists prefer information-rich screens.
- **Function over form** — Plain labels, direct actions, minimal animation.
- **Confidence through structure** — Consistent column widths, aligned numbers, clear hierarchy.
- **Trust through transparency** — Always show AI confidence scores, always allow human override.

---

## Token Overrides

Shared tokens (background, surface, text, border, typography, spacing, motion) are inherited from the root ecosystem DESIGN.md without modification.

### Semantic Colors

| Role | Token | Value | Notes |
|------|-------|-------|-------|
| Primary | `--primary` | `#6C5CE7` (Indigo Violet) | Same as ecosystem default. Buttons, active nav, focus rings. |
| Accent | `--accent` | `#00D4AA` (Vivid Teal) | Success states, positive indicators, verified badges. |

### Roundness

| Element | Radius | Notes |
|---------|--------|-------|
| Buttons | `8px` (ROUND_EIGHT) | Tight, professional. |
| Cards | `8px` | Tighter than ecosystem default (12px). Dense layout needs less rounding. |
| Inputs | `4px` | Inherited from ecosystem. |
| Modals/Panels | `8px` | Consistent with cards. |
| Pills/Avatars | `9999px` | Inherited from ecosystem. |

Override in CSS:
```css
/* lab-manager overrides */
:root {
  --radius: 0.5rem; /* 8px base */
}
```

### Layout

- **Sidebar-first:** Persistent left sidebar (240px), always visible on desktop.
- **Dense data tables:** Default view for inventory, documents, orders. No card-grid alternatives.
- **Iconography:** Lucide icons exclusively. Functional, not decorative.
- **Mobile:** Bottom tab navigation replaces sidebar. Same density principles, adapted for touch.

---

## Stitch designTheme Target

When generating or editing screens in Stitch project `11370887761312061505`, use this theme prompt:

> Dark scientific UI. Background #0B0B14, cards #12121E, text #F0F0F5. Primary indigo-violet #6C5CE7, accent teal #00D4AA. 8px border radius on all elements. Left sidebar navigation, dense data tables. Lucide icons. No decorative illustrations. Professional, utilitarian, data-dense. Product name is "Lab Manager" (never "Shen Lab").

---

## Screen Inventory (24 screens)

### Desktop — Dashboard (6 screens)

| Screen | ID | Status |
|--------|----|--------|
| Lab Manager Dashboard | `38bc4416042d496691f1363d44414d97` | OK |
| Lab Manager Dashboard | `26c4304ed8ad4961892833d46805a929` | OK (iteration) |
| Lab Manager Dashboard Refined | `f2d166172a7f41ca9027179aa551c678` | OK |
| Lab Manager Dashboard with Sidebar | `698dfbb13fa746068ffe0e4674d1bed1` | OK (canonical layout) |
| Shen Lab Manager Dashboard | `6fbb6d7888184d5a893cbb6e2e9958af` | BRAND LEAK: rename to "Lab Manager Dashboard" |
| Refined Main Dashboard (UX Optimized) | `45b50d553d264f69a4091ccbbcfb2330` | OK |

### Desktop — Feature Screens (7 screens)

| Screen | ID | Status |
|--------|----|--------|
| Shen Lab Review Queue | `bbb6c09fcfa9428891aa2d68a7e98edc` | BRAND LEAK: rename to "Review Queue" |
| Refined Review Queue (UX Optimized) | `fb6ba701a0e7462aa1adca1ddec9007d` | OK |
| Document Verification Detail | `5c91f071a32649febf343b07960ed797` | OK |
| Shen Lab Inventory Management | `30c63361b05b4a91b1fd37f9c6d619ef` | BRAND LEAK: rename to "Inventory Management" |
| Shen Lab Documents Management | `e5723d2573a743abb17f326886db28f0` | BRAND LEAK: rename to "Documents Management" |
| Shen Lab Orders Tracking | `cdd365cb719c47c0b66056ba95ca61e9` | BRAND LEAK: rename to "Orders Tracking" |
| Lab Theme Customization | `d86210cdbf8b4e228fe57787d2dc08e7` | OK |

### Desktop — Light Theme (2 screens)

| Screen | ID | Status |
|--------|----|--------|
| Shen Lab Dashboard (Light) | `b474b0936b464a98b64dea5f1cf97217` | BRAND LEAK: rename to "Lab Manager Dashboard (Light)" |
| Shen Lab Dashboard (Light) | `a2c31a7a90714beba460c79898765bcd` | BRAND LEAK: rename to "Lab Manager Dashboard (Light)" |

### Desktop — Onboarding (2 screens)

| Screen | ID | Status |
|--------|----|--------|
| Shen Lab Production Onboarding (Refined) | `eff609ffe00a419eb1b46b3088e9c8a4` | BRAND LEAK: rename to "Lab Manager Onboarding" |
| Shen Lab Multi-Module Onboarding | `647e9c175b7e4d279737e5d83d886ce4` | BRAND LEAK: rename to "Lab Manager Multi-Module Onboarding" |

### Mobile (5 screens)

| Screen | ID | Status |
|--------|----|--------|
| Lab Manager Mobile Dashboard | `9ac5d0305982492f9bf4c08cd68b9b96` | OK |
| Shen Lab iPhone Dashboard | `7587e9cf4ca74f979a1828f89acf88bb` | BRAND LEAK: rename to "Lab Manager iPhone Dashboard" |
| Shen Lab Android Dashboard | `b8d8774914a94528a9d43c4896f02136` | BRAND LEAK: rename to "Lab Manager Android Dashboard" |
| Shen Lab Mobile (Light) | `d547211d7c364a72be50e7e9877e5f2f` | BRAND LEAK: rename to "Lab Manager Mobile (Light)" |
| Shen Lab Mobile (Light) | `81b9fe45ebb34b678f06467ed8a35258` | BRAND LEAK: rename to "Lab Manager Mobile (Light)" |

### Broken / Meta (3 screens, not production)

| Screen | ID | Status |
|--------|----|--------|
| Gap Analysis & Release Checklist | `d0ecb800d9fd44cebd0395e5a86c638b` | Meta doc (height=0, no screenshot) |
| Lab-Manager 项目设计总结 | `c5385bcf3a884e289c6ab0069d8ea5ee` | Meta doc (height=0, no screenshot) |
| User Onboarding: Welcome Screen | `5b974d02bb2c4f979d519d73e74632df` | Broken (height=0) |

---

## Audit Findings

| Issue | Count | Action |
|-------|-------|--------|
| "Shen Lab" brand leaks in screen titles | 12 | Rename all to "Lab Manager" via `edit_screens` |
| Broken screens (height=0, no screenshots) | 2 | Delete or regenerate |
| Iteration duplicates not cleaned up | ~4 | Keep canonical, archive rest |
| No loading/empty/error state designs | 0 screens | Design needed: empty inventory, loading skeleton, error fallback |

---

## Component Patterns

These patterns extend the ecosystem-level component patterns from the root DESIGN.md.

### Navigation Sidebar

- Width: 240px, fixed left, full viewport height.
- Background: Surface 1 (`#12121E`), 1px right border (`#2A2A3E`).
- Sections: Dashboard, Review Queue, Inventory, Documents, Orders, Settings.
- Active item: Primary background at 15% opacity, left 3px accent bar, primary text color.
- Collapsed mode (mobile/narrow): 64px icon-only sidebar or bottom tab bar.

### Universal Search

- Trigger: `Cmd+K` / `Ctrl+K` modal overlay.
- Background: Surface 2 (`#1A1A2E`), 8px radius.
- Searches across: inventory items, documents, orders, review queue.
- Results grouped by category with Lucide icons.

### Review Queue

- Table layout: columns for Document Type, Submission Date, AI Confidence, Status, Assignee.
- Row states: Pending (muted), In Review (primary), Verified (accent/teal), Rejected (destructive).
- Batch actions: Select multiple, bulk approve/reject.
- Sort by AI confidence ascending to surface lowest-confidence items first.

### Document Verification Detail

- Split-pane layout: Original document (left 50%), extracted fields (right 50%).
- Each extracted field shows: value, AI confidence badge (color-coded), accept/reject/edit controls.
- Confidence badges: >= 95% accent/teal, 80-94% primary/indigo, < 80% warning/amber, < 50% destructive/red.
- Bottom action bar: "Approve All", "Reject", "Save & Next".

### Inventory Table

- Dense table: columns for Name, Category, Location, Quantity, Unit, Expiry Date, Last Updated.
- Sticky header with Surface 3 (`#242438`).
- Alternating row backgrounds: Surface 1 / Background.
- Inline editing for quantity fields.
- Column sorting, multi-column filtering, CSV export.
- Empty state: centered message with "Add your first item" CTA.

---

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-19 | v0.1.0: Initial project-level DESIGN.md | Separates lab-manager personality from ecosystem shared tokens. |
| 2026-03-19 | Card radius 8px (not ecosystem 12px) | Dense data layout benefits from tighter rounding. |
| 2026-03-19 | "Lab Manager" is the only product name | Generic white-label. Shen Lab branding scoped to deployment instance only. |
| 2026-03-19 | Sidebar-first layout as canonical | Data-heavy app needs persistent navigation. Matches "with Sidebar" dashboard variant. |
| 2026-03-19 | 12 screens flagged for brand leak rename | "Shen Lab" in titles must become "Lab Manager" before next design pass. |
