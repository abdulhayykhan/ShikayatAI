"""
agents/classifier.py
────────────────────
ShikayatAI – Complaint Classifier Agent

Accepts a civic complaint in English, Urdu, or Romanised Urdu and returns
a structured JSON classification that downstream agents use for routing.

Uses:
  • google.adk.agents.LlmAgent      – core agent
  • output_schema (Pydantic)         – enforces JSON shape
  • InMemorySessionService + Runner  – for the test harness
"""

from __future__ import annotations

import asyncio
import sys
import json
import os
import uuid
from typing import Literal, Optional

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types
from pydantic import BaseModel, Field

# ─────────────────────────────────────────────
# 0.  Environment & API-key rotation pool
# ─────────────────────────────────────────────
# Reconfigure stdout to UTF-8 so Urdu script and box chars print on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()  # loads .env -> os.environ

# Collect every API key found in the environment (primary + any backups).
# Supported variable names:
#   GOOGLE_API_KEY          – primary (required)
#   GOOGLE_API_KEY_BACKUP   – first backup
#   GOOGLE_API_KEY_2, _3 …  – additional backups (optional)
_API_KEYS: list[str] = []
for _var in [
    "GOOGLE_API_KEY",
    "GOOGLE_API_KEY_BACKUP",
    *[f"GOOGLE_API_KEY_{i}" for i in range(2, 10)],
]:
    _val = os.getenv(_var)
    if _val and _val not in _API_KEYS:  # deduplicate
        _API_KEYS.append(_val)

# ─────────────────────────────────────────────
# 1.  Output Schema  (Pydantic → ADK enforces it)
# ─────────────────────────────────────────────

ComplaintType = Literal[
    "water",
    "electricity",
    "sewage",
    "road",
    "garbage",
    "illegal_construction",
    "noise",
    "gas",
    "internet",
    "other",
    "invalid",          # non-civic or irrelevant input
]

UrgencyLevel = Literal["low", "medium", "high", "emergency"]


class ClassificationResult(BaseModel):
    """Structured output returned by ClassifierAgent."""

    complaint_type: ComplaintType = Field(
        description="Category of the civic complaint."
    )
    responsible_body: str = Field(
        description="Full official name of the responsible government body."
    )
    responsible_body_short: str = Field(
        description="Abbreviation / short name of the responsible body."
    )
    urgency: UrgencyLevel = Field(
        description="Urgency level of the complaint."
    )
    summary_english: str = Field(
        description="One-sentence summary of the complaint in English."
    )
    summary_urdu: str = Field(
        description="One-sentence summary of the complaint in Urdu script."
    )
    location_mentioned: bool = Field(
        description="True if the complaint mentions a specific location."
    )
    needs_clarification: bool = Field(
        description="True if the complaint is ambiguous and needs more info."
    )
    clarification_question: Optional[str] = Field(
        default=None,
        description=(
            "If needs_clarification is true, a question in BOTH English and "
            "Urdu asking for the missing detail. Otherwise null."
        ),
    )


# ─────────────────────────────────────────────
# 2.  System Prompt
# ─────────────────────────────────────────────

SYSTEM_INSTRUCTION = """\
You are ClassifierAgent, the first stage of ShikayatAI — a civic complaint
routing system for Karachi, Pakistan.

Your job is to read a complaint written in English, Urdu, or Romanised Urdu
and classify it so it can be routed to the correct government authority.

══════════════════════════════════════════════
AUTHORITY MAPPING  (use these exact names)
══════════════════════════════════════════════
water              → KWSB   (Karachi Water & Sewerage Board)
sewage             → KWSB   (Karachi Water & Sewerage Board)
electricity        → K-Electric
gas                → SSGC   (Sui Southern Gas Company)
road               → KMC    (Karachi Metropolitan Corporation)
garbage            → KMC    (Karachi Metropolitan Corporation)
illegal_construction:
  • Buildings / structures  → SBCA  (Sindh Building Control Authority)
  • Land encroachment       → KDA   (Karachi Development Authority)
noise              → District Administration / local SHO
internet           → PTA    (Pakistan Telecommunication Authority)
other              → Deputy Commissioner Office, Karachi

══════════════════════════════════════════════
URGENCY RULES
══════════════════════════════════════════════
emergency  – immediate threat to life/safety (gas leak, live wire, sewage
             flooding into homes)
high       – major disruption (no water >24 h, prolonged power cut, large
             road collapse)
medium     – ongoing but not acute (intermittent supply, pothole, noise
             continuing for days)
low        – minor or one-off nuisance (single garbage miss, internet slow)

══════════════════════════════════════════════
LANGUAGE SUPPORT
══════════════════════════════════════════════
Accept input in English, Urdu script, or Romanised Urdu. Examples:
  "bijli nahi hai"        → electricity complaint
  "sadak toot gayi"       → road complaint
  "kachra nahi uthaya"    → garbage complaint
  "pani nahi aa raha"     → water complaint
  "gas band hai"          → gas complaint
  "naali bhar gayi"       → sewage complaint

Always write summary_urdu in proper Urdu script (not Roman Urdu).

══════════════════════════════════════════════
EDGE CASES
══════════════════════════════════════════════
1. AMBIGUOUS COMPLAINT
   If you cannot determine the category or location matters for routing,
   set needs_clarification=true and provide a clarification_question in
   BOTH English and Urdu separated by a newline.
   Example:
     "Can you tell me the area / street name where this problem is occurring?
      کیا آپ وہ علاقہ یا گلی کا نام بتا سکتے ہیں جہاں یہ مسئلہ ہے؟"

2. NON-CIVIC INPUT
   If the complaint is NOT a civic issue (e.g., medical emergency, personal
   dispute, political grievance, random text):
   • Set complaint_type = "invalid"
   • Set responsible_body = "Not Applicable"
   • Set responsible_body_short = "N/A"
   • Explain in summary_english why this is not a civic complaint
   • summary_urdu should be the Urdu translation of that explanation
   • Set urgency = "low"

3. MULTIPLE ISSUES  
   If the complaint covers more than one issue, pick the PRIMARY / most
   urgent one and mention the secondary issues in summary_english.

══════════════════════════════════════════════
OUTPUT
══════════════════════════════════════════════
Return ONLY the JSON object matching the schema. No extra text, no markdown
code fences. The schema is enforced — every field is required.
"""

# ─────────────────────────────────────────────
# 3.  Agent Definition
# ─────────────────────────────────────────────

_MODEL = "gemini-2.5-flash"

_AGENT_DESCRIPTION = (
    "Classifies Karachi civic complaints (English / Urdu / Romanised Urdu) "
    "and returns structured routing metadata."
)


def _make_agent() -> LlmAgent:
    """Return a fresh LlmAgent instance.

    A new instance is required each time we rotate API keys because
    google.genai caches the API client (and its key) at construction time.
    Creating a fresh LlmAgent after setting os.environ['GOOGLE_API_KEY']
    ensures the new key is picked up.
    """
    return LlmAgent(
        name="ClassifierAgent",
        model=_MODEL,
        description=_AGENT_DESCRIPTION,
        instruction=SYSTEM_INSTRUCTION,
        output_schema=ClassificationResult,
        tools=[],
    )


# Module-level reference used by the test harness; rotated on quota errors.
classifier_agent = _make_agent()

# ─────────────────────────────────────────────
# 4.  Helper: run one complaint through the agent
# ─────────────────────────────────────────────

APP_NAME = "ShikayatAI"


def _is_quota_error(exc: BaseException) -> bool:
    """Return True if *exc* is a 429 / RESOURCE_EXHAUSTED or empty response error."""
    msg = str(exc)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg or "empty response" in msg


async def _run_with_key(
    complaint_text: str,
    api_key: str,
    key_label: str,
) -> ClassificationResult:
    """Run one classification attempt using *api_key*."""
    # Point ADK / google.genai to this specific key.
    os.environ["GOOGLE_API_KEY"] = api_key

    # Fresh agent so its genai client picks up the new env var.
    agent = _make_agent()

    session_service = InMemorySessionService()
    user_id = "test-user"
    session_id = str(uuid.uuid4())

    await session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
    )

    runner = Runner(
        agent=agent,
        session_service=session_service,
        app_name=APP_NAME,
    )

    message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=complaint_text)],
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
        raise ValueError(
            f"ClassifierAgent returned an empty response for: {complaint_text!r}"
        )

    raw = json.loads(final_text)
    return ClassificationResult(**raw)


async def classify_complaint(complaint_text: str) -> ClassificationResult:
    """
    Send a complaint to ClassifierAgent and return a ClassificationResult.

    Automatically rotates through available API keys on 429 quota errors:
      GOOGLE_API_KEY  →  GOOGLE_API_KEY_BACKUP  →  GOOGLE_API_KEY_2 …
    """
    if not _API_KEYS:
        raise EnvironmentError(
            "No API keys configured. Set GOOGLE_API_KEY in your .env file."
        )

    last_exc: BaseException | None = None
    for idx, key in enumerate(_API_KEYS):
        label = "primary" if idx == 0 else f"backup-{idx}"
        try:
            return await _run_with_key(complaint_text, key, label)
        except Exception as exc:  # noqa: BLE001
            if _is_quota_error(exc):
                print(
                    f"  [key-rotation] {label} key quota exhausted — "
                    f"switching to next key ({idx + 1}/{len(_API_KEYS)})",
                    file=sys.stderr,
                )
                last_exc = exc
                continue
            raise  # non-quota errors bubble up immediately

    raise last_exc or RuntimeError("All API keys exhausted.")


# ─────────────────────────────────────────────
# 5.  Test harness  (5 diverse complaints)
# ─────────────────────────────────────────────

TEST_COMPLAINTS = [
    # (label, text)
    (
        "[English – Water]",
        "There has been no water supply in our area (Gulshan-e-Iqbal Block 7) "
        "for the past three days. Residents are suffering.",
    ),
    (
        "[Romanised Urdu – Electricity]",
        "Bijli nahi hai hamare mohalle mein kal raat se. Bahut garmi hai.",
    ),
    (
        "[Urdu script – Garbage]",
        "ہمارے گلی میں کئی دنوں سے کچرا نہیں اٹھایا گیا۔ بو بہت تکلیف دہ ہے۔",
    ),
    (
        "[Romanised Urdu – Road]",
        "Sadak bilkul toot gayi hai Clifton Block 5 ke paas. Gaadiyan phans "
        "rahi hain aur accident ka darr hai.",
    ),
    (
        "[English – Non-civic / Invalid]",
        "My neighbour and I have a property dispute. He is harassing me and "
        "I want the police to arrest him.",
    ),
]


def _print_result(label: str, complaint: str, result: ClassificationResult) -> None:
    """Pretty-print one classification result."""
    sep = "-" * 60
    print(f"\n{sep}")
    print(f"  {label}")
    print(f"{sep}")
    snippet = complaint[:80] + ("..." if len(complaint) > 80 else "")
    print(f"  Complaint  : {snippet}")
    print(f"  Type       : {result.complaint_type}")
    print(f"  Authority  : {result.responsible_body} ({result.responsible_body_short})")
    print(f"  Urgency    : {result.urgency}")
    print(f"  Summary EN : {result.summary_english}")
    print(f"  Summary UR : {result.summary_urdu}")
    print(f"  Location?  : {result.location_mentioned}")
    print(f"  Clarify?   : {result.needs_clarification}")
    if result.clarification_question:
        print(f"  Question   : {result.clarification_question}")
    print(sep)


async def run_tests() -> None:
    """Run all test complaints through ClassifierAgent and print results."""
    if not os.getenv("GOOGLE_API_KEY"):
        raise EnvironmentError(
            "GOOGLE_API_KEY is not set. Copy .env.example → .env and add your key."
        )

    print("\n" + "=" * 60)
    print("  ShikayatAI - ClassifierAgent Test Suite")
    print(f"  Model: {_MODEL}  |  ADK 2.3.0")
    print("=" * 60)

    for label, complaint in TEST_COMPLAINTS:
        try:
            result = await classify_complaint(complaint)
            _print_result(label, complaint, result)
        except Exception as exc:  # noqa: BLE001
            print(f"\n[ERROR] {label}: {exc}")

    print("\nAll tests complete.\n")


# ─────────────────────────────────────────────
# 6.  Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import io
    import contextlib

    # The ADK OpenTelemetry tracer emits a harmless ValueError
    # ("Token was created in a different Context") after each run_async
    # generator closes.  We silence it so the test output stays clean.
    class _SuppressOtelNoise:
        """Stderr filter: drop lines containing the known OTel context error."""
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

    import sys
    sys.stderr = _SuppressOtelNoise(sys.stderr)
    try:
        asyncio.run(run_tests())
    finally:
        sys.stderr = sys.stderr._real
