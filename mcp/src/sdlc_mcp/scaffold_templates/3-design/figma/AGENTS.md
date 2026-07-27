# Figma — design source of truth

The Figma file is the origin for all design components. React and Vue
implementations are derived from / synced against it.

## Figma file link

> **TODO:** paste the Figma file URL here.
>
> `https://www.figma.com/file/<FILE_KEY>/<FILE_NAME>`

## Conventions
- Components in Figma map 1:1 to components in `../react/` and `../vue/`.
- Keep component names consistent across Figma, React, and Vue.
- Every component must have a corresponding **Storybook** story in each
  framework folder, covering all of its internal states — no component is
  "done" until every state it can be in appears there.
