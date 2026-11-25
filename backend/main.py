"""
main.py

FastAPI entrypoint for Role 3's chatbot.

Run locally:
    uvicorn main:app --reload --port 8000

Contract for frontend (put this in CONTRACTS.md):

POST /chat
  body: {"question": "What was our biggest expense this month?"}
  response: {
    "answer": "...",          # plain-language string to render in chat window
    "type": "general" | "whatif" | "refusal",
    "evidence": {...}          # only present for "whatif" — optional to show
  }
"""
import uuid

from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from chat import answer_question
from intelligence import router as intel_router
from imports import router as imports_router
from request_context import session_id

app = FastAPI(title="Finance Chatbot API")
app.include_router(intel_router)
app.include_router(imports_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5174", "https://phutcop.github.io"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def browser_session(request, call_next):
    raw = request.headers.get("X-Finshyt-Session", "")
    try:
        current = str(uuid.UUID(raw)) if raw else None
    except ValueError:
        current = None
    token = session_id.set(current)
    try:
        return await call_next(request)
    finally:
        session_id.reset(token)


class ChatRequest(BaseModel):
    question: str
    year: int | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(req: ChatRequest):
    return answer_question(req.question, selected_year=req.year)
