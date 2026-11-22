# DESIGN.md — Dubai Travel Planner

Adapted from the Airbnb analysis in [awesome-design-md](https://github.com/voltagent/awesome-design-md)
(full source: https://getdesign.md/airbnb/design-md). We borrow the *style*: a warm, photo-friendly
marketplace look with a white canvas, ink type, one coral accent, soft radii and a single shadow tier.
We do not use Airbnb's logo, wordmark or proprietary font. Tokens live in `app/globals.css` `:root`.

The public pages, including `/` and `/audit`, do not use this file. They use `app/journey.css` (ivory, navy, teal) and speak to someone planning a trip. `/audit` is the "check a chatbot plan" page: a verdict, the names we recognized, the names we could not find, and a rebuilt day list. The coral tokens below stay on the developer dashboard under `/dev`.

## Tokens

| Token | Value | Use |
|---|---|---|
| `--primary` | `#ff385c` | The only accent: primary CTA, brand mark, running-node dot, map markers, "Day N" label |
| `--primary-active` | `#e00b41` | CTA press state |
| `--primary-disabled` | `#ffd1da` | Disabled CTA |
| `--ink` | `#222222` | Headings, body, active tabs, selected pills, budget bars. Never pure black |
| `--body` / `--muted` | `#3f3f3f` / `#6a6a6a` | Long copy / secondary text |
| `--hairline` / `--hairline-soft` | `#dddddd` / `#ebebeb` | Card borders / row dividers |
| `--border-strong` | `#b0b0b0` | Form input outlines |
| `--canvas` / `--surface-soft` / `--surface-strong` | `#fff` / `#f7f7f7` / `#f2f2f2` | Page / subtle fills / icon circles |
| `--error` / `--warn` / `--ok` | `#c13515` / `#b4690e` / `#008a05` | Semantic only |
| `--radius-sm` / `--radius-md` / pill | 8px / 14px / 999px | Buttons + inputs / cards / chips, badges, nav links |
| `--shadow` | single tier | Reservation card, banners, hover lift. No other shadows |

Type: Inter (via `next/font`), falling back to the system stack. Modest weights: h1 28px/700,
card titles 22px/600, day titles 20px/600, body 16px/400, meta 14px. The one loud moment is the
budget total at 64px/700 (the "rating display").

Spacing: 4px base; 16px gaps inside cards, 24px card padding and column gaps, 32px between major regions.

## Rules

1. Use `--primary` sparingly: one or two coral moments per screen. Everything else is white + ink.
2. Every interactive element is rounded. No hard corners.
3. Cards are flat with a hairline border; only the trip form (`.reserve`) and floating banners get the shadow. Itinerary day cards lift on hover.
4. Inputs: 8px radius, `--border-strong` outline; focus is a 2px ink border, no glow or color ring.
5. Grouped fields use the segmented box (`.fields`): hairline-divided cells, a tiny uppercase caption label above the value.
6. Filters/presets are outline pills; selected = ink fill, white text.
7. Tabs: muted labels, active = ink with a 2px ink underline.
8. Ratings, totals and status use ink or semantic colors, never the accent, except "over budget" which uses the error red on a coral tint.

## Components

- **Top nav** `.topnav`: white, 80px (64px mobile), hairline bottom, brand left, outline pill links right.
- **Reservation card** `.card.reserve`: trip request, preset pills, segmented fields, full-width coral CTA.
- **Day card** `.day`: coral "Day N" label, theme title, time column + activity rows, transport legs as soft pills.
- **Stay card** `.stay`: round icon, name, area · tier.
- **Badge** `.badge`: white pill, hairline border, 11px/600.
- **Timeline**: status dots (coral = running with halo, ink = done, red = error, amber = revision).

## Responsive

- `< 744px`: single column, 16px gutters, slot rows stack, tabs scroll horizontally.
- `744–1128px`: narrower left rail.
- `> 1128px`: content caps at 1280px.
