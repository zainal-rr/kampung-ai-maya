import asyncio
import aiosqlite
import os

DB_PATH = "/Users/zainalabidinjamal/projects/kampung-ai/session_history.db"

async def prune():
    async with aiosqlite.connect(DB_PATH) as db:
        # 1. Identify duplicates
        cursor = await db.execute("SELECT count(*), content FROM knowledge_base GROUP BY content")
        rows = await cursor.fetchall()
        
        total_before = sum(r[0] for r in rows)
        unique_after = len(rows)
        
        # 2. Create temp table with unique content
        await db.execute("CREATE TABLE knowledge_base_temp AS SELECT MIN(id) as id, category, content, tags FROM knowledge_base GROUP BY content")
        
        # 3. Swap tables
        await db.execute("DROP TABLE knowledge_base")
        await db.execute("ALTER TABLE knowledge_base_temp RENAME TO knowledge_base")
        await db.commit()
        
        print(f"Total chunks before: {total_before}")
        print(f"Total chunks after pruning: {unique_after}")
        print(f"Pruned {total_before - unique_after} redundant entries.")

if __name__ == "__main__":
    asyncio.run(prune())
