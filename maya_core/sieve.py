import asyncio
import os
import logging
from pathlib import Path

from maya_core.models import TheSenses
from maya_core.hardware_event_store import record_hardware_event
from maya_core.omi_adapter import load_omi_transcript
from maya_core.omi_context_sieve import ingest_omi_decision, is_omi_noise, sieve_omi_transcript
from maya_core.storage import init_db

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
        Path(self.watch_dir).mkdir(parents=True, exist_ok=True)

    def is_noise(self, text: str) -> bool:
        """Simple heuristic to skip obviously useless transcripts."""
        return is_omi_noise(text)

    async def extract_high_value_intent(self, transcript: str) -> str:
        """Uses TheSenses (Gemini 3.1 Flash) to distill the transcript into a memory chunk."""
        decision = await sieve_omi_transcript(transcript, self._distill_with_gemini)
        return decision.summary if decision.accepted else "NO_VALUE"

    async def process_file(self, filename: str):
        """Processes a single transcript file."""
        watch_root = Path(self.watch_dir).expanduser().resolve(strict=False)
        file_path = (watch_root / filename).resolve(strict=False)
        if not _within(file_path, watch_root):
            logger.warning("Skipping Omi file outside watch directory: %s", filename)
            return
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
            
            decision = await sieve_omi_transcript(content, self._distill_with_gemini)
            if decision.accepted:
                logger.info("Distilled high-value memory from %s.", filename)
                await ingest_omi_decision(
                    self.db_path,
                    decision,
                    source_ref=f"{transcript.source_name}:{transcript.timestamp or filename}",
                )
            else:
                logger.info("Skipping %s: %s.", filename, decision.status)
            
            # Move to processed or delete
            file_path.unlink(missing_ok=True)
            
        except Exception as e:
            logger.error("Failed to process %s: %s", filename, e)

    async def _distill_with_gemini(self, prompt: str) -> str:
        try:
            return (await self.senses.chat([{"role": "user", "content": prompt}])).strip()
        except Exception as e:
            logger.error("Gemini Omi distillation failed: %s", e)
            return ""

    async def run(self):
        """Polls the watch directory for new Tailscale syncs."""
        logger.info("Sieve Node monitoring: %s", self.watch_dir)
        while True:
            files = [f.name for f in Path(self.watch_dir).iterdir() if f.name.endswith(".txt") or f.name.endswith(".json")]
            for file in files:
                await self.process_file(file)
            
            await asyncio.sleep(10) # Wait 10 seconds before next poll

if __name__ == "__main__":
    # Configuration: env-driven, defaulting to paths relative to this repo.
    from maya_core.repo_paths import repo_root

    _ROOT = repo_root(__file__)
    WATCH_DIR = os.getenv("OMI_WATCH_DIR", str(_ROOT / "omi_sync"))
    DB_PATH = os.getenv("KAMPUNG_DB_PATH", str(_ROOT / "session_history.db"))


    async def main():
        await init_db(DB_PATH)
        sieve = SieveNode(WATCH_DIR, DB_PATH)
        await sieve.run()

    asyncio.run(main())


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
