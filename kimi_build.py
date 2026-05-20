import os
import re
import asyncio
from openai import OpenAI
from config import get_env

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ENGINEERING_RULES = """
ENGINEERING RULES FOR THE ARTISAN:
1. Keep every .py file under 300 lines.
2. Keep each file responsible for one clear thing.
3. Do not split code just to satisfy line count.
4. Treat 250 to 280 lines as an early refactor warning.
5. If a change would push a file over the warning zone, extract a clean module first.
"""

async def build_project():
    kimi_api_key = get_env("KIMI_API_KEY")
    if not kimi_api_key:
        raise ValueError("KIMI_API_KEY environment variable not set.")

    client = OpenAI(
        api_key=kimi_api_key,
        base_url="https://api.moonshot.ai/v1",
    )

    # Read context
    with open(os.path.join(BASE_DIR, "KAMPUNG_AI.md"), "r", encoding="utf-8") as f:
        blueprint = f.read()
    with open(os.path.join(BASE_DIR, "KAMPUNG_AI_CHECKLIST.md"), "r", encoding="utf-8") as f:
        checklist = f.read()

    # Strategic Feedback
    feedback = """
Artisan, your first draft was too simplistic. I need a robust, production-ready system.
1. models.py: Use correct LangChain classes (ChatOpenAI for GPT-5.5 and Kimi, ChatGoogleGenerativeAI for Gemini). Use python-dotenv to load keys from .env.
2. orchestrator.py: Use the 'langgraph' library to build a real StateGraph. Nodes: 'brain_node', 'artisan_node', 'sight_node', 'pulse_node'. 
3. Budget Lock: In the orchestrator, implement a check that scans Maya's (GPT-5.5's) output. If it contains ```python or ```bash, it must trigger a transition to the artisan_node instead of returning to Zainal.
4. utils.py: Use regex to mask provider names (Anthropic, Google, Moonshot, OpenAI, xAI, Claude, Gemini, Kimi, Grok) and replace them with 'Maya'.
5. telegram_bridge.py: Implement the full async bot using python-telegram-bot's Application. Set up Mirror Mode for voice.
6. main.py: Should initialize the database and start the bot polling.
"""

    prompt = f"""You are The Artisan (Kimi k2.6). I am Maya (GPT-5.5). 
I've reviewed your initial code and it needs major improvements.

CONTEXT:
{blueprint}

{ENGINEERING_RULES}

FEEDBACK:
{feedback}

TASK:
Rewrite the core files to be high-quality and follow the 'Friendship' philosophy. 
Generate the code for:
- models.py
- orchestrator.py
- utils.py
- telegram_bridge.py
- main.py

OUTPUT EACH FILE IN A SEPARATE CODE BLOCK WITH '# filename: name.py' AS THE FIRST LINE.
"""

    print("--- Requesting REWRITE from Kimi ---")
    response = client.chat.completions.create(
        model="moonshot-v1-32k",
        messages=[
            {"role": "system", "content": "You are an expert Python developer. Follow the engineering rules exactly."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
    )

    content = response.choices[0].message.content
    print("--- Received Response ---")
    
    # Parse files
    file_pattern = r"# filename: ([\w\.]+)\n```python\n(.*?)\n```"
    files = re.findall(file_pattern, content, re.DOTALL)
    
    if not files:
        file_pattern = r"### ([\w\.]+)\n```python\n(.*?)\n```"
        files = re.findall(file_pattern, content, re.DOTALL)

    for filename, code in files:
        file_path = os.path.join(BASE_DIR, filename)
        print(f"Writing {filename}...")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code.strip())
        print(f"Finished {filename}")

if __name__ == "__main__":
    asyncio.run(build_project())
