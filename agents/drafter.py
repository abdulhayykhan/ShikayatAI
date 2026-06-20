"""
agents/drafter.py
─────────────────
ShikayatAI – Drafter Agent

Reads classifier + researcher output from session state and uses
code execution to generate formatted complaint letters.

Uses:
  • google.adk.agents.LlmAgent
  • google.adk.tools (Code Execution)
  • Output schema (Prompt-enforced to avoid tool conflicts)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from typing import Any, Literal

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types
from pydantic import BaseModel, Field

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
class DrafterResult(BaseModel):
    reference_number: str
    english_letter: str
    urdu_letter: str
    submission_method: Literal["online", "physical", "both", "phone"]
    submission_url: str | None = None
    helpline_to_call: str | None = None
    next_steps_english: list[str]
    next_steps_urdu: list[str]

# ─────────────────────────────────────────────
# 2. System Prompt
# ─────────────────────────────────────────────
SYSTEM_INSTRUCTION = """\
You are the DrafterAgent for ShikayatAI, a civic complaint routing system for Karachi, Pakistan.
You will be provided with a JSON string containing the combined outputs of the ClassifierAgent and ResearcherAgent.

Your job is to draft formal complaint letters in both English and Urdu, and to determine the best next steps for the user based on the available contact information.

REQUIRED ACTIONS:
You MUST use the code execution tool (Python) to:
1. Generate a reference number format: REF-[YEAR]-[8 random digits]
2. Get today's date formatted as "Month DD, YYYY" (e.g. "June 20, 2026")
3. Get today's date formatted in Urdu (e.g. "20 جون 2026")

You must use these dynamically generated values in your letters.

ENGLISH LETTER FORMAT (Formal):
---
Reference No: [Generated Reference Number]
Date: [Generated English Date]

The [Authority Full Name],
[Physical Address]

Subject: Complaint Regarding [complaint_type] Issue

Respected Sir/Madam,

I, the undersigned resident of [location if provided, else "Karachi"], 
wish to register a formal complaint regarding [summary_english].

[2-3 sentences expanding the issue based on the summary]

I kindly request your immediate attention to this matter and urge prompt resolution.

Yours faithfully,
_____________________
Name: _______________
CNIC: _______________
Contact: ____________
Address: ____________
---

URDU LETTER FORMAT (درخواست style):
---
حوالہ نمبر: [Generated Reference Number]
تاریخ: [Generated Urdu Date]

جناب [Authority Full Name in Urdu],
[Physical Address]

موضوع: [Translate complaint_type to Urdu] سے متعلق شکایت

جناب والا،

میں [location if provided, else "کراچی"] کا/کی رہائشی ہوں اور [summary_urdu] کی شکایت درج کرانا چاہتا/چاہتی ہوں۔

[2-3 Urdu sentences expanding the issue based on the summary]

گزارش ہے کہ اس معاملے پر فوری توجہ دی جائے اور اسے جلد از جلد حل کیا جائے۔

خاکسار،
_____________________
نام: _______________
شناختی کارڈ: _______________
رابطہ: ____________
پتہ: ____________
---

Always output ONLY valid JSON matching this exact schema (do NOT wrap in markdown codeblocks, just raw JSON). Use these exact keys:
"reference_number": "string"
"english_letter": "string (full text)"
"urdu_letter": "string (full text)"
"submission_method": "online|physical|both|phone"
"submission_url": "string or null"
"helpline_to_call": "string or null"
"next_steps_english": ["string"]
"next_steps_urdu": ["string"]
"""

# ─────────────────────────────────────────────
# 3. Agent Definition & Factory
# ─────────────────────────────────────────────

_MODEL = "gemini-2.5-flash" 

_AGENT_DESCRIPTION = (
    "Drafts formal civic complaint letters in English and Urdu, generating "
    "dynamic dates and reference numbers via code execution."
)

def built_in_code_execution(python_code: str) -> str:
    """
    Executes the provided Python code and returns the printed stdout.
    Use this to generate reference numbers, calculate dates, etc.
    Make sure to use print() to output the final result.
    """
    import io
    import sys
    
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        # Provide a basic safe globals dict
        exec(python_code, {"__builtins__": __builtins__})
        output = sys.stdout.getvalue()
    except Exception as e:
        output = f"Execution Error: {str(e)}"
    finally:
        sys.stdout = old_stdout
    
    return output.strip()

def _make_agent() -> LlmAgent:
    """Return a fresh LlmAgent instance."""
    return LlmAgent(
        name="DrafterAgent",
        model=_MODEL,
        description=_AGENT_DESCRIPTION,
        instruction=SYSTEM_INSTRUCTION,
        tools=[built_in_code_execution],
    )

# ─────────────────────────────────────────────
# 4. Helper: run one drafting task
# ─────────────────────────────────────────────

APP_NAME = "ShikayatAI"

def _is_quota_error(exc: BaseException) -> bool:
    msg = str(exc)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg or "empty response" in msg

async def _run_with_key(
    combined_input: dict[str, Any],
    api_key: str,
    key_label: str,
) -> DrafterResult:
    """Run one drafting attempt using *api_key*."""
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
    
    # Expose state if necessary
    session = await session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
    if session:
        session.state["input_data"] = combined_input

    runner = Runner(
        agent=agent,
        session_service=session_service,
        app_name=APP_NAME,
    )

    user_prompt = f"Here is the combined classifier and researcher output:\n{json.dumps(combined_input, indent=2)}\n\nPlease generate the letters and return the JSON."

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
                        final_text += part.text

    if not final_text:
        raise ValueError("DrafterAgent returned an empty response.")

    final_text = final_text.strip()
    if final_text.startswith("```json"):
        final_text = final_text[7:]
    elif final_text.startswith("```"):
        final_text = final_text[3:]
    if final_text.endswith("```"):
        final_text = final_text[:-3]
    final_text = final_text.strip()

    raw = json.loads(final_text)
    return DrafterResult(**raw)

async def draft_complaint(combined_input: dict[str, Any]) -> DrafterResult:
    """
    Send the combined JSON to DrafterAgent and return a DrafterResult.
    Automatically rotates through available API keys on 429 quota errors.
    """
    if not _API_KEYS:
        raise EnvironmentError("No API keys configured. Set GOOGLE_API_KEY in your .env file.")

    last_exc: BaseException | None = None
    for idx, key in enumerate(_API_KEYS):
        label = "primary" if idx == 0 else f"backup-{idx}"
        try:
            return await _run_with_key(combined_input, key, label)
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
        "label": "[KWSB Drafter Test]",
        "input_data": {
            "classifier_output": {
                "complaint_type": "water",
                "responsible_body": "Karachi Water & Sewerage Board",
                "responsible_body_short": "KWSB",
                "urgency": "high",
                "summary_english": "No water supply for 3 days in Gulshan-e-Iqbal Block 7.",
                "summary_urdu": "گلشن اقبال بلاک 7 میں تین دن سے پانی کی فراہمی نہیں ہے۔",
                "location_mentioned": True,
                "needs_clarification": False,
                "clarification_question": None
            },
            "researcher_output": {
                "authority_full_name": "Karachi Water & Sewerage Corporation",
                "complaint_portal_url": "https://kwsc.gos.pk/e-complaint",
                "helpline_numbers": ["1339", "021-34313638"],
                "whatsapp_number": "0329-3223344",
                "email": "info@kwsc.gos.pk",
                "physical_address": "9th Mile Karsaz, Main Shahrah-e-Faisal, Karachi",
                "office_hours": "24/7",
                "online_tracking_available": True,
                "search_timestamp": "2026-06-20T09:00:00Z",
                "data_confidence": "high"
            }
        }
    }
]

def _print_result(label: str, result: DrafterResult) -> None:
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  {label}")
    print(f"{sep}\n")
    print(f"  Reference No : {result.reference_number}")
    print(f"  Method       : {result.submission_method}")
    print(f"  URL          : {result.submission_url}")
    print(f"  Helpline     : {result.helpline_to_call}")
    
    print("\n  [Next Steps - EN]")
    for step in result.next_steps_english:
        print(f"  - {step}")
        
    print("\n  [Next Steps - UR]")
    for step in result.next_steps_urdu:
        print(f"  - {step}")

    print("\n" + "-" * 60)
    print("  [English Letter Preview (First 300 chars)]")
    print("-" * 60)
    print(result.english_letter[:300] + "...\n")

    print("-" * 60)
    print("  [Urdu Letter Preview (First 300 chars)]")
    print("-" * 60)
    print(result.urdu_letter[:300] + "...\n")
    print(sep)

async def run_tests() -> None:
    print("\n" + "=" * 60)
    print("  ShikayatAI - DrafterAgent Test Suite")
    print(f"  Model: {_MODEL}  |  ADK 2.3.0")
    print("=" * 60)

    for case in TEST_CASES:
        try:
            result = await draft_complaint(case["input_data"])
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
