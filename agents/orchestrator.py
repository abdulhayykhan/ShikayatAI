"""
agents/orchestrator.py
──────────────────────
ShikayatAI – Orchestrator Agent

Supervisor that strings the civic complaint pipeline together.
Runs a safety pre-check before routing through:
  Memory -> Classifier -> Researcher -> Drafter
"""

import asyncio
import json
import os
import sys
import uuid

from dotenv import load_dotenv
from google.adk.agents import SequentialAgent, LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import Client, types

# Ensure we import the factory functions for the sub-agents
# Note: we need to adapt the signatures or wrap them if they don't exactly match the simple ADK signature,
# but for ADK SequentialAgent, you just pass the agent instances.
from agents.memory_agent import make_memory_agent
from agents.classifier import _make_agent as make_classifier_agent
from agents.researcher import _make_agent as make_researcher_agent
from agents.drafter import _make_agent as make_drafter_agent

load_dotenv()

# We will use the same api key pool concept for safety check
_API_KEY = os.getenv("GOOGLE_API_KEY")

# ─────────────────────────────────────────────
# 1. Safety Pre-Check
# ─────────────────────────────────────────────

def run_safety_precheck(complaint_text: str) -> dict:
    """
    Evaluates the complaint text to ensure it's a valid civic complaint.
    Returns {"safe": True} or {"safe": False, "reason": "..."}
    """
    if len(complaint_text.strip()) < 5:
        return {
            "safe": False, 
            "reason": "Input is too short to be a valid complaint. Please provide more details.\n(یہ شکایت بہت مختصر ہے۔ براہ کرم مزید تفصیلات فراہم کریں۔)"
        }

    client = Client(api_key=_API_KEY)
    
    prompt = f"""
    Analyze the following input from a resident of Karachi:
    "{complaint_text}"
    
    Determine if this is a valid civic infrastructure complaint (water, electricity, roads, garbage, sewage, etc.).
    REJECT if:
    1. It's a medical, fire, or police emergency (tell them to call 1122 for medical/fire or 15 for police).
    2. It contains hate speech, profanity, or political inflammation.
    3. It's complete gibberish or entirely unrelated to civic issues.
    
    Output ONLY a JSON response:
    {{
      "safe": true/false,
      "rejection_reason_english": "If false, provide reason and helpline if applicable, else null",
      "rejection_reason_urdu": "If false, provide reason in Urdu, else null"
    }}
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    
    raw = response.text.strip()
    if raw.startswith("```json"):
        raw = raw[7:-3]
    elif raw.startswith("```"):
        raw = raw[3:-3]
        
    try:
        data = json.loads(raw.strip())
        if not data.get("safe", True):
            reason = f"{data.get('rejection_reason_english')}\n\n{data.get('rejection_reason_urdu')}"
            return {"safe": False, "reason": reason}
        return {"safe": True}
    except Exception:
        # If parsing fails, default to safe to not block the user incorrectly
        return {"safe": True}


# ─────────────────────────────────────────────
# 2. Sequential Agent Setup
# ─────────────────────────────────────────────

def make_orchestrator() -> SequentialAgent:
    """Creates the main supervisor pipeline."""
    return SequentialAgent(
        name="ShikayatAI_Orchestrator",
        description="Routes Karachi civic complaints to correct authority and generates formal complaint letters in Urdu and English",
        agents=[
            make_memory_agent(),
            make_classifier_agent(),
            make_researcher_agent(),
            make_drafter_agent()
        ]
    )

# ─────────────────────────────────────────────
# 3. Main Runner & Test Harness
# ─────────────────────────────────────────────

async def process_complaint(user_text: str):
    """End to end process with state management."""
    print("=" * 60)
    print(f"INPUT: {user_text}")
    print("=" * 60)
    
    print("[1] Running Safety Pre-Check...")
    safety = run_safety_precheck(user_text)
    if not safety.get("safe"):
        print("\n[REJECTED]\n" + safety.get("reason", ""))
        return
    print("    -> Passed!")

    orchestrator = make_orchestrator()
    session_service = InMemorySessionService()
    user_id = "test-user"
    session_id = str(uuid.uuid4())

    await session_service.create_session(
        app_name="ShikayatAI",
        user_id=user_id,
        session_id=session_id,
    )
    
    # Store initial state for the agents to pull from using tool_context
    session = await session_service.get_session("ShikayatAI", user_id, session_id)
    if session:
        session.state["user_complaint"] = user_text
        session.state["user_id"] = user_id
    
    runner = Runner(
        agent=orchestrator,
        session_service=session_service,
        app_name="ShikayatAI"
    )

    print("\n[2] Routing to ShikayatAI Agent Pipeline...")
    
    message = types.Content(
        role="user",
        parts=[types.Part(text=user_text)],
    )

    try:
        final_output = ""
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=message
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if getattr(part, "text", None):
                            final_output += part.text
                            
            # You could also listen to intermediate node events if you want to print each agent's output
            # For ADK 2.3.0, you can check event.node_name or similar if exposed.
            
        print("\n[PIPELINE COMPLETE]")
        print("Final Agent Output:\n")
        print(final_output)

        # Let's also print the memory agent's decision from state
        session = await session_service.get_session("ShikayatAI", user_id, session_id)
        if session and "memory_output" in session.state:
            print("\n[MEMORY AGENT DECISION]:")
            print(session.state["memory_output"])
            
    except Exception as e:
        print(f"\n[PIPELINE FAILED]: {e}")


async def main():
    test_query = "Hamare mohalle mein teen din se pani nahi aa raha PECHS Block 2 mein, KWSB ka koi jawab nahi"
    await process_complaint(test_query)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        
    class _SuppressOtelNoise:
        def __init__(self, real_stderr):
            self._real = real_stderr
        def write(self, msg):
            if "was created in a different Context" not in msg and \
               "Failed to detach context" not in msg and \
               "Root node" not in msg and \
               "GeneratorExit" not in msg:
                self._real.write(msg)
        def flush(self):
            self._real.flush()

    sys.stderr = _SuppressOtelNoise(sys.stderr)
    try:
        asyncio.run(main())
    finally:
        sys.stderr = sys.stderr._real
