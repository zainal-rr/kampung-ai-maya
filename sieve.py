import asyncio
import os
import logging

from models import TheSenses
from hardware_event_store import record_hardware_event
from omi_adapter import load_omi_transcript
from storage import add_knowledge_chunk, init_db

logger = logging.getLogger("maya.omi")

class SieveNode:
    """
    SieveNode: The gateway for Omi transcripts.
    Filters noise, extracts intent, and prepares high-value context for Maya.
    """
    def __init__(self, watch_dir: str, db_path: str):
        self.watch_dir = watch_dir
        self.db_path = db_path
        self.senses = TheSenses(os.getenv("GOOGLE_API_KEY", "dummy"))
        
        # Ensure watch directory exists
        os.makedirs(self.watch_dir, exist_ok=True)

    def is_noise(self, text: str) -> bool:
        """Simple heuristic to skip obviously useless transcripts."""
        noise_markers = ["[silence]", "[music]", "[unintelligible]", "unknown speaker"]
        text_lower = text.lower()
        
        if len(text.strip()) < 15: # Too short
            return True
        if any(marker in text_lower for marker in noise_markers):
            return True
        return False

    async def extract_high_value_intent(self, transcript: str) -> str:
        """Uses TheSenses (Gemini 3.1 Flash) to distill the transcript into a memory chunk."""
        prompt = [
            {"role": "system", "content": "You are the Sieve Node for Kampung AI. "
                                          "Your job is to take a raw transcript (English, Malay, or Manglish) and distill it into a concise, high-value memory chunk. "
                                          "Focus on: Decisions made, tasks mentioned, people named, or new facts learned. "
                                          "If the transcript is just small talk, return 'NO_VALUE'."},
            {"role": "user", "content": f"Transcript: {transcript}"}
        ]
        
        try:
            distilled = await self.senses.chat(prompt)
            return distilled.strip()
        except Exception as e:
            logger.error("Gemini distillation failed: %s", e)
            return "ERROR_PROCESSING"

    async def process_file(self, filename: str):
        """Processes a single transcript file."""
        file_path = os.path.join(self.watch_dir, filename)
        try:
            transcript = load_omi_transcript(file_path)
            await record_hardware_event(
                self.db_path,
                source="omi",
                event_type="transcript",
                payload={
                    "source": transcript.source_name,
                    "timestamp": transcript.timestamp,
                    "text": transcript.text[:500],
                    "confidence": transcript.confidence,
                    "device_id": transcript.device_id,
                    "ingestion_status": "queued",
                },
                status="queued",
            )
            content = transcript.text
            
            if self.is_noise(content):
                logger.info("Skipping %s: Noise detected.", filename)
                os.remove(file_path)
                return

            distilled = await self.extract_high_value_intent(content)
            
            if distilled != "NO_VALUE" and distilled != "ERROR_PROCESSING":
                logger.info("Distilled high-value memory from %s.", filename)
                await add_knowledge_chunk(
                    self.db_path,
                    distilled,
                    category="omi_transcript",
                    tags=transcript.source_tag,
                )
            
            # Move to processed or delete
            os.remove(file_path)
            
        except Exception as e:
            logger.error("Failed to process %s: %s", filename, e)

    async def run(self):
        """Polls the watch directory for new Tailscale syncs."""
        logger.info("Sieve Node monitoring: %s", self.watch_dir)
        while True:
            files = [f for f in os.listdir(self.watch_dir) if f.endswith(".txt") or f.endswith(".json")]
            for file in files:
                await self.process_file(file)
            
            await asyncio.sleep(10) # Wait 10 seconds before next poll

if __name__ == "__main__":
    # Configuration
    WATCH_DIR = "/Users/zainalabidinjamal/projects/kampung-ai/omi_sync"
    DB_PATH = "/Users/zainalabidinjamal/projects/kampung-ai/session_history.db"
    
    async def main():
        await init_db(DB_PATH)
        sieve = SieveNode(WATCH_DIR, DB_PATH)
        await sieve.run()

    asyncio.run(main())
