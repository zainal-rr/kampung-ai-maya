import asyncio
import aiosqlite
import os

from maya_core.repo_paths import repo_root

# Paths
BASE_DIR = str(repo_root(__file__))
CHROMA_DB_PATH = os.path.join(BASE_DIR, "_archive_v2/chroma_db/chroma.sqlite3")
SESSION_DB_PATH = os.path.join(BASE_DIR, "session_history.db")

async def migrate():
    if not os.path.exists(CHROMA_DB_PATH):
        print(f"Error: ChromaDB not found at {CHROMA_DB_PATH}")
        return

    print(f"Connecting to legacy ChromaDB at {CHROMA_DB_PATH}...")
    
    # Connect to ChromaDB (Legacy)
    async with aiosqlite.connect(CHROMA_DB_PATH) as chroma_db:
        chroma_db.row_factory = aiosqlite.Row
        
        # 1. Fetch content from Full Text Search table
        cursor = await chroma_db.execute("SELECT id, c0 FROM embedding_fulltext_search_content")
        docs = await cursor.fetchall()
        
        knowledge_items = []
        for doc in docs:
            doc_id = doc['id']
            content = doc['c0']
            
            # 2. Fetch associated metadata
            m_cursor = await chroma_db.execute(
                "SELECT key, string_value FROM embedding_metadata WHERE id = ?", (doc_id,)
            )
            metadata = await m_cursor.fetchall()
            
            category = "general"
            tags_list = []
            for m in metadata:
                key, val = m['key'], m['string_value']
                if key == 'topic':
                    category = val
                elif key == 'source':
                    tags_list.append(f"source:{val}")
                elif key == 'tags':
                    tags_list.append(val)
                elif key not in ('chroma:document', 'id'):
                    tags_list.append(f"{key}:{val}")
            
            knowledge_items.append({
                "category": category,
                "content": content,
                "tags": ", ".join(tags_list)
            })

    print(f"Extracted {len(knowledge_items)} chunks. Migrating to {SESSION_DB_PATH}...")

    # Connect to the new Local architecture DB
    async with aiosqlite.connect(SESSION_DB_PATH) as session_db:
        # Create the knowledge_base table
        await session_db.execute('''
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                content TEXT,
                tags TEXT
            )
        ''')
        
        # Clear existing to avoid duplicates if re-run
        await session_db.execute("DELETE FROM knowledge_base")
        
        # Insert legacy chunks
        for item in knowledge_items:
            await session_db.execute(
                "INSERT INTO knowledge_base (category, content, tags) VALUES (?, ?, ?)",
                (item['category'], item['content'], item['tags'])
            )
        
        await session_db.commit()
        print(f"Success: Ported {len(knowledge_items)} knowledge chunks into 'knowledge_base' table.")

if __name__ == "__main__":
    asyncio.run(migrate())
