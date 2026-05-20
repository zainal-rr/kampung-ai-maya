from __future__ import annotations

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from harness_checkpoint_migration import snapshot_or_migrate
from harness_graph import HarnessGraphRunner


async def snapshot_for_run(db_path: str, run: dict) -> dict:
    async with AsyncSqliteSaver.from_conn_string(db_path) as saver:
        await saver.setup()
        graph = HarnessGraphRunner(db_path)._build_graph().compile(checkpointer=saver)
        config = {"configurable": {"thread_id": str(run["thread_id"])}}
        values = await snapshot_or_migrate(db_path, graph, config, run)
    return values
