"""The FastMCP server — exposes :class:`SdlcService` as MCP tools/resources/prompts.

Run over stdio (for Claude Code) with ``sdlc-mcp`` or
``python -m sdlc_mcp.server``. Each tool is a thin wrapper: the law and the
audit/transcript side effects live in the service, not here.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import prompts
from .config import load_config
from .service import SdlcService

mcp = FastMCP("sdlc-platform")

_service: SdlcService | None = None


def service() -> SdlcService:
    """Lazily-built singleton service (opens the audit db, starts a session)."""
    global _service
    if _service is None:
        _service = SdlcService()
    return _service


# --------------------------------------------------------------------------- #
# Reads / ids / validation
# --------------------------------------------------------------------------- #
@mcp.tool()
def allocate_id(artifact_type: str) -> dict:
    """Next free id for a type (BT, MOD, ACTOR, ENT, EVT, UC, FIG, TC). Read-only."""
    return {"id": service().allocate_id(artifact_type)}


@mcp.tool()
def resolve_id(artifact_id: str) -> dict:
    """Locate an id: its path and whether it is entombed (obsolete)."""
    return service().resolve_id(artifact_id)


@mcp.tool()
def read_artifact(artifact_id: str) -> str:
    """Full Markdown of an artifact by id (live preferred, else entombed)."""
    return service().read_artifact(artifact_id)


@mcp.tool()
def list_artifacts(artifact_type: str) -> list[dict]:
    """All artifacts of a type: id, path, is_obsolete."""
    return service().list_artifacts(artifact_type)


@mcp.tool()
def read_prd() -> str:
    """The current PRD."""
    return service().read_prd()


@mcp.tool()
def validate_tree() -> dict:
    """Check tree integrity: id collisions (errors) + dangling/stale citations."""
    return service().validate()


@mcp.tool()
def audit_history(
    artifact_id: str | None = None,
    artifact_type: str | None = None,
    session_id: str | None = None,
    action: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Change history (who/what/when), most recent first, with optional filters."""
    return service().audit_history(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        session_id=session_id,
        action=action,
        limit=limit,
    )


@mcp.tool()
def transcript_read() -> list[dict]:
    """The current session's transcript (append-only interaction log)."""
    return service().transcript_read()


@mcp.tool()
def session_note(text: str) -> dict:
    """Record a free-text note into the audit ledger and session transcript."""
    return service().session_note(text)


# --------------------------------------------------------------------------- #
# Business tasks
# --------------------------------------------------------------------------- #
@mcp.tool()
def business_task_create(
    name: str,
    requirements: list[str] | None = None,
    title: str | None = None,
    kind: str = "planning",
    severity: str | None = None,
    raw_note: str = "нет.",
    current_state: str = "TBD.",
    what_to_do: str = "TBD.",
    acceptance: list[str] | None = None,
    open_questions: str = "Нет.",
    surfaced_by: str | None = None,
    supersede_of: str | None = None,
) -> dict:
    """Create a business task (BT). ``name`` is the ASCII filename token (e.g. BOARD);
    ``requirements`` are R-ids it serves; ``kind`` is 'planning' or 'observation'
    (then set ``severity`` = ERROR/WARNING/INFO)."""
    return service().create_business_task(
        name=name, requirements=requirements, title=title, kind=kind,
        severity=severity, raw_note=raw_note, current_state=current_state,
        what_to_do=what_to_do, acceptance=acceptance, open_questions=open_questions,
        surfaced_by=surfaced_by, supersede_of=supersede_of,
    )


# --------------------------------------------------------------------------- #
# Specs
# --------------------------------------------------------------------------- #
@mcp.tool()
def module_create(
    name: str,
    derived_from_bt: str,
    purpose: str = "TBD.",
    composition: str = "TBD.",
    boundary: str = "TBD.",
    supersede_of: str | None = None,
) -> dict:
    """Create a module (MOD). ``name`` = one UPPERCASE token; cite the BT it derives from."""
    return service().create_module(
        name=name, derived_from_bt=derived_from_bt, purpose=purpose,
        composition=composition, boundary=boundary, supersede_of=supersede_of,
    )


@mcp.tool()
def actor_create(
    name: str,
    module: str,
    title: str,
    identity: str = "TBD.",
    goals: str = "TBD.",
    permissions: str = "TBD.",
    interacts: list[str] | None = None,
    supersede_of: str | None = None,
) -> dict:
    """Create an actor (ACTOR-…-IN-MODULE). ``interacts`` = ids it interacts with."""
    return service().create_actor(
        name=name, module=module, title=title, identity=identity, goals=goals,
        permissions=permissions, interacts=interacts, supersede_of=supersede_of,
    )


@mcp.tool()
def entity_create(
    name: str,
    module: str,
    title: str,
    owning_module: str,
    description: str = "TBD.",
    fields: list[list[str]] | None = None,
    source_rows: list[list[str]] | None = None,
    supersede_of: str | None = None,
) -> dict:
    """Create an entity (ENT-…-IN-MODULE). ``fields`` rows = [name, type, desc];
    ``source_rows`` = [file, symbol, status, role]; cite the owning MOD id."""
    return service().create_entity(
        name=name, module=module, title=title, owning_module=owning_module,
        description=description, fields=fields, source_rows=source_rows,
        supersede_of=supersede_of,
    )


@mcp.tool()
def event_create(
    name: str,
    module: str,
    title: str,
    initiator: str,
    entities: list[str],
    trigger: str = "TBD.",
    effect: str = "TBD.",
    source: str = "TBD.",
    supersede_of: str | None = None,
) -> dict:
    """Create an event (EVT-…-IN-MODULE), past-tense name, exactly one ``initiator``
    (an ACTOR id); ``entities`` = entity ids it acts on."""
    return service().create_event(
        name=name, module=module, title=title, initiator=initiator,
        entities=entities, trigger=trigger, effect=effect, source=source,
        supersede_of=supersede_of,
    )


@mcp.tool()
def use_case_create(
    actor_id: str,
    evt_id: str,
    ent_id: str,
    crud: str,
    outcome: str,
    module: str,
    title: str,
    purpose: str = "TBD.",
    current_main: str = "TBD.",
    current_alt: str = "Нет.",
    related_entities: list[str] | None = None,
    business_rules: str = "Нет.",
    target: str = "Не отличается от CURRENT.",
    tbd: str = "Нет.",
    tech_deps: str = "TBD.",
    acceptance: list[str] | None = None,
    tests: str = "TBD — теста нет.",
    open_questions: str = "Нет.",
    supersede_of: str | None = None,
) -> dict:
    """Create a use-case. ``crud`` ∈ CREATE/READ/UPDATE/DELETE, ``outcome`` ∈
    OK/ERROR/REJECTED; ``actor_id``/``evt_id``/``ent_id`` must already exist."""
    return service().create_use_case(
        actor_id=actor_id, evt_id=evt_id, ent_id=ent_id, crud=crud, outcome=outcome,
        module=module, title=title, purpose=purpose, current_main=current_main,
        current_alt=current_alt, related_entities=related_entities,
        business_rules=business_rules, target=target, tbd=tbd, tech_deps=tech_deps,
        acceptance=acceptance, tests=tests, open_questions=open_questions,
        supersede_of=supersede_of,
    )


# --------------------------------------------------------------------------- #
# Entomb + PRD
# --------------------------------------------------------------------------- #
@mcp.tool()
def entomb_artifact(artifact_id: str, why: str, superseded_by: str | None = None) -> dict:
    """Retire an artifact: move it to obsolete/ with a header. Never deletes."""
    return service().entomb_artifact(artifact_id, why=why, superseded_by=superseded_by)


@mcp.tool()
def prd_add_requirement(text: str) -> dict:
    """Add a new R{n} requirement to the PRD (in place, with a history snapshot)."""
    return service().prd_add_requirement(text)


@mcp.tool()
def prd_deprecate_requirement(rid: str, replaced_by: str) -> dict:
    """Mark an R{n} deprecated in place, naming the R{n} that replaced it."""
    return service().prd_deprecate_requirement(rid, replaced_by)


@mcp.tool()
def prd_propose_edit(new_text: str, why: str) -> dict:
    """Rewrite the PRD wholesale (snapshots the old version to history/ first)."""
    return service().prd_propose_edit(new_text, why)


# --------------------------------------------------------------------------- #
# Scaffold a new project
# --------------------------------------------------------------------------- #
@mcp.tool()
def scaffold_project(
    target: str,
    container: str = "sdlc",
    project_name: str = "Project",
    force: bool = False,
    dry_run: bool = False,
    host_pointer: bool = True,
) -> dict:
    """Scaffold the numbered SDLC pipeline (0-vibes … 9-observation, per-stage
    README/AGENTS/CLAUDE + RUNBOOK) into ``target`` — structure & conventions
    only, no domain content. Use to start a new project on this workflow. Lands
    in ``target/<container>`` (default ``sdlc``); ``{{PROJECT_NAME}}`` is filled
    from ``project_name``; idempotent (skips existing unless ``force``, which
    backs up first); a marked pointer is added to the host CLAUDE.md. Preview
    with ``dry_run=True``. After scaffolding, do the adaptation pass (set the
    stage list, prune unused stages/design targets)."""
    return service().scaffold_project(
        target=target, container=container, project_name=project_name,
        force=force, dry_run=dry_run, host_pointer=host_pointer,
    )


# --------------------------------------------------------------------------- #
# External actions (real when configured, otherwise recorded fakes)
# --------------------------------------------------------------------------- #
@mcp.tool()
def open_pull_request(
    title: str, body: str = "", base: str | None = None, head: str | None = None
) -> dict:
    """Open a PR in the app repo (git push + gh pr create). ``base`` defaults to
    the project's configured base branch (APP_BASE_BRANCH); ``head`` defaults to
    the repo's current branch. Falls back to a recorded fake if the app repo /
    gh aren't configured — see docs/SETUP.md."""
    return service().open_pull_request(title=title, body=body, base=base, head=head)


@mcp.tool()
def build_and_deliver_apk(flavor: str = "prod", caption: str | None = None) -> dict:
    """Build the app APK (flutter) and deliver it to Telegram. Falls back to
    fakes without app repo / bot credentials — see docs/SETUP.md."""
    return service().build_and_deliver_apk(flavor=flavor, caption=caption)


# --------------------------------------------------------------------------- #
# Resources
# --------------------------------------------------------------------------- #
@mcp.resource("sdlc://prd")
def prd_resource() -> str:
    return service().read_prd()


@mcp.resource("sdlc://artifact/{artifact_id}")
def artifact_resource(artifact_id: str) -> str:
    return service().read_artifact(artifact_id)


@mcp.resource("sdlc://index/{artifact_type}")
def index_resource(artifact_type: str) -> str:
    rows = service().list_artifacts(artifact_type)
    return "\n".join(
        f"{r['id']}\t{'(obsolete) ' if r['is_obsolete'] else ''}{r['path']}"
        for r in rows
    )


# --------------------------------------------------------------------------- #
# Prompts
# --------------------------------------------------------------------------- #
@mcp.prompt()
def run_pass() -> str:
    """How to run one SDLC pass (absorb → PRD delta → propose → issue/entomb)."""
    return prompts.RUN_PASS


@mcp.prompt()
def new_feature() -> str:
    """How to take a human request from idea to a coding task through the pipeline."""
    return prompts.NEW_FEATURE


@mcp.prompt()
def tdd_task() -> str:
    """The red→green→refactor loop for implementing a coding task."""
    return prompts.TDD_TASK


def main() -> None:
    cfg = load_config()
    if cfg.transport == "stdio":
        mcp.run()
        return
    from .transport import run_http

    run_http(mcp, cfg)


if __name__ == "__main__":  # pragma: no cover
    main()
