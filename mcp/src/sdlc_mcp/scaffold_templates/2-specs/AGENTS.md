Specs expand planning tasks into actors, entities, events, and use-cases.

Generate in this order — each step depends on the one before it:

1. Read the planning business tasks (`BT-{n}-PLANNING-…`) this spec set derives from.
2. Define the modules in `modules/`. Every other spec id names its module, so a
   module invented later leaves those ids pointing at nothing.
3. Derive actors, entities, and events into their folders.
4. Derive use-cases last — a use-case cites ids that must already exist.

Every id carries its module as the `-IN-{MODULE}` suffix.

Each subfolder states its own naming scheme. Read it before generating into it.
