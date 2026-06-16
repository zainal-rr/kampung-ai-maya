import asyncio
import os
from dotenv import load_dotenv
from sieve import SieveNode

async def test_sieve():
    load_dotenv()
    # Mocking the watch directory
    watch_dir = "/Users/zainalabidinjamal/projects/kampung-ai/omi_sync"
    db_path = "/Users/zainalabidinjamal/projects/kampung-ai/session_history.db"
    
    sieve = SieveNode(watch_dir, db_path)
    
    test_transcript = "Zainal: Wey Maya, tolong ingatkan I esok pagi pukul 9 ada meeting dengan vendor. Pastu jangan lupa check server log."
    print(f"[TEST] Processing transcript: {test_transcript}")
    
    distilled = await sieve.extract_high_value_intent(test_transcript)
    print(f"[TEST] Distilled result: {distilled}")

if __name__ == "__main__":
    asyncio.run(test_sieve())
