from tests.evals.memory_recall_eval_compare import *  # noqa: F401,F403
from tests.evals.memory_recall_eval_compare import _main


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(_main()))
