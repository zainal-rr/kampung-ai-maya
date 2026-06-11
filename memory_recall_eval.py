from tests.evals.memory_recall_eval import *  # noqa: F401,F403
from tests.evals.memory_recall_eval import _main


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(_main()))
