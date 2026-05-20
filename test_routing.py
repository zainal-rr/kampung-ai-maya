import asyncio
import os
from orchestrator import Orchestrator
from dotenv import load_dotenv

# Set logging to capture the handoff
import logging
logging.basicConfig(level=logging.INFO)

async def test_flow():
    load_dotenv()

    orch = Orchestrator()
    # Force vision presence for test
    orch.vision.is_present = True
    
    test_input = "Wey Maya, tolong tulis simple Python script to calculate the area of a circle? I pun nak tau macam mana concept idempotency tu works in real life."
    print(f"\n[TEST] Sending input: {test_input}")
    
    # We run() and expect to see Gemini route to Artisan (Kimi)
    response = await orch.run(test_input)
    
    print("\n" + "="*50)
    print("FINAL RESPONSE FROM ENGINE:")
    print("="*50)
    print(response)
    print("="*50)
    
    # Close DB connection
    if orch.conn:
        await orch.conn.close()

if __name__ == "__main__":
    asyncio.run(test_flow())
