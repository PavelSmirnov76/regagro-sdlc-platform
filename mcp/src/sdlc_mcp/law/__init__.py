"""Pure functions implementing the SDLC pipeline law.

Nothing in this package knows about MCP, SQLite, or the network. Every function
takes an explicit ``sdlc_root: Path`` and operates only on the file tree, which
makes the law fully testable against a throwaway temp tree.

The law (see the project's ``sdlc/AGENTS.md``):

* artifacts are **frozen** on write — never edited in place (PRD excepted);
* "change" means issuing a **new id** and **entombing** the old one;
* ids are **permanent and monotonic** per type, derived from filenames;
* citations are Markdown links whose visible text is the bare id.
"""
