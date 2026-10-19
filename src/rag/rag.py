"""Insight Agent: retrieval + constrained generation + honesty gate.

Flow:
1. Embed the question with Mistral, retrieve top-k gold facts from Chroma.
2. If the best similarity score is below MIN_RELEVANCE -> refuse upfront
   ("I don't know"), skip the LLM entirely (structural gate, not prompt-based).
3. Otherwise generate with Groq from ONLY the retrieved facts.
4. verify_answer() re-checks every number and citation tag in the reply.
   If the model hallucinated a number, the reply is discarded and replaced
   with the structured refusal. Violations are logged to
   artifacts/rag_integrity.csv for the repo's honesty audit trail.
"""

from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import AsyncIterator, Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from rag.citations import load_citation_registry  # noqa: F401 (re-exported)
from rag.config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    GROQ_URDU_MODEL,
    MIN_RELEVANCE_SCORE,
    PRIMARY_USER_PERSONA,
    TOP_K,
)
from rag.prompts import (
    MAIN_TEMPLATE_EN,
    MAIN_TEMPLATE_URDU,
    REFUSAL_EN,
    REFUSAL_URDU,
)
from rag.retrieval import Evidence, best_score, retrieve
from rag.verify import log_verification, verify_answer

Language = Literal["en", "ur"]

REFUSAL_MARKER = "I don't know"
REFUSAL_MARKER_URDU = "معذرت"

WHITESPACE_RE = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# helpers


def _format_evidence(evidence: list[Evidence]) -> str:
    return "\n".join(f"- {e.text} (rows: {e.row_ids})" for e in evidence)


def _coverage(evidence: list[Evidence]) -> str:
    entities = OrderedDict()
    for e in evidence:
        name = e.meta.get("entity", "")
        if name:
            entities[name] = True
    return ", ".join(entities)


def should_refuse(evidence: list[Evidence]) -> bool:
    """Structural refusal: retrieval confidence too low."""
    return best_score(evidence) < MIN_RELEVANCE_SCORE


def build_refusal(lang: Language, evidence: list[Evidence]) -> str:
    coverage = _coverage(evidence)
    tpl = REFUSAL_URDU if lang == "ur" else REFUSAL_EN
    return tpl.format(
        coverage=coverage or "petrol price facts; try asking about those"
    )


def sanitize(text: str) -> str:
    """Collapse whitespace; keep citation tags but visually space them."""
    text = WHITESPACE_RE.sub(" ", text).strip()
    return re.sub(r"\[([A-Za-z0-9_\-]+)\]", r"\1", text)


# ---------------------------------------------------------------------------
# generation


@dataclass
class Answer:
    text: str
    refused: bool
    evidence: list[Evidence]


async def generate_answer(
    question: str,
    lang: Language = "en",
    history: list[str] | None = None,
) -> Answer:
    """Retrieve -> (maybe refuse) -> generate -> verify -> (maybe override)."""
    evidence = retrieve(question, k=TOP_K)
    history_context = "\n".join((history or [])[-5:])
    evidence_texts = [e.text for e in evidence]
    valid_tags = {e.citation_tag for e in evidence}

    if should_refuse(evidence):
        refusal = build_refusal(lang, evidence)
        log_verification(
            question,
            verify_answer(refusal, evidence_texts, valid_tags, refusal=True),
            lang,
        )
        return Answer(refusal, refused=True, evidence=evidence)

    if lang == "ur":
        template, marker, model_name = (
            MAIN_TEMPLATE_URDU, REFUSAL_MARKER_URDU, GROQ_URDU_MODEL,
        )
    else:
        template, marker, model_name = (
            MAIN_TEMPLATE_EN, REFUSAL_MARKER, GROQ_MODEL,
        )

    model = ChatGroq(model=model_name, api_key=GROQ_API_KEY, temperature=0.1)
    prompt = ChatPromptTemplate.from_template(template)
    messages = prompt.format_messages(
        persona=PRIMARY_USER_PERSONA,
        evidence=_format_evidence(evidence),
        chat_history=history_context or "(none)",
        question=question,
    )

    raw = (await model.ainvoke(messages)).content
    cleaned = sanitize(raw)

    refusal_intended = cleaned.startswith(marker) or cleaned.startswith(
        REFUSAL_MARKER_URDU
    ) or cleaned.startswith("معذرت")
    ver = verify_answer(
        cleaned,
        evidence_texts=evidence_texts,
        valid_tags=valid_tags,
        refusal=refusal_intended,
    )
    log_verification(question, ver, lang)

    if not ver.ok:
        # Model hallucinated a number or cited an unknown tag -> discard.
        return Answer(build_refusal(lang, evidence), refused=True,
                      evidence=evidence)
    return Answer(cleaned, refused=refusal_intended, evidence=evidence)


# ---------------------------------------------------------------------------
# public sync/async wrappers


def ask(
    question: str,
    lang: Language = "en",
    history: list[str] | None = None,
) -> str:
    """Blocking single answer. lang: 'en' (default) or 'ur' (Urdu toggle)."""
    import asyncio

    return asyncio.run(ask_async(question, lang, history))


async def ask_async(
    question: str,
    lang: Language = "en",
    history: list[str] | None = None,
) -> str:
    return (await generate_answer(question, lang, history)).text


def ask_english(question: str, history: list[str] | None = None) -> str:
    return ask(question, lang="en", history=history)


def ask_urdu(question: str, history: list[str] | None = None) -> str:
    return ask(question, lang="ur", history=history)


async def ask_stream(
    question: str,
    lang: Language = "en",
    history: list[str] | None = None,
) -> AsyncIterator[str]:
    """Streaming API.

    Because the honesty gate needs the *full* answer before it can pass or
    fail, we generate, verify, then stream out the final text in small
    chunks. Trustworthiness beats typing latency here, deliberately.
    """
    answer = await generate_answer(question, lang, history)
    text = answer.text
    for i in range(0, len(text), 64):
        yield text[i: i + 64]
        if i + 64 < len(text):
            import asyncio as _aio

            await _aio.sleep(0.02)
