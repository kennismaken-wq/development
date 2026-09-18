---
version: alpha
name: HandigerAI-glass-design
description: "A dark, warm glassmorphism system shared across the HandigerAI product family (the huisstijl-tool at tools.handigerai.nl and the klusapp for De Groene M). A fixed, saturated gradient background (never white) carries translucent 'glass' panels: rgba(255,255,255,0.10) fills, 28px backdrop-blur, hairline white borders, soft dark drop shadows. Inter carries every line of body text, labels and buttons; italic Fraunces (weight 600) is reserved exclusively for headings and brand marks — that sans/italic-serif contrast is the family's single most recognizable fingerprint. Every interactive shape is a pill (999px) or a generously rounded card (16-32px) — sharp corners (0-4px) never appear. One thing is NOT fixed: the accent hue. The house tool runs cool blue (#5B8FA8) with a coral secondary (#E07B5F); the klusapp reskins the identical system in De Groene M's lime green (#95BF1D). Everything else — the glass recipe, the type pairing, the radius scale, the spacing rhythm, the component patterns — stays byte-for-byte the same across both."

colors:
  # Root tool (tools.handigerai.nl / glass.html) — the canonical prototype palette.
  accent: "#5B8FA8"
  warm: "#E07B5F"
  ink: "#1A1A18"
  on-ink: "#FFFFFF"
  success: "#7FE0A0"
  gradient-stop-1: "#1E3540"
  gradient-stop-2: "#3B6376"
  gradient-stop-3: "#6E8798"
  gradient-stop-4: "#A5806A"
  gradient-stop-5: "#C98B5E"
  # klusapp (De Groene M) — same system, swapped accent. See "Per-product accent" below.
  klusapp-accent: "#95BF1D"
  klusapp-hi: "#D6EC9B"
  klusapp-rood: "#E07B5F"
  klusapp-gradient-stop-1: "#1D1D1B"
  klusapp-gradient-stop-2: "#212220"
  klusapp-gradient-stop-3: "#262B20"
  klusapp-gradient-stop-4: "#2E3522"
  # Shared, regardless of accent
  glass-fill: "rgba(255,255,255,0.10)"
  glass-border: "rgba(255,255,255,0.20)"
  text-high: "rgba(255,255,255,0.85)"
  text-mid: "rgba(255,255,255,0.6)"
  text-low: "rgba(255,255,255,0.5)"

typography:
  h1:
    fontFamily: Fraunces
    fontStyle: italic
    fontWeight: 600
    fontSize: 1.6rem
    lineHeight: 1.15
  h1-hero:
    fontFamily: Fraunces
    fontStyle: italic
    fontWeight: 600
    fontSize: 2rem
  card-title:
    fontFamily: Fraunces
    fontStyle: italic
    fontWeight: 600
    fontSize: 1.05rem
  section-label:
    fontFamily: Inter
    fontSize: 10.5px
    fontWeight: 600
    letterSpacing: 0.07em
    textTransform: uppercase
    color: "{colors.text-low}"
  body:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: 400
  meta:
    fontFamily: Inter
    fontSize: 11.5px
    fontWeight: 400
    color: "{colors.text-mid}"
  button:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: 600

rounded:
  pill: 999px
  card-lg: 28px
  card-lg-mobile: 22px
  window: 32px
  widget: 18-24px
  input: 13-14px
  icon-badge: 10-17px
  circle: 50%

spacing:
  card-padding-desktop: 1.8rem 2rem 2.2rem
  card-padding-mobile: 1.2rem 1rem 1.6rem
  section-gap: 1.4-2.5rem
  label-margin: 1.1rem 0 .35rem
  widget-gap: .5-1.1rem
  breakpoint-mobile: 700px

components:
  glass-panel:
    backgroundColor: "{colors.glass-fill}"
    border: "1px solid {colors.glass-border}"
    backdropFilter: blur(28px) saturate(150%)
    boxShadow: 0 24px 70px rgba(0,0,0,0.30), inset 0 1px 0 rgba(255,255,255,0.15)
    rounded: "{rounded.card-lg}"
  button-primary-gradient:
    backgroundColor: linear-gradient(135deg, rgba(accent-rgb,0.95), rgba(accent-rgb,0.72))
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.pill}"
    minHeight: 50px
  button-primary-solid:
    backgroundColor: "#FFFFFF"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.pill}"
    boxShadow: 0 8px 24px rgba(0,0,0,0.18)
  button-ghost:
    backgroundColor: "{colors.glass-fill}"
    textColor: "#FFFFFF"
    border: "1px solid {colors.glass-border}"
    typography: "{typography.button}"
    rounded: "{rounded.pill}"
  input:
    backgroundColor: "{colors.glass-fill}"
    textColor: "#FFFFFF"
    border: "1px solid {colors.glass-border}"
    typography: "{typography.body}"
    rounded: "{rounded.input}"
    padding: .8rem .9rem
  badge-pill:
    backgroundColor: rgba(accent,0.22)
    textColor: "{colors.text-high}"
    border: "1px solid rgba(accent,0.4)"
    rounded: "{rounded.pill}"
    padding: .25rem .7rem
  sidebar-nav:
    backgroundColor: "{colors.glass-fill}"
    rounded: "{rounded.pill}"
    layout: floating vertical pill (desktop) / horizontal scroll bar (mobile)
  empty-state:
    border: "1.5px dashed rgba(255,255,255,0.28)"
    textColor: "{colors.text-low}"
    rounded: "{rounded.widget}"
  modal:
    backgroundColor: "{colors.glass-fill}"
    backdrop: rgba(10,10,8,0.55) + blur(3px)
    rounded: 22px
  toggle-switch:
    trackColor: rgba(255,255,255,0.18)
    trackColorChecked: "{colors.accent}"
    thumbColor: "#FFFFFF"
    rounded: "{rounded.pill}"
  choice-pill:
    backgroundColor: rgba(255,255,255,0.07)
    backgroundColorSelected: rgba(accent-rgb,0.32)
    textColor: rgba(255,255,255,0.7)
    textColorSelected: "{colors.klusapp-hi}"
    typography: "{typography.button}"
    rounded: "{rounded.pill}"
    minHeight: 38px
---

## Overview

Everything in this family lives on a fixed, saturated gradient — never white, never flat. Content sits in translucent "glass" cards on top: `rgba(255,255,255,0.10)` fill, `blur(28px) saturate(150%)` backdrop-filter, a hairline `rgba(255,255,255,0.20)` border, and a soft dark drop shadow with a faint inset highlight on the top edge. This `.glass` recipe is copy-pasted verbatim everywhere — cards, modals, inputs, nav, chips — it is the family's structural signature, more than any single color.

Typography carries a second signature: **Inter** for every line of body text, labels, buttons and inputs, and *italic* **Fraunces** (weight 600) exclusively for headings, card titles and the brand mark. That sans-body / italic-serif-heading contrast is the most recognizable fingerprint in the family — never swap it, never use Fraunces for body text or Inter for a heading.

Shape follows one rule: **round everything, sharply nothing**. Buttons, badges, chips, toggles and tabs are always full pills (`999px`). Cards and panels get generous 16–32px corners depending on size. A `0px` or `4px` corner anywhere reads as "not glassy" immediately.

**Key Characteristics:**
- **Fixed gradient body background**, `background-attachment: fixed`, two soft radial highlights over a diagonal linear base — content never scrolls the background.
- **`.glass` panel recipe** — identical CSS block reused on every card, input, nav and modal across both products.
- **Inter body / italic Fraunces headings** — the one typographic rule that never bends.
- **Pill-or-nothing shape language** — `999px` for anything interactive, 16–32px for containers, never sharp.
- **One swappable token: the accent hue.** Structure, spacing, type and the glass recipe are fixed; only the accent color (and the gradient's base hue) changes per product. See "Per-Product Accent" below.
- **No frameworks.** Server-rendered HTML/CSS, vanilla JS only where interaction truly needs it (see `klusapp/static/js/kalender.js`). No React, no Tailwind, no build step.
- **Mobile-first.** Every screen is designed and tested at 375px before it merges; `font-size: 16px` on inputs is non-negotiable (smaller sizes make iOS auto-zoom on focus).

## Per-Product Accent

The system ships two live skins of the exact same structure:

| | Root tool (`glass.html`) | klusapp (De Groene M) |
|---|---|---|
| Accent | `{colors.accent}` `#5B8FA8` cool blue | `{colors.klusapp-accent}` `#95BF1D` lime green |
| Secondary | `{colors.warm}` `#E07B5F` coral | same `#E07B5F` (used for errors only) |
| Background gradient | light, saturated teal → clay (`{colors.gradient-stop-1}`…`{colors.gradient-stop-5}`) | near-black → dark olive (`{colors.klusapp-gradient-stop-1}`…`{colors.klusapp-gradient-stop-4}`) with a lime glow |
| Light accent text | — | `{colors.klusapp-hi}` `#D6EC9B`, for numbers/"today"/emphasis on dark |

The formula behind the background is fixed even though the hues aren't:
```css
background:
  radial-gradient(ellipse 60% 50% at 15% 10%, <accent at ~50% opacity>, transparent 60%),
  radial-gradient(ellipse 55% 55% at 90% 95%, <warm/secondary at ~50% opacity>, transparent 60%),
  linear-gradient(150-160deg, <5 stops from dark to accent-tinted>);
background-attachment: fixed;
```
A **third** product picks its own accent + gradient stops the same way — never reuses blue or green, never touches the glass recipe, type pairing, radius scale or spacing rhythm.

## Colors

> Sources: `glass.html` (root prototype), `klusapp/static/css/app.css`, `CONTEXT.md` in both.

### Brand & Accent
- **Accent** (`{colors.accent}` / `{colors.klusapp-accent}`): primary CTA fills, active nav state, focus rings, links, "on" status. Scarce elsewhere — the accent should read as *the* interactive color, not decoration.
- **Warm/secondary** (`{colors.warm}`): secondary emphasis and — in klusapp — the only error/destructive color (`rood`). Never a second competing primary.
- **Ink** (`{colors.ink}`): near-black text used only *on* light surfaces (a white button, a highlighted term).

### Surface
- **Glass fill** (`{colors.glass-fill}`): every card, input, nav pill, modal, badge background.
- **Glass border** (`{colors.glass-border}`): hairline 1px border on every glass surface.
- No opaque light surface exists anywhere in the system. If something needs to feel "raised," it gets *more* glass opacity (`0.14`–`0.18`) and a stronger border, never white.

### Text
- **High** (`{colors.text-high}` ≈ `rgba(255,255,255,0.85)`): primary content, active labels.
- **Mid** (`{colors.text-mid}` ≈ `rgba(255,255,255,0.6)`): meta info, secondary labels, sub-headers.
- **Low** (`{colors.text-low}` ≈ `rgba(255,255,255,0.5)`): section labels, placeholders, least emphasis.
- Full opaque `#FFFFFF` is reserved for headings and the single most important line in a block.

### Semantic
- **Success**: `{colors.success}` `#7FE0A0` (root) / the accent itself doubles as success in klusapp (`rgba(accent, 0.18–0.42)` fill).
- **Error/warning**: `{colors.warm}` `#E07B5F` at `rgba(…, 0.18–0.48)` fill — identical in both products.

## Typography

### Font Family
Both loaded together, always:
```html
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,wght@0,600;0,700;1,600;1,700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
```
- **Inter** — every line of body copy, labels, buttons, inputs, nav, meta text.
- **Fraunces**, *italic*, weight 600 — headings, card titles, greetings, the brand wordmark only.

### Hierarchy

| Token | Size | Family | Weight/Style | Use |
|---|---|---|---|---|
| `{typography.h1-hero}` | 2rem | Fraunces | italic 600 | Login/dashboard greeting ("Hai, {naam}") |
| `{typography.h1}` | 1.6rem | Fraunces | italic 600 | Page title in `.kop` |
| `{typography.card-title}` | 1.05rem | Fraunces | italic 600 | List-row name, card title |
| `{typography.body}` | 16px | Inter | 400 | All body copy, inputs (never smaller — see Responsive) |
| `{typography.meta}` | 11.5–12.5px | Inter | 400 | Timestamps, "by whom", secondary line |
| `{typography.section-label}` | 10.5–11px | Inter | 600 uppercase | Form labels, section eyebrows |
| `{typography.button}` | 15px | Inter | 600 | All button/pill labels |

### Principles
- **One family per role, no exceptions.** If it's a heading-shaped element, it's italic Fraunces 600. If it's anything else, it's Inter.
- **Uppercase + letter-spacing marks metadata**, not emphasis — form labels and section eyebrows use `letter-spacing: .07em` plus reduced opacity, not size, to recede.
- **Opacity carries hierarchy** as much as size does: the same 12px Inter line can be "important" (`0.85`) or "background" (`0.5`) purely by color.

## Layout

### Spacing System
- Card outer padding: `{spacing.card-padding-desktop}` desktop, tightening to `{spacing.card-padding-mobile}` under `{spacing.breakpoint-mobile}`.
- Form label margin: `{spacing.label-margin}` — labels sit close under their field, generous gap above the next one.
- Section gaps: `{spacing.section-gap}` between major blocks (a heading + its content).
- List/grid gaps: `{spacing.widget-gap}`.
- Generous throughout — this system reads as spacious by design; when in doubt, add space rather than remove it.

### Grid & Container
- A screen is one centered `.kaart.glas`, max-width ~640px for forms/detail, ~1180px for wide data (weekkalender, planbord).
- The root tool's `glass.html` app-shell is a different pattern — a full window (`max-width: 1240px`, own sidebar inside the window) — used when a product is a standalone app shell rather than a single floating card. Pick one pattern per product, don't mix.

### Whitespace Philosophy
The gradient itself *is* the whitespace — there is no light "page background" to separate sections with. Hierarchy comes from which glass card something lives in and how translucent that card is, not from empty white space.

## Elevation & Depth

| Level | Treatment | Use |
|---|---|---|
| 0 | Gradient background, no panel | Page canvas only |
| 1 | `.glass` — `rgba(255,255,255,0.10)` fill, hairline border | Default card, input, nav, badge |
| 2 | `rgba(255,255,255,0.14–0.18)` fill | Hover state, active nav item, "lifted" widget |
| 3 | Accent-tinted fill `rgba(accent, 0.14–0.42)` | Selected/active state, success/total row |
| Modal | `.glass` card over a `rgba(10,10,8,0.55)` blurred backdrop | Dialogs, upload sheets |

No hard drop shadows outside the glass recipe itself (`0 24px 70px rgba(0,0,0,0.30)`) — depth comes from blur and border, not shadow stacking.

## Shapes

### Border Radius Scale

| Token | Value | Use |
|---|---|---|
| `{rounded.pill}` | 999px | Buttons, badges, chips, toggle track, tabs, nav pill — always, no exceptions |
| `{rounded.card-lg}` | 28px (22px mobile) | Main page card |
| `{rounded.window}` | 32px | Full app-shell window (root tool pattern) |
| `{rounded.widget}` | 16–24px | Sub-widgets, stat cards, modal cards |
| `{rounded.input}` | 13–14px | Text inputs, textareas |
| `{rounded.icon-badge}` | 10–17px | Icon badges, small square tiles |
| `{rounded.circle}` | 50% | Avatar-style icon buttons (close, logout, status dot) |

Never `0px` or `4px`. If a shape looks even slightly sharp, round it further.

## Components

### Buttons
- **Primary** — full-width or inline pill. Two valid recipes, pick one per product and stay consistent: `button-primary-gradient` (accent gradient fill, `{colors.ink}` text — klusapp's `.knop`) or `button-primary-solid` (solid white, `{colors.ink}` text, soft shadow, `translateY(-1px)` on hover — root tool's `.btn-white`). `min-height: 50px`.
- **Secondary/ghost** (`button-ghost`, `.knop-stil`/`.btn-ghost`) — translucent glass fill, white text, thin border. Used next to a primary action, never alone as the only CTA on a screen.
- Hover: lift (`translateY(-1px)`) or brighten (`filter: brightness(.94)` on `:active`) — never a color swap that breaks the pill's translucency.

### Inputs & Forms
- `input` recipe above. `font-size: 16px` is mandatory on every text/date/time input — anything smaller triggers iOS auto-zoom on focus, which breaks the layout.
- Date/time picker icons render black-on-dark by default; invert them (`filter: invert(1); opacity: .6`).
- Checkboxes are the one native-chrome exception: `accent-color: var(--accent)`, scaled up (`transform: scale(1.25)`), never full-width.
- No placeholder-as-label pattern — every field gets a real `section-label` above it (per house rule: "Geen hinttekst" — no explanatory hint text, but a label is not a hint).

### Cards & Containers
- `glass-panel` recipe on every card, list row, table row, stat tile.
- List rows (`.klusregel`, `.urenlijst li`, `.doclijst li`) are `display: grid`, `gap: .2–.3rem`, same glass fill/border as cards, just smaller radius (14–18px).

### Badges & Chips
- `badge-pill` recipe — accent-tinted translucent fill, matching border at higher opacity, pill radius, small uppercase-ish text.
- A colored dot (`.vlek`) — `width/height: 14px`, `border-radius: 999px`, `border: 1px solid`, filled with `linear-gradient(150deg, {kleur}D9, {kleur}73)` — is the pattern for "this item has its own identity color" (klus color-coding). The `D9`/`73` suffixes are hex alpha (~85%/~45%) appended directly to a hex color — reuse that trick instead of switching to `rgba()` when the color itself is a runtime variable.

### Brand Mark
- klusapp carries De Groene M's leaf: `34px` wide next to the page title in `.kop` (`.merk`), `96px` and centered above the title on the login card (`.kaart.inloggen`). Never a full lockup with wordmark — the card already says "De Groene M" in Fraunces.
- The supplied logo is green + near-black (`#1D1D1B`) with a drop shadow. On the dark glass the black halves disappear and the shadow smudges, so the app uses a derived light variant (`static/img/logo-de-groene-m-licht.png`: black → `#F4F6EE`, shadow stripped). The untouched two-tone file (`logo-de-groene-m.png`) is for light surfaces such as the photo report PDF.
- Favicon/home-screen icon is the leaf on a solid `#1D1D1B` tile (`favicon.png`, `icoon-180.png`), not the bare transparent leaf: a white-and-green mark on a light browser tab loses half of itself.
- A product without its own client logo shows no mark at all rather than a stand-in.

### Navigation
- **Floating glass pill**, not a tile grid: desktop = vertical pill, fixed, vertically centered, detached from the edge (`left: 1.3rem`); mobile (<700px) = horizontal bar pinned to the bottom, `env(safe-area-inset-bottom)`-aware, horizontal-scrolling if icons don't fit (never collapses into a hamburger/overflow menu).
- Active state = accent-tinted gradient fill + border; inactive = transparent, `rgba(255,255,255,0.6)` icon color, brightens on hover.
- Reference implementation: `klusapp/templates/basis.html` + `klusapp/static/css/app.css` (search "ZIJBALK").

### Empty States
- `empty-state` recipe — dashed `1.5–1.8px` border at low opacity, centered, muted text, no icon required. Never just blank space; always signal "this is empty, not broken."

### Modal / Dialog
- Native `<dialog>` element where possible (see `_fotodialoog.html`) — glass card, backdrop `rgba(10,10,8,0.55)` + `blur(3px)`, close = small circular glass button top-right.

### Toggle Switch
- `toggle-switch` recipe (root tool, `glass.html`) — pill track, white circular thumb, track fills with the accent color when checked. Standard checkbox-styled-as-switch pattern (`input[type=checkbox]` visually hidden, `<span>` sibling styled). Not currently shipped in klusapp — use `choice-pill` there instead.

### Choice Pill
- `choice-pill` recipe (klusapp, `.keuzepil` — aanwezigheidsregistratie) — the shipped, tested alternative to a binary toggle when there are two or more discrete states (ja/nee/onbekend). A `<label>` wraps a visually-hidden radio/checkbox and an inline `<span>` that IS the pill; `input:checked + span` gets the filled/accent style. Works without JS, keeps keyboard and screen-reader behavior intact. Prefer this over a toggle-switch whenever a field is really "pick one of N," not strictly on/off.

## Do's and Don'ts

### Do
- **Copy CSS literally from `glass.html`** (root) or the equivalent shipped screen in klusapp when unsure — never invent a new visual solution from scratch. This is the single most important rule in the family; every past deviation ("simplified," "cleaned up") shipped a visible bug.
- Keep the glass recipe byte-identical everywhere: `rgba(255,255,255,0.10)` fill, `blur(28px) saturate(150%)`, `1px solid rgba(255,255,255,0.20)` border, that exact box-shadow.
- Reserve Fraunces italic for headings only; Inter for everything else.
- Round every interactive element to a full pill; round every container generously.
- Give the accent color room to be scarce and meaningful — CTA, active state, focus, links. Not a background fill.
- Design mobile-first; test every screen at 375px before merging.
- When a needed component isn't in `glass.html`, look at [ui.shadcn.com](https://ui.shadcn.com/docs/components) for *behavior* (states, keyboard/focus handling) only — then build it natively in HTML/CSS/vanilla-JS, styled with this system's tokens. [uiverse.io/glassmorphism](https://uiverse.io/glassmorphism) has ready glass components in plain HTML/CSS, but check each one's license before copying — when unsure, rewrite it with the same structure instead of copying 1:1.

### Don't
- Don't introduce a white or flat opaque background anywhere — everything lives on the gradient, via glass panels.
- Don't use Fraunces for body text, or Inter for a heading.
- Don't ship a sharp corner (`0px`/`4px`) on anything.
- Don't add a third font family, even "just for code" or "just for numbers."
- Don't use strong, fully-saturated flat color fills — every color is translucent/muted over the gradient.
- Don't let a new product reuse another product's accent hue (blue is the root tool's, green is klusapp's).
- Don't pull in a component framework (React/Tailwind/shadcn-as-a-library) or add a build step — server-rendered HTML/CSS + vanilla JS only.
- Don't hide navigation behind a hamburger/overflow menu on mobile — scroll horizontally instead.
- Don't add placeholder-only inputs without a real label, and don't add explanatory hint/helper text under fields — the client explicitly found it too busy.

## Responsive Behavior

### Breakpoints
| Name | Width | Key Changes |
|---|---|---|
| Desktop | > 700px | Sidebar floats vertically, centered, left-detached; wide cards use `.kaart.breed` (1180px) |
| Mobile | ≤ 700px | `{spacing.breakpoint-mobile}` — card padding tightens, sidebar becomes a bottom bar |

### Touch Targets
- Buttons: `min-height: 50px`.
- Inputs: `font-size: 16px` non-negotiable (prevents iOS zoom-on-focus).
- Nav icons: 44px circles, generous tap area even inside the compact mobile bar.

### Collapsing Strategy
- **Nav**: vertical floating pill → horizontal bottom bar, scrolls rather than hides icons.
- **Wide data grids** (weekkalender, planbord): horizontal-scroll their own container, never reflow into a card-per-row — a fixed first column (name/time axis) stays sticky while the rest scrolls.
- **Multi-column forms**: single column below `700px`; nothing sits side-by-side on mobile.

### Image Behavior
- Photo grids use a masonry/column layout (`columns: 2 200px`, 4 on wider screens) so aspect ratio is preserved, never force-cropped.

## Iteration Guide

1. Before building any screen, open `glass.html` next to it and copy the closest matching block literally.
2. Decide accent color once per product (not per screen) — see "Per-Product Accent."
3. Default every body line to `{typography.body}` at 16px minimum.
4. Every new interactive shape gets a pill or a generous radius — check the Shapes scale before shipping a custom radius value.
5. Test at 375px width before merging; the sidebar/bottom-bar and any wide grid are where mobile breaks first.
6. If a component genuinely doesn't exist yet in either product, reference shadcn for behavior, uiverse.io/glassmorphism for a glass-styled HTML/CSS starting point (check its license), then re-skin with this system's exact tokens.
7. Update this file when a new structural pattern is deliberately added — not for one-off exceptions, only for things meant to be reused.

## Known Gaps

- No documented dark/light mode split — the system has exactly one mode (dark gradient); a light mode has never been designed.
- The root huisstijl-tool is still mostly a prototype (`glass.html` + a bare `templates/index.html`); most of the *shipped, tested* component patterns currently live in klusapp, not the root tool itself.
- No formal design tool (Figma etc.) backs this — `glass.html` itself is the single source of truth, plus this file as its structured summary.
- Chart/data-visualization styling isn't covered here; nothing in either product renders a chart yet.
