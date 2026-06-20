"""
api/main.py
───────────
FastAPI Backend for ShikayatAI
Exposes the ADK Orchestrator pipeline to the Next.js frontend.
"""

import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Import our custom ADK tools and agents
from agents.orchestrator import make_orchestrator, run_safety_precheck
from agents.memory_agent import memory_service

# ─────────────────────────────────────────────
# Set up logging (avoiding raw input texts)
# ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger("ShikayatAI")

# ─────────────────────────────────────────────
# Pydantic Models for Input Validation
# ─────────────────────────────────────────────
class ComplaintRequest(BaseModel):
    complaint: str = Field(..., min_length=5, max_length=500, description="Raw complaint text from user")
    user_id: str = Field(..., description="Unique ID for local storage session tracking")
    location: str | None = Field(None, description="Optional location field")

class FeedbackRequest(BaseModel):
    reference_number: str
    resolved: bool
    user_id: str

# ─────────────────────────────────────────────
# FastAPI App Initialization
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: preload models if needed
    logger.info("ShikayatAI Backend Server Starting...")
    yield
    # Shutdown
    logger.info("ShikayatAI Backend Server Shutting down...")

app = FastAPI(title="ShikayatAI API", lifespan=lifespan)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# Custom Middlewares
# ─────────────────────────────────────────────
@app.middleware("http")
async def process_time_and_logging_middleware(request: Request, call_next):
    start_time = time.time()
    
    # Process the request
    response = await call_next(request)
    
    process_time = time.time() - start_time
    response.headers["X-Response-Time"] = str(process_time)
    
    # We purposefully do not log the body here for privacy.
    # Instead, we just log the endpoint and latency.
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.2f}s")
    
    return response

# Global Exception Handler to ensure generic bilingual 500s
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Internal Server Error: {str(exc)}")
    # Hide internal details
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error_english": "An internal server error occurred. Please try again later.",
            "error_urdu": "سرور میں کوئی اندرونی خامی پیش آ گئی ہے۔ براہ کرم کچھ دیر بعد دوبارہ کوشش کریں۔"
        }
    )

# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────

@app.get("/api/health")
async def health_check():
    """System health check and model info."""
    return {
        "status": "ok",
        "model": "gemini-2.5-flash",
        "agents": ["Classifier", "Researcher", "Drafter", "Memory"]
    }

@app.post("/api/complaint")
async def submit_complaint(req: ComplaintRequest):
    """
    Main inference endpoint.
    1. Runs safety pre-check.
    2. Runs ADK Orchestrator.
    3. Returns Drafter's JSON.
    """
    input_text = req.complaint
    if req.location:
        input_text += f"\n[Location Context: {req.location}]"

    # 1. Safety Pre-check
    safety = run_safety_precheck(input_text)
    if not safety.get("safe"):
        reason = safety.get("reason", "Invalid complaint.")
        logger.warning(f"Complaint rejected by safety check for user {req.user_id}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error_english": "Your complaint was rejected by the safety filters.",
                "error_urdu": "آپ کی شکایت حفاظتی فلٹرز کی وجہ سے مسترد کر دی گئی ہے۔",
                "details": reason
            }
        )

    # 2. ADK Runner Setup
    orchestrator = make_orchestrator()
    session_service = InMemorySessionService()
    session_id = str(uuid.uuid4())

    await session_service.create_session(
        app_name="ShikayatAI",
        user_id=req.user_id,
        session_id=session_id,
    )
    
    session = await session_service.get_session("ShikayatAI", req.user_id, session_id)
    if session:
        session.state["user_complaint"] = input_text
        session.state["user_id"] = req.user_id

    runner = Runner(
        agent=orchestrator,
        session_service=session_service,
        app_name="ShikayatAI"
    )

    message = types.Content(
        role="user",
        parts=[types.Part(text=input_text)],
    )

    final_output = ""
    try:
        async for event in runner.run_async(
            user_id=req.user_id,
            session_id=session_id,
            new_message=message
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if getattr(part, "text", None):
                            final_output += part.text
                            
        # Look for MemoryAgent intercept
        refreshed_session = await session_service.get_session("ShikayatAI", req.user_id, session_id)
        if refreshed_session and "memory_output" in refreshed_session.state:
            mem_out = refreshed_session.state["memory_output"]
            if mem_out.get("action") == "warn":
                # Duplicate detected!
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "error_english": "Duplicate complaint detected.",
                        "error_urdu": "پہلے سے درج شدہ شکایت موصول ہوئی۔",
                        "details": mem_out.get("message")
                    }
                )
    
    except Exception as e:
        logger.error(f"ADK Execution Error: {e}")
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error_english": "AI Quota limit exceeded. Please try again tomorrow.",
                    "error_urdu": "آرٹیفیشل انٹیلیجنس کی روزانہ کی حد پوری ہو گئی ہے۔ براہ کرم کل کوشش کریں۔"
                }
            )
        raise e

    # Parse final JSON output from Drafter
    try:
        raw_json = final_output.strip()
        if raw_json.startswith("```json"):
            raw_json = raw_json[7:]
        if raw_json.startswith("```"):
            raw_json = raw_json[3:]
        if raw_json.endswith("```"):
            raw_json = raw_json[:-3]
        
        parsed = json.loads(raw_json.strip())
        logger.info(f"[LOG] Complaint successfully routed and drafted for user {req.user_id}")
        return parsed
    except json.JSONDecodeError:
        logger.error("Failed to parse Drafter JSON output.")
        raise HTTPException(status_code=500, detail="Failed to parse model output.")


@app.get("/api/complaint/{reference_number}")
async def get_complaint_status(reference_number: str, user_id: str):
    """Retrieves complaint status from memory agent service."""
    complaints = memory_service.get_complaints(user_id)
    for c in complaints:
        if c.get("reference_number") == reference_number:
            return c
            
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error_english": "Complaint not found.",
            "error_urdu": "شکایت نہیں ملی۔"
        }
    )

@app.post("/api/feedback")
async def update_complaint_feedback(req: FeedbackRequest):
    """Updates the status of a complaint based on user feedback."""
    if req.resolved:
        success = memory_service.update_status(req.user_id, req.reference_number, "resolved")
        if success:
            return {"status": "success", "message": "Complaint marked as resolved."}
            
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error_english": "Failed to update complaint status. Not found.",
            "error_urdu": "اسٹیٹس اپ ڈیٹ کرنے میں ناکامی۔ شکایت نہیں ملی۔"
        }
    )
