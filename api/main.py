"""
api/main.py
───────────
FastAPI Backend for ShikayatAI
Exposes the ADK Orchestrator pipeline to the Next.js frontend.
"""

import asyncio
import json
import logging
import sqlite3
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



# ─────────────────────────────────────────────
# FastAPI App Initialization
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: preload models if needed
    logger.info("ShikayatAI Backend Server Starting...")
    
    # Initialize SQLite database
    try:
        with sqlite3.connect("complaints.db") as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS complaints
                            (ref_num TEXT PRIMARY KEY, data TEXT)''')
    except Exception as e:
        logger.error(f"Failed to initialize SQLite DB: {e}")

    yield
    # Shutdown
    logger.info("ShikayatAI Backend Server Shutting down...")

app = FastAPI(title="ShikayatAI API", lifespan=lifespan)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://shikayatai-web-941068767562.asia-south1.run.app"],
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
        "model": "groq/llama-3.3-70b-versatile",
        "agents": ["Classifier", "Researcher", "Drafter"]
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
    
    session = await session_service.get_session(app_name="ShikayatAI", user_id=req.user_id, session_id=session_id)
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
                node_name = event.node_name or ""
                author = event.author or ""
                event_text = ""
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if getattr(part, "text", None):
                            event_text += part.text
                logger.info(f"Final response event: node_name='{node_name}', author='{author}', text_preview='{event_text[:60]}'")
                
                # Only accumulate text from the Drafter agent
                if node_name == "Drafter" or author == "Drafter" or "Drafter" in node_name or "Drafter" in author:
                    final_output += event_text
                            

    
    except Exception as e:
        logger.error(f"ADK Execution Error: {e}")
        error_str = str(e).lower()
        if "429" in error_str or "resource_exhausted" in error_str or "rate limit" in error_str:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error_english": "AI Quota limit exceeded. Please try again later.",
                    "error_urdu": "آرٹیفیشل انٹیلیجنس کی روزانہ کی حد پوری ہو گئی ہے۔ براہ کرم کچھ دیر بعد دوبارہ کوشش کریں۔"
                }
            )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error_english": f"Pipeline Error: {str(e)}",
                "error_urdu": "سرور میں کوئی اندرونی خامی پیش آ گئی ہے۔"
            }
        )

    # Parse final JSON output from Drafter
    try:
        text = final_output.strip()
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace == -1 or last_brace == -1 or last_brace < first_brace:
            logger.error(f"No JSON object found in Drafter output. Raw output: {repr(final_output)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error_english": "The AI failed to format the response correctly. Please try again.",
                    "error_urdu": "اے آئی نے جواب درست فارمیٹ میں نہیں دیا۔ براہ کرم دوبارہ کوشش کریں۔"
                }
            )
        
        json_str = text[first_brace:last_brace + 1]
        parsed = json.loads(json_str, strict=False)
        
        # Inject Date and Reference Number
        import random
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Asia/Karachi"))
        ref_num = f"KF-{now.year}{now.month:02d}{now.day:02d}-{random.randint(100, 999)}"
        date_en = now.strftime("%B %d, %Y")
        urdu_months = ["جنوری", "فروری", "مارچ", "اپریل", "مئی", "جون", "جولائی", "اگست", "ستمبر", "اکتوبر", "نومبر", "دسمبر"]
        date_ur = f"{now.day} {urdu_months[now.month - 1]} {now.year}"

        parsed["reference_number"] = ref_num
        if "english_letter" in parsed:
            parsed["english_letter"] = parsed["english_letter"].replace("[REF_NUM]", ref_num).replace("[DATE_EN]", date_en)
        if "urdu_letter" in parsed:
            parsed["urdu_letter"] = parsed["urdu_letter"].replace("[REF_NUM]", ref_num).replace("[DATE_UR]", date_ur)

        # Save to database
        try:
            with sqlite3.connect("complaints.db") as conn:
                conn.execute("INSERT OR REPLACE INTO complaints (ref_num, data) VALUES (?, ?)", 
                             (ref_num, json.dumps(parsed)))
        except Exception as db_err:
            logger.error(f"Failed to save complaint to DB: {db_err}")

        logger.info(f"[LOG] Complaint successfully routed and drafted for user {req.user_id}")
        return parsed
    except Exception as e:
        logger.error(f"Failed to parse Drafter JSON output. Raw output: {repr(final_output)}. Error: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error_english": "The AI produced an invalid response format. Please try again.",
                "error_urdu": "اے آئی کے جواب میں کچھ خرابی تھی۔ براہ کرم دوبارہ کوشش کریں۔"
            }
        )

@app.get("/api/complaint/{reference_number}")
async def get_complaint(reference_number: str):
    """Fetch an existing complaint by tracking number."""
    try:
        with sqlite3.connect("complaints.db") as conn:
            cursor = conn.execute("SELECT data FROM complaints WHERE ref_num = ?", (reference_number,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            else:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={
                        "error_english": "Complaint not found. Please check your tracking number.",
                        "error_urdu": "شکایت نہیں ملی۔ براہ کرم اپنا ٹریکنگ نمبر چیک کریں۔"
                    }
                )
    except Exception as e:
        logger.error(f"Database error on fetch: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error_english": "Failed to retrieve complaint due to an internal error.",
                "error_urdu": "اندرونی خرابی کی وجہ سے شکایت حاصل کرنے میں ناکامی۔"
            }
        )


