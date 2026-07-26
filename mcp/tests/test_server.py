"""Smoke test: the FastMCP app builds and registers the expected surface."""

from sdlc_mcp import server


async def test_tools_registered():
    tools = await server.mcp.list_tools()
    names = {t.name for t in tools}
    expected = {
        "allocate_id",
        "resolve_id",
        "read_artifact",
        "read_prd",
        "validate_tree",
        "audit_history",
        "business_task_create",
        "module_create",
        "actor_create",
        "entity_create",
        "event_create",
        "use_case_create",
        "entomb_artifact",
        "prd_add_requirement",
    }
    assert expected <= names


async def test_prompts_registered():
    prompts = await server.mcp.list_prompts()
    names = {p.name for p in prompts}
    assert {"run_pass", "new_feature", "tdd_task"} <= names
