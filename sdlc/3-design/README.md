# 3 — Design

Design components built from the specs in `../2-specs/`, organized by target.

An item leaves this stage when its implementation task is written in
`../4-tasks/`.

## Structure
- `figma/` — Figma source of truth (design origin). See `figma/AGENTS.md`.

This project is a Flutter app, not a web component library — the scaffold's
`react/`/`vue/` mirror targets and their Storybook rule were dropped. Design
components are implemented directly as Flutter widgets in `lib/`; there is no
separate implementation-mirror stage here. If that changes, re-add a target
folder under `3-design/` with its own `AGENTS.md`.

Naming conventions in [`AGENTS.md`](AGENTS.md).
