from __future__ import annotations

from maya_harness.harness_store import finish_run, record_event


async def snapshot_or_migrate(db_path: str, graph, config: dict, run: dict) -> dict:
    snapshot = await graph.aget_state(config)
    if snapshot.values:
        return dict(snapshot.values)
    state = dict(run.get("state") or {})
    if not state:
        await finish_run(db_path, str(run["run_id"]), status="needs_manual_resume")
        return {}
    state["run_id"] = str(run["run_id"])
    state["thread_id"] = str(run["thread_id"])
    state.setdefault("schema_version", 1)
    await graph.aupdate_state(config, state, as_node="finish")
    await record_event(db_path, str(run["run_id"]), "checkpoint_migration", "seeded from state_json")
    return state
