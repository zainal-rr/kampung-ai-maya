import os
import re
from typing import TypedDict, List, Dict, Annotated, Sequence
import operator

import aiosqlite
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from models import TheMind, TheHands, TheSenses, TheNews
from orchestrator_prompts import (
    ARTISAN_SYSTEM_PROMPT,
    GEMINI_ROUTING_PROMPT,
    MIND_ESCALATION_PROMPT,
    TECHNICAL_KEYWORDS,
)
from vision import VisionNode
import atexit

# Define the state
class AgentState(TypedDict):
    messages: Annotated[Sequence[Dict[str, str]], operator.add]
    next_node: str
    final_response: str

class Orchestrator:
    def __init__(self, db_path="session_history.db"):
        # Initialize models from env
        # Note: In a real scenario, we'd ensure these keys exist
        self.mind = TheMind(os.getenv("OPENAI_API_KEY", "dummy"))
        self.hands = TheHands(os.getenv("KIMI_API_KEY", "dummy"))
        self.senses = TheSenses(os.getenv("GOOGLE_API_KEY", "dummy"))
        self.news = TheNews(os.getenv("XAI_API_KEY", "dummy"))
        self.db_path = db_path

        # Initialize and start VisionNode for presence gatekeeping
        self.vision = VisionNode()
        self.vision.start()
        atexit.register(self.vision.stop)

        self.app = None
        self.checkpointer = None
        self.conn = None

    async def initialize(self):
        """Asynchronous initialization for components that require a running loop."""
        if self.app:
            return

        # Build Graph
        workflow = StateGraph(AgentState)

        workflow.add_node("supervisor", self.supervisor_node)
        workflow.add_node("artisan", self.artisan_node)
        workflow.add_node("sight", self.sight_node)
        workflow.add_node("pulse", self.pulse_node)
        workflow.add_node("library", self.library_node)

        workflow.set_entry_point("supervisor")

        workflow.add_conditional_edges(
            "supervisor",
            self.should_continue,
            {
                "artisan": "artisan",
                "sight": "sight",
                "pulse": "pulse",
                "library": "library",
                "end": END
            }
        )

        workflow.add_edge("artisan", "supervisor")
        workflow.add_edge("sight", "supervisor")
        workflow.add_edge("pulse", "supervisor")
        workflow.add_edge("library", "supervisor")

        # Persistence setup
        self.conn = aiosqlite.connect(self.db_path)
        self.checkpointer = AsyncSqliteSaver(self.conn)
        self.app = workflow.compile(checkpointer=self.checkpointer)

    async def supervisor_node(self, state: AgentState):
        """Maya's routing layer decides who speaks next."""
        # Presence Gatekeeping: Privacy and Budget Filter
        if not self.vision.is_present:
            return {
                "final_response": "Zainal, I'm here, but I don't see you. I'll stay in standby until you return to the iMac.",
                "next_node": "end"
            }

        # CHECK FOR CODE/TECHNICAL INTENT FIRST (Hard Lock for Kimi)
        last_user_message = self._extract_user_text(state["messages"][-1]["content"]).upper()
        
        if any(kw in last_user_message for kw in TECHNICAL_KEYWORDS):
            print(f"\n[ORCHESTRATOR] Technical Keyword Detected. Routing to Artisan.")
            return {"next_node": "artisan"}

        # Gemini-First Routing for Chat/Linguistics
        gemini_prompt = {
            "role": "system",
            "content": GEMINI_ROUTING_PROMPT,
        }
        gemini_messages = [gemini_prompt] + list(state["messages"])
        gemini_response = await self.senses.chat(gemini_messages)

        # Handle Routing from Gemini
        if "DELEGATE TO PULSE" in gemini_response.upper():
            return {"next_node": "pulse"}
        if "DELEGATE TO LIBRARY" in gemini_response.upper():
            return {"next_node": "library"}
        if "DELEGATE TO SUPERVISOR" in gemini_response.upper():
            # Escalation to GPT-5.5 (The Mind)
            prompt = {
                "role": "system", 
                "content": MIND_ESCALATION_PROMPT,
            }
            mind_messages = [prompt] + list(state["messages"])
            response = await self.mind.chat(mind_messages)
            return {"final_response": response, "next_node": "end"}
        
        return {"final_response": gemini_response, "next_node": "end"}

    @staticmethod
    def _extract_user_text(content: str) -> str:
        marker = "[user]\n"
        lowered = content.lower()
        index = lowered.rfind(marker)
        if index >= 0:
            return content[index + len(marker):].strip()
        return content.strip()

    def should_continue(self, state: AgentState):
        return state["next_node"]

    async def add_shadow_lesson(self, error: str, fix: str, participant: str):
        """Adds a new lesson learned to the shadow memory table."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO shadow_memory (error, fix, participant) VALUES (?, ?, ?)",
                    (error, fix, participant)
                )
                await db.commit()
        except Exception as e:
            pass

    async def get_shadow_memory(self, limit=5) -> str:
        """Retrieves recent lessons from the DB shadow_memory table."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT error, fix, participant FROM shadow_memory ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                )
                rows = await cursor.fetchall()
                
                if not rows:
                    return ""
                
                output = "\n### SHADOW MEMORY (Past Lessons - Do Not Repeat These Mistakes)\n"
                for r in rows:
                    output += f"- ERROR: {r['error']}\n  FIX: {r['fix']} (Contributor: {r['participant']})\n"
                return output
        except Exception as e:
            # Silent fail for architectural integrity in production-like environments
            return ""

    async def artisan_node(self, state: AgentState):
        """Kimi - The Executor (handles ALL code)"""
        if not self.vision.is_present:
            return {"next_node": "supervisor"}

        shadow_memory = await self.get_shadow_memory(limit=5)
        
        messages = [{"role": "system", "content": ARTISAN_SYSTEM_PROMPT}]
        
        if shadow_memory:
            messages.append({"role": "system", "content": shadow_memory})
            
        messages.extend(list(state["messages"]))
        response = await self.hands.chat(messages)
        return {"messages": [{"role": "assistant", "content": f"[Artisan]: {response}"}]}

    async def sight_node(self, state: AgentState):
        """Gemini - The Observer"""
        if not self.vision.is_present:
            return {"next_node": "supervisor"}

        response = await self.senses.chat(state["messages"])
        return {"messages": [{"role": "assistant", "content": f"[Sight]: {response}"}]}

    async def pulse_node(self, state: AgentState):
        """Grok - The News"""
        if not self.vision.is_present:
            return {"next_node": "supervisor"}

        response = await self.news.chat(state["messages"])
        return {"messages": [{"role": "assistant", "content": f"[Pulse]: {response}"}]}

    async def library_node(self, state: AgentState):
        """Library - The Archivist (Legacy Knowledge)"""
        if not self.vision.is_present:
            return {"next_node": "supervisor"}

        query = state["messages"][-1]["content"]
        # Extract keywords for simple search
        keywords = re.findall(r'\b\w{4,}\b', query.lower())
        
        results = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            for word in keywords[:3]: # Limit words to search
                cursor = await db.execute(
                    "SELECT content FROM knowledge_base WHERE content LIKE ? LIMIT 2",
                    (f"%{word}%",)
                )
                rows = await cursor.fetchall()
                results.extend([r['content'] for r in rows])
        
        context = "\n---\n".join(list(set(results))[:5])
        if not context: context = "No legacy records found for those terms."
        
        return {"messages": [{"role": "assistant", "content": f"[Library Context]: {context}"}]}

    async def run(self, user_input: str, history: List[Dict[str, str]] = None):
        # Immediate entry gatekeeping
        if not self.vision.is_present:
            return "Zainal, I'm here, but I don't see you. I'll stay in standby until you return to the iMac."

        await self.initialize()

        initial_messages = list(history or [])
        initial_messages.append({"role": "user", "content": user_input})
        
        inputs = {"messages": initial_messages, "next_node": ""}
        config = {"configurable": {"thread_id": "zainal_session"}}
        final_state = await self.app.ainvoke(inputs, config=config)
        return final_state.get("final_response", "Maaf, saya tidak dapat memproses permintaan tersebut.")
