Each component should have naming

FIG-{number}-{TYPE}-{VARIANT1-name}-{value}-{VARIANT2-name}-{value}...

Cite the use-case (`UC-{number}`) and entity (`ENT-{number}`) ids the component
serves.

Typography/color/spacing constants are not restated here — this project already
has one home for them: `lib/theme/app_typography.dart` and
`lib/theme/app_colors.dart` (see `.claude/rules/ui-architecture.md`). Pull real
values from Figma into those files, never hardcode inline, never duplicate them
into this AGENTS.md as a second copy that can drift.

Figma access in this project is read-only — see `.claude/rules/figma-read-only.md`.
No write/create/update/delete calls into Figma from any agent working this stage.
