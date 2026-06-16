import asyncio
import aiosqlite
import re

DB_PATH = "/Users/zainalabidinjamal/projects/kampung-ai/session_history.db"

async def deep_prune():
    async with aiosqlite.connect(DB_PATH) as db:
        # Identify noise: 'ping', 'system_health', etc.
        patterns = [
            r"User: ping \| Maya: Here",
            r"call the system_health tool right now",
            r"Ini adalah ujian transkript Bahasa Melayu"
        ]
        
        total_deleted = 0
        
        # Simple LIKE deletions for noise
        noise_queries = [
            "%User: ping | Maya:%",
            "%system_health tool%",
            "%ujian transkript Bahasa Melayu%"
        ]
        
        for q in noise_queries:
            cursor = await db.execute("DELETE FROM knowledge_base WHERE content LIKE ?", (q,))
            total_deleted += cursor.rowcount
            
        await db.commit()
        
        cursor = await db.execute("SELECT count(*) FROM knowledge_base")
        final_count = (await cursor.fetchone())[0]
        
        print(f"Deep Pruning Complete.")
        print(f"Removed {total_deleted} noise/ping/test entries.")
        print(f"Final High-Value Memory Count: {final_count}")

if __name__ == "__main__":
    asyncio.run(deep_prune())
