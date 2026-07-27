# 3 — Design

Design components built from the specs in `../2-specs/`, organized by target.

An item leaves this stage when its implementation task is written in
`../4-tasks/`.

## Structure
- `figma/` — Figma source of truth (design origin). See `figma/AGENTS.md`.
- `react/` — React component implementations.
- `vue/` — Vue component implementations.

Naming and size conventions in [`AGENTS.md`](AGENTS.md).

## Rule: every component ships a Storybook story covering all its internal states
Each component in `react/` and `vue/` must have its own Storybook
(`*.stories.*`) so it can be viewed, tested, and reviewed in isolation — and the
story must cover every internal state the component can be in, matching the
Figma component it mirrors. A single default story does not satisfy this.
