"""
agents/memory_agent.py
──────────────────────
ShikayatAI – Memory Agent

Stores and retrieves user complaints. Warns if duplicates exist,
summarizes past complaints, and updates resolved status.

Uses:
  • google.adk.agents.LlmAgent
"""

import json
from typing import Literal

from google.adk.agents import LlmAgent
from google.adk.tools import tool_context

# Simulated In-Memory Service since ADK's InMemoryMemoryService is missing/unexported
class InMemoryMemoryService:
    def __init__(self):
        self._db: dict[str, list[dict]] = {}

    def get_complaints(self, user_id: str) -> list[dict]:
        return self._db.get(user_id, [])

    def add_complaint(self, user_id: str, record: dict) -> None:
        if user_id not in self._db:
            self._db[user_id] = []
        self._db[user_id].append(record)

    def update_status(self, user_id: str, ref_number: str, status: str) -> bool:
        for c in self.get_complaints(user_id):
            if c.get("reference_number") == ref_number:
                c["status"] = status
                return True
        return False

# Global instance for the current runtime
memory_service = InMemoryMemoryService()

# Seed some dummy data for the test user to demonstrate duplicate checks
memory_service.add_complaint("test-user", {
    "reference_number": "REF-2026-99991111",
    "complaint_type": "water",
    "authority": "KWSB",
    "date": "June 18, 2026",
    "status": "pending",
    "summary": "Pani nahi aa raha PECHS Block 2 mein"
})


def search_past_complaints() -> str:
    """Retrieve all past complaints for the current user."""
    # Assuming user_id is passed in state or we hardcode 'test-user' for this demo
    user_id = tool_context.state.get("user_id", "test-user")
    records = memory_service.get_complaints(user_id)
    if not records:
        return "No past complaints found."
    return json.dumps(records, indent=2)

def add_new_complaint(reference_number: str, complaint_type: str, authority: str, date: str) -> str:
    """Save a new complaint record to memory."""
    user_id = tool_context.state.get("user_id", "test-user")
    record = {
        "reference_number": reference_number,
        "complaint_type": complaint_type,
        "authority": authority,
        "date": date,
        "status": "pending"
    }
    memory_service.add_complaint(user_id, record)
    return "Complaint added to memory."

def mark_complaint_resolved(reference_number: str) -> str:
    """Mark an existing complaint as resolved."""
    user_id = tool_context.state.get("user_id", "test-user")
    success = memory_service.update_status(user_id, reference_number, "resolved")
    return "Status updated to resolved." if success else "Complaint not found."

def set_memory_agent_output(output_action: Literal["proceed", "warn", "summarize", "resolved"], message: str) -> str:
    """
    Saves the memory agent's final decision to the session state so the orchestrator knows what to do.
    """
    tool_context.state["memory_output"] = {
        "action": output_action,
        "message": message
    }
    return "Output saved."

SYSTEM_INSTRUCTION = """\
You are the MemoryAgent for ShikayatAI, handling complaints for Karachi residents.
When you receive a user's input, use your tools to interact with their memory profile.

ROLES:
1. NEW COMPLAINT: If the user describes a new problem, search past complaints. If a similar unresolved complaint exists, warn the user. Otherwise, approve it to proceed.
2. PAST COMPLAINTS QUERY ("meri purani shikayat"): Retrieve past complaints and summarize them nicely in English and Urdu.
3. STATUS UPDATE ("mera masla hal ho gaya"): Identify which complaint is resolved and update its status.

When you are done processing, you MUST call the `set_memory_agent_output` tool to record your final decision.
- If it's a new unique complaint, action="proceed", message="Clear to process"
- If it's a duplicate, action="warn", message="Warning in EN/UR about duplicate"
- If they asked for a summary, action="summarize", message="Summary in EN/UR"
- If they resolved an issue, action="resolved", message="Resolution confirmation in EN/UR"

Output a brief text acknowledging what you did.
"""

def make_memory_agent() -> LlmAgent:
    return LlmAgent(
        name="MemoryAgent",
        model="gemini-2.5-flash",
        description="Manages user complaint history and detects duplicates.",
        instruction=SYSTEM_INSTRUCTION,
        tools=[
            search_past_complaints,
            add_new_complaint,
            mark_complaint_resolved,
            set_memory_agent_output
        ]
    )
