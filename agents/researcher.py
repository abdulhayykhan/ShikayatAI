"""
agents/researcher.py
────────────────────
ShikayatAI – Researcher Agent

Receives classifier output (JSON) and uses Google Search to find
live complaint portal information for the responsible authority.

Uses:
  • google.adk.agents.LlmAgent
  • google.adk.tools (Google Search)
  • Output schema (Pydantic)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime
from typing import Literal, Optional, Any

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types
from pydantic import BaseModel, Field

# Try to import Google Search tool. If ADK has a specific wrapper, we use it,
# otherwise we use the genai_types.Tool for Google Search.
try:
    from google.adk.tools import GoogleSearchTool
    _HAS_ADK_SEARCH = True
except ImportError:
    _HAS_ADK_SEARCH = False

# ─────────────────────────────────────────────
# 0. Environment & API-key rotation pool
# ─────────────────────────────────────────────
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

_API_KEYS: list[str] = []
for _var in [
    "GOOGLE_API_KEY",
    "GOOGLE_API_KEY_BACKUP",
    *[f"GOOGLE_API_KEY_{i}" for i in range(2, 10)],
]:
    _val = os.getenv(_var)
    if _val and _val not in _API_KEYS:
        _API_KEYS.append(_val)

# ─────────────────────────────────────────────
# 1. Output Schema
# ─────────────────────────────────────────────

class ResearchResult(BaseModel):
    authority_full_name: str
    complaint_portal_url: Optional[str] = None
    helpline_numbers: list[str] = Field(default_factory=list)
    whatsapp_number: Optional[str] = None
    email: Optional[str] = None
    physical_address: str
    office_hours: Optional[str] = None
    online_tracking_available: bool
    search_timestamp: str = Field(
        description="ISO datetime string of when the search was performed"
    )
    data_confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence based on source: high (.gov.pk/official), medium (news/recent), low (old/unverified)"
    )

# ─────────────────────────────────────────────
# 2. System Prompt
# ─────────────────────────────────────────────

SYSTEM_INSTRUCTION = """\
You are the ResearcherAgent for ShikayatAI, a civic complaint routing system for Karachi, Pakistan.
You receive a JSON object representing a classified civic complaint (the "classifier_output").
Your job is to find the most up-to-date contact information, complaint portal URLs, and helplines
for the responsible authority mentioned in the classifier output.

SEARCH STRATEGY:
Use the Google Search tool to find information. You MUST follow these exact search queries:
1. "[authority_name] official complaint portal Pakistan"
2. "[authority_name] helpline number Karachi 2025"
3. "[authority_name] online complaint registration"

DATA CONFIDENCE RULES:
Set `data_confidence` to:
- "high": Found official .gov.pk or official domain URLs.
- "medium": Found from news/third party but recent (2024-2026).
- "low": Found old data or couldn't verify.

If search returns nothing useful, return nulls/empty lists but DO NOT hallucinate phone numbers. Mark data_confidence as "low".

KNOWN RELIABLE FALLBACKS (Use these ONLY if search fails or to supplement missing data):
- K-Electric: Helpline 118, website: kesc.com.pk (now ke.com.pk)
- KWSB (Karachi Water & Sewerage Board): Helpline 1309, no reliable online portal
- SSGC (Sui Southern Gas Company): Helpline 1199
- KMC (Karachi Metropolitan Corporation): Phone 021-99251600

Always output ONLY valid JSON matching this exact schema (do NOT wrap in markdown codeblocks, just raw JSON):
{
  "authority_full_name": "string",
  "complaint_portal_url": "string or null",
  "helpline_numbers": ["string"],
  "whatsapp_number": "string or null",
  "email": "string or null",
  "physical_address": "string",
  "office_hours": "string or null",
  "online_tracking_available": true/false,
  "search_timestamp": "ISO datetime string",
  "data_confidence": "high|medium|low"
}
"""

# ─────────────────────────────────────────────
# 3. Agent Definition & Factory
# ─────────────────────────────────────────────

_MODEL = "gemini-2.5-flash"  # Using 2.5-flash to bypass quota issues, though 2.0-flash is also acceptable

_AGENT_DESCRIPTION = (
    "Researches civic authorities in Karachi to find contact info, helplines, "
    "and online complaint portals."
)

from google.adk.tools import google_search

def _make_agent() -> LlmAgent:
    """Return a fresh LlmAgent instance."""
    return LlmAgent(
        name="ResearcherAgent",
        model=_MODEL,
        description=_AGENT_DESCRIPTION,
        instruction=SYSTEM_INSTRUCTION,
        tools=[google_search],
    )

# ─────────────────────────────────────────────
# 4. Helper: run one research task
# ─────────────────────────────────────────────

APP_NAME = "ShikayatAI"

def _is_quota_error(exc: BaseException) -> bool:
    msg = str(exc)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg or "empty response" in msg

async def _run_with_key(
    classifier_output: dict[str, Any],
    api_key: str,
    key_label: str,
) -> ResearchResult:
    """Run one research attempt using *api_key*."""
    os.environ["GOOGLE_API_KEY"] = api_key
    agent = _make_agent()

    session_service = InMemorySessionService()
    user_id = "test-user"
    session_id = str(uuid.uuid4())

    await session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
    )
    
    # Store the classifier output in the session state so the agent has it
    session = await session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
    if session:
        session.state["classifier_output"] = classifier_output

    runner = Runner(
        agent=agent,
        session_service=session_service,
        app_name=APP_NAME,
    )

    # We tell the agent to look at the classifier_output
    user_prompt = f"Here is the classifier_output:\n{json.dumps(classifier_output, indent=2)}\n\nPlease research the responsible authority and return the JSON."

    message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=user_prompt)],
    )

    final_text: str = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=message,
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if getattr(part, "text", None):
                        final_text = part.text
                        break
            break

    if not final_text:
        raise ValueError("ResearcherAgent returned an empty response.")

    final_text = final_text.strip()
    if final_text.startswith("```json"):
        final_text = final_text[7:]
    elif final_text.startswith("```"):
        final_text = final_text[3:]
    if final_text.endswith("```"):
        final_text = final_text[:-3]
    final_text = final_text.strip()

    raw = json.loads(final_text)
    return ResearchResult(**raw)

async def research_complaint(classifier_output: dict[str, Any]) -> ResearchResult:
    """
    Send the classifier JSON to ResearcherAgent and return a ResearchResult.
    Automatically rotates through available API keys on 429 quota errors.
    """
    if not _API_KEYS:
        raise EnvironmentError("No API keys configured. Set GOOGLE_API_KEY in your .env file.")

    last_exc: BaseException | None = None
    for idx, key in enumerate(_API_KEYS):
        label = "primary" if idx == 0 else f"backup-{idx}"
        try:
            return await _run_with_key(classifier_output, key, label)
        except Exception as exc:  # noqa: BLE001
            if _is_quota_error(exc):
                print(
                    f"  [key-rotation] {label} key quota exhausted — "
                    f"switching to next key ({idx + 1}/{len(_API_KEYS)})",
                    file=sys.stderr,
                )
                last_exc = exc
                continue
            raise

    raise last_exc or RuntimeError("All API keys exhausted.")

# ─────────────────────────────────────────────
# 5. Test harness
# ─────────────────────────────────────────────

TEST_CASES = [
    {
        "label": "[K-Electric Search]",
        "classifier_output": {
            "complaint_type": "electricity",
            "responsible_body": "K-Electric",
            "responsible_body_short": "KE",
            "urgency": "high",
            "summary_english": "No electricity for 12 hours.",
            "summary_urdu": "12 گھنٹے سے بجلی نہیں ہے۔",
            "location_mentioned": True,
            "needs_clarification": False,
            "clarification_question": None
        }
    },
    {
        "label": "[KWSB Search]",
        "classifier_output": {
            "complaint_type": "water",
            "responsible_body": "Karachi Water & Sewerage Board",
            "responsible_body_short": "KWSB",
            "urgency": "medium",
            "summary_english": "Water pipe leaking on main road.",
            "summary_urdu": "مین روڈ پر پانی کی پائپ لائن لیک ہو رہی ہے۔",
            "location_mentioned": True,
            "needs_clarification": False,
            "clarification_question": None
        }
    }
]

def _print_result(label: str, result: ResearchResult) -> None:
    sep = "-" * 60
    print(f"\n{sep}")
    print(f"  {label}")
    print(f"{sep}")
    print(f"  Authority    : {result.authority_full_name}")
    print(f"  Portal URL   : {result.complaint_portal_url}")
    print(f"  Helplines    : {', '.join(result.helpline_numbers)}")
    print(f"  WhatsApp     : {result.whatsapp_number}")
    print(f"  Email        : {result.email}")
    print(f"  Address      : {result.physical_address}")
    print(f"  Office Hours : {result.office_hours}")
    print(f"  Trackable?   : {result.online_tracking_available}")
    print(f"  Timestamp    : {result.search_timestamp}")
    print(f"  Confidence   : {result.data_confidence}")
    print(sep)

async def run_tests() -> None:
    print("\n" + "=" * 60)
    print("  ShikayatAI - ResearcherAgent Test Suite")
    print(f"  Model: {_MODEL}  |  ADK 2.3.0")
    print("=" * 60)

    for case in TEST_CASES:
        try:
            result = await research_complaint(case["classifier_output"])
            _print_result(case["label"], result)
        except Exception as exc:  # noqa: BLE001
            print(f"\n[ERROR] {case['label']}: {exc}")

    print("\nAll tests complete.\n")

# ─────────────────────────────────────────────
# 6. Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import contextlib

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
        asyncio.run(run_tests())
    finally:
        sys.stderr = sys.stderr._real
