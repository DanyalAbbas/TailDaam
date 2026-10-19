"""FastAPI service for the Insight Agent.

Endpoints:
- GET  /health          -> {"status": "ok", "facts_indexed": N}
- POST /ask             -> {"answer": ..., "refused": bool, "citations": [...], "row_ids": [...]}
- POST /ask/stream      -> Server-Sent Events stream of the final verified text
- GET  /index/status    -> how many gold facts are indexed

Environment:
    GROQ_API_KEY, MISTRAL_API_KEY (required)
    GROQ_MODEL, GROQ_URDU_MODEL, RAG_TOP_K, RAG_MIN_RELEVANCE (optional)

Run (dev):
    uvicorn rag.api:app --reload --port 8000  (from src/)
Or:
    python -m rag.api  (from src/)

HF Space deploy runs this with `uvicorn` or `fastapi run`; the React build can
be mounted later via app.frontend("/", directory="frontend/dist")
(FastAPI >= 0.138) once the UI teammate lands their build.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field

from rag.rag import generate_answer, ask_async
from rag.retrieval import get_vectorstore


app = FastAPI(
    title="HackInsight Insight Agent",
    description=(
        "RAG over verified gold tables. Every number is traceable to row ids "
        "and a licence; the agent refuses when evidence is missing."
    ),
    version="0.1.0",
)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    lang: Literal["en", "ur"] = "en"
    history: list[str] | None = None


@app.get("/health")
async def health():
    try:
        vs = get_vectorstore()
        n_facts = vs._collection.count()
    except Exception:
        n_facts = 0
    return {"status": "ok", "facts_indexed": n_facts}


@app.post("/ask")
async def ask(req: AskRequest):
    try:
        answer = await generate_answer(req.question, req.lang, req.history)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    citations = sorted({e.citation_tag for e in answer.evidence})
    row_ids = sorted(
        {rid for e in answer.evidence for rid in e.row_ids.split(",") if rid}
    )
    return {
        "answer": answer.text,
        "refused": answer.refused,
        "citations": citations,
        "row_ids": row_ids,
        "confidence": max((e.score for e in answer.evidence), default=0.0),
    }


@app.post("/ask/stream")
async def ask_stream(req: AskRequest):
    async def event_source():
        from rag.rag import generate_answer

        answer = await generate_answer(req.question, req.lang, req.history)
        citations = sorted({e.citation_tag for e in answer.evidence})
        # First a metadata frame, then the text frames.
        yield ServerSentEvent(
            {
                "type": "meta",
                "refused": answer.refused,
                "citations": citations,
                "row_ids": sorted(
                    {rid for e in answer.evidence for rid in e.row_ids.split(",")
                     if rid}
                ),
            }
        )
        text = answer.text
        for i in range(0, len(text), 64):
            yield ServerSentEvent({"type": "chunk", "text": text[i: i + 64]})
        yield ServerSentEvent({"type": "done"})

    return EventSourceResponse(event_source())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
