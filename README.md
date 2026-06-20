# 🏛️ ShikayatAI

```text
  ███████╗██╗  ██╗██╗██╗  ██╗ █████╗ ██╗   ██╗ █████╗ ████████╗ █████╗ ██╗
  ██╔════╝██║  ██║██║██║ ██╔╝██╔══██╗╚██╗ ██╔╝██╔══██╗╚══██╔══╝██╔══██╗██║
  ███████╗███████║██║█████╔╝ ███████║ ╚████╔╝ ███████║   ██║   ███████║██║
  ╚════██║██╔══██║██║██╔═██╗ ██╔══██║  ╚██╔╝  ██╔══██║   ██║   ██╔══██║██║
  ███████║██║  ██║██║██║  ██╗██║  ██║   ██║   ██║  ██║   ██║   ██║  ██║██║
  ╚══════╝╚═╝  ╚═╝╚═╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝
          AI-Powered Civic Complaint Resolution System for Karachi
```

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111%2B-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-14.2-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)
![Google Gemini](https://img.shields.io/badge/Google_Gemini-2.5_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/TailwindCSS-3.4-38B2AC?style=for-the-badge&logo=tailwindcss&logoColor=white)

---

## 🏙️ What is ShikayatAI?

ShikayatAI is a **bilingual (Urdu & English) civic complaint resolution platform** engineered specifically for the citizens of Karachi, Pakistan. It leverages a multi-agent AI pipeline built on Google's ADK and the Gemini 2.5 Flash model to instantly categorize, route, and draft formal civic complaints based on natural language input.

Instead of citizens navigating complex bureaucracy or figuring out which department handles their specific issue (e.g., KWSB for water, KE for electricity, SSMB for garbage), ShikayatAI acts as a single intelligent portal. A user simply types their problem in plain Urdu, Roman Urdu, or English. The AI pipeline runs a safety pre-check, dynamically researches live contact info for the correct authority via Google Search, and drafts formal, reference-tracked complaint letters in both languages, ready for submission.

---

## 🌐 Live Demo

| Service | URL |
|---------|-----|
| Frontend (Cloud Run) | [https://shikayatai-web-941068767562.asia-south1.run.app](https://shikayatai-web-941068767562.asia-south1.run.app) |
| Backend API (Cloud Run) | [https://shikayatai-api-941068767562.asia-south1.run.app](https://shikayatai-api-941068767562.asia-south1.run.app) |
| Backend Health Check | [https://shikayatai-api-941068767562.asia-south1.run.app/api/health](https://shikayatai-api-941068767562.asia-south1.run.app/api/health) |

---

## ✨ Feature List

### 🧠 Multi-Agent AI Pipeline
- Built using the **Google Agent Development Kit (ADK)** and `SequentialAgent` orchestration.
- Four distinct, specialized agents work in tandem: **Memory**, **Classifier**, **Researcher**, and **Drafter**.

### 🛡️ Safety & Content Moderation Pre-check
- Intercepts and rejects medical emergencies, active crimes, political rants, or gibberish.
- Returns empathetic, bilingual redirection (e.g., advising users to call 15 for police or 1122 for medical).

### 🔍 Automated Department Routing
- Maps colloquial Karachi civic issues to official bodies (KWSB, KE, KMC, SSMB, SBCA, PTCL, SSGC).
- Assesses and assigns priority levels (`high`, `medium`, `low`) to every issue.

### 🌐 Live Information Researcher
- Executes real-time Google Searches via tool calling to scrape up-to-date official complaint portals, helplines, and physical addresses of the determined authority.

### 📝 Bilingual Formal Drafting
- Dynamically executes Python code to generate unique tracking reference numbers (`REF-2026-XXXXXXXX`) and localized timestamps.
- Generates highly formal, ready-to-print official complaint letters in both English and Urdu (Nastaliq).

### 💾 Local History & Memory
- Detects duplicate submissions to prevent spamming authorities.
- Tracks past complaints in browser `localStorage` and maintains status resolution flows.

---

## 🏗️ Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND                                  │
│                                                                        │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │ Next.js 14 Web UI (Tailwind CSS, Urdu Nastaliq Fonts)          │   │
│   │ Single Page App -> POST /api/complaint                         │   │
│   └────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  │ JSON Payload
┌─────────────────────────────────▼──────────────────────────────────────┐
│                              BACKEND API                               │
│                                                                        │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │ FastAPI (api/main.py)                                          │   │
│   │  ├─ Global Error Handlers (Bilingual)                          │   │
│   │  └─ Latency & Logging Middlewares                              │   │
│   └─────────────────────────────┬──────────────────────────────────┘   │
│                                 │                                      │
│   ┌─────────────────────────────▼──────────────────────────────────┐   │
│   │ ADK Orchestrator (agents/orchestrator.py)                      │   │
│   │                                                                │   │
│   │  1. Safety Pre-check (Gemini 2.5 Flash)                        │   │
│   │     If safe, triggers Sequential Pipeline:                     │   │
│   │                                                                │   │
│   │  ┌──────────┐   ┌────────────┐   ┌────────────┐   ┌──────────┐ │   │
│   │  │ Memory   ├──►│ Classifier ├──►│ Researcher ├──►│ Drafter  │ │   │
│   │  │ Agent    │   │ Agent      │   │ Agent      │   │ Agent    │ │   │
│   │  └──────────┘   └────────────┘   └─┬──────────┘   └──────────┘ │   │
│   └────────────────────────────────────┼───────────────────────────┘   │
└────────────────────────────────────────┼───────────────────────────────┘
                                         │
                             ┌───────────▼───────────┐
                             │ Google Search Tool    │
                             │ (Live portal scraping)│
                             └───────────────────────┘
```

---

## 🛠️ Tech Stack

### Backend

| Technology | Role |
|------------|------|
| Python 3.11+ | Runtime |
| FastAPI | REST API Framework |
| Uvicorn | ASGI Server |
| Google ADK | Multi-Agent Orchestration |
| Gemini API | LLM Engine (`gemini-2.5-flash`) |

### Frontend

| Technology | Role |
|------------|------|
| Next.js 14 | React Framework (App Router) |
| TypeScript | Type Safety |
| Tailwind CSS v4 | Utility-first styling & theming |
| CSS/Google Fonts | Urdu typography (`Noto Nastaliq Urdu`) |

### Infrastructure

| Service | Purpose |
|---------|---------|
| Google Cloud Run | Serverless API & Frontend Hosting |
| Google Cloud Build | CI/CD Pipeline |
| Google Secret Manager| Secure API Key Injection |

---

## ⚙️ How It Works

### 1. Memory Agent
Before processing, checks the internal memory service (mapping `user_id` to past complaints). If a user submits a nearly identical complaint that is still pending, it warns them to prevent duplicate tickets.

### 2. Classifier Agent
Extracts the core issue, assigns the responsible administrative body in Karachi, sets urgency, and returns structured JSON outlining the problem in English and Urdu.

### 3. Researcher Agent
Receives the target authority (e.g., "KWSB"). Uses a live Google Search tool to find the exact, current complaint portal URL, helpline numbers, and physical address for that authority.

### 4. Drafter Agent
Uses a secure Python code execution tool to generate a unique `REF` number and localized date. It then writes a highly formal, persuasive letter in English, and a perfectly localized Urdu letter requesting immediate action from the authority.

---

## 📁 Project Structure

```text
ShikayatAI/
│
├── agents/                       Google ADK AI Logic
│   ├── orchestrator.py           Pipeline manager & Safety Pre-check
│   ├── classifier.py             Categorization agent
│   ├── researcher.py             Live web search agent
│   ├── drafter.py                Letter generation agent (Python tool)
│   └── memory_agent.py           User session history management
│
├── api/                          Backend Server
│   └── main.py                   FastAPI endpoints & CORS config
│
├── eval/                         Benchmarking
│   └── test_cases.py             15 automated test cases evaluating safety/classification
│
├── frontend/                     Next.js Web Application
│   ├── src/app/
│   │   ├── page.tsx              Main UI, form, state, and results rendering
│   │   ├── layout.tsx            Metadata and font loading
│   │   └── globals.css           Tailwind configuration and custom fonts
│   ├── Dockerfile                Standalone image builder for Cloud Run
│   └── next.config.ts            Standalone output configuration
│
├── cloudbuild.yaml               CI/CD deployment pipeline for GCP
├── smoke_test.py                 Post-deployment verification script
├── Dockerfile                    Backend API Docker image builder
└── requirements.txt              Python dependencies
```

---

## 🚀 Local Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- A Google Gemini API Key

### Step 1 — Backend Setup

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Create environment file
echo GOOGLE_API_KEY=your_gemini_key_here > .env
```

### Step 2 — Start the Backend API

```bash
uvicorn api.main:app --reload --port 8000
```
Verify it's running: `curl http://localhost:8000/api/health`

### Step 3 — Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
echo NEXT_PUBLIC_API_URL=http://localhost:8000 > .env.local
```

### Step 4 — Start the Frontend UI

```bash
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) to view the ShikayatAI dashboard.

---

## 📡 API Reference

### `POST /api/complaint`
Main inference endpoint. Runs safety check and orchestrator pipeline.

**Body:**
```json
{
  "complaint": "Teen din se pani nahi aa raha...",
  "location": "PECHS Block 2",
  "user_id": "user_xyz123"
}
```

### `GET /api/health`
**Response:**
```json
{
  "status": "ok",
  "model": "gemini-2.5-flash",
  "agents": ["Classifier", "Researcher", "Drafter", "Memory"]
}
```

---

## ☁️ Deployment (Google Cloud Run)

We deploy both the Python Backend and the Next.js Frontend to Google Cloud Run. For automated CI/CD, use the provided `cloudbuild.yaml`.

### 1. Set up Secrets
Add your Gemini API Key to Google Cloud Secret Manager:
```bash
printf "YOUR_GEMINI_API_KEY" | gcloud secrets create shikayatai-google-api-key --data-file=-

gcloud secrets add-iam-policy-binding shikayatai-google-api-key \
  --member="serviceAccount:COMPUTE_ENGINE_DEFAULT_SERVICE_ACCOUNT" \
  --role="roles/secretmanager.secretAccessor"
```

### 2. Deploy the Backend API
```bash
gcloud run deploy shikayatai-api \
  --source . \
  --region asia-south1 \
  --platform managed \
  --allow-unauthenticated \
  --update-secrets=GOOGLE_API_KEY=shikayatai-google-api-key:latest
```
*(Copy the resulting URL for the next step)*

### 3. Deploy the Next.js Web UI
Deploy the web frontend, passing the backend API URL as a build argument:
```bash
cd frontend

gcloud run deploy shikayatai-web \
  --source . \
  --region asia-south1 \
  --platform managed \
  --allow-unauthenticated \
  --set-build-env-vars NEXT_PUBLIC_API_URL=https://shikayatai-api-[YOUR_PROJECT].run.app
```

---

## 📄 License

This project is open-source and available for educational and commercial use under the MIT License.

---

**Made with ❤️ by [Abdul Hayy Khan](https://www.linkedin.com/in/abdulhayykhan)**