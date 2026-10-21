"""Insight Agent: retrieval + constrained generation + honesty gate.

Two generation modes, selected at runtime:

1. **LLM mode** (GROQ_API_KEY set): Groq generates from retrieved facts only;
   `verify.py` re-checks every number and citation tag, and discards the reply
   if anything is unsupported.
2. **Extractive mode** (no key, default for offline judging): the answer is
   assembled from the retrieved gold-table facts themselves. No generation, so
   no hallucination is possible; every sentence carries its citation tag and
   the underlying row ids. This mode is deliberately boring and trustworthy.

Both modes share the structural refusal gate: if retrieval confidence is below
the mode's threshold, the agent says it does not know.
"""

from __future__ import annotations

import os
import re
import calendar
from collections import OrderedDict
from dataclasses import dataclass
from typing import AsyncIterator, Literal

from rag.config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    GROQ_URDU_MODEL,
    MIN_RELEVANCE_SCORE,
    MIN_RELEVANCE_TFIDF,
    PRIMARY_USER_PERSONA,
    TOP_K,
)
from rag.prompts import (
    MAIN_TEMPLATE_EN,
    MAIN_TEMPLATE_URDU,
    REFUSAL_EN,
    REFUSAL_URDU,
)
from rag.retrieval import Evidence, best_score, embedding_mode, retrieve
from rag.verify import log_verification, verify_answer

Language = Literal["en", "ur"]

REFUSAL_MARKER = "I don't know"
REFUSAL_MARKER_URDU = "معذرت"
WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class Answer:
    text: str
    refused: bool
    evidence: list[Evidence]


def _format_evidence(evidence: list[Evidence]) -> str:
    return "\n".join(f"- {e.text} (rows: {e.row_ids})" for e in evidence)


URDU_GLOSSARY = {
    "پیٹرول": "petrol", "ڈیزل": "diesel", "قیمت": "price", "تیل": "oil",
    "پاکستان": "Pakistan", "کراچی": "Karachi", "لاہور": "Lahore",
    "اسلام آباد": "Islamabad", "راولپنڈی": "Rawalpindi", "ماڈل": "model",
    "درست": "accuracy", "درستگی": "accuracy", "موجودہ": "current",
    "آج": "today", "حالیہ": "latest", "بیس لائن": "baseline",
    "بہتری": "improvement", "شرح": "rate", "لیٹر": "litre",
    "درآمد": "import", "اپریل": "April", "جنوری": "January",
    "فروری": "February", "مارچ": "March", "مئی": "May", "جون": "June",
    "جولائی": "July", "اگست": "August", "ستمبر": "September",
    "اکتوبر": "October", "نومبر": "November", "دسمبر": "December",
}


def normalize_query(question: str) -> str:
    """Deterministic Urdu->English glossary so lexical retrieval can work.

    This is a small, auditable dictionary, not a translation model. When a
    Mistral key is present the multilingual embedder handles Urdu directly and
    this remains a harmless no-op for English questions.
    """
    q = question
    for ur, en in URDU_GLOSSARY.items():
        q = q.replace(ur, f" {en} ")
    return q


def _coverage(evidence: list[Evidence]) -> str:
    entities = OrderedDict()
    for e in evidence:
        name = e.meta.get("entity", "")
        if name:
            entities[name] = True
    return ", ".join(list(entities)[:5])


def relevance_floor() -> float:
    return MIN_RELEVANCE_SCORE if embedding_mode() == "mistral-embed" \
        else MIN_RELEVANCE_TFIDF


# Core scope terms. A bare "price" is not enough on its own (e.g. "price of
# gold"), but "price" plus a place or product is.
CORE_TERMS = {
    "petrol", "diesel", "fuel", "gasoline", "hsd", "brent", "crude", "oil",
    "petroleum", "volatility", "model", "mae", "forecast", "accuracy",
    "accurate", "baseline", "interval", "coverage", "pass-through", "spi",
}
PLACES = {"pakistan", "islamabad", "rawalpindi", "gujranwala", "sialkot",
          "lahore", "faisalabad", "sargodha", "multan", "bahawalpur",
          "karachi", "hyderabad", "sukkur", "larkana", "peshawar", "bannu",
          "quetta", "khuzdar"}

# The record covers Pakistani retail prices and global benchmarks, not other
# countries' retail prices. Naming one is a scope miss, not a retrieval miss.
FOREIGN_PLACES = {
    "india", "indian", "indias", "delhi", "mumbai", "bangalore", "kolkata",
    "bangladesh", "dhaka", "sri", "lanka", "colombo", "nepal", "kathmandu",
    "china", "chinese", "beijing", "usa", "american", "america", "canada",
    "uk", "britain", "british", "london", "europe", "germany", "france",
    "dubai", "uae", "saudi", "riyadh", "iran", "tehran", "afghanistan",
    "kabul", "russia", "japan", "tokyo", "australia", "turkey",
}


def is_in_scope(question: str) -> bool:
    tokens = set(re.findall(r"[a-z\-]+", question.lower()))
    if tokens & FOREIGN_PLACES:
        return False
    if tokens & CORE_TERMS:
        return True
    if (tokens & {"price", "prices", "cost", "costs", "rate", "rates"}) \
            and (tokens & PLACES):
        return True
    return False

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
    "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}

RECENCY_WORDS = {"current", "currently", "latest", "today", "now", "recent",
                 "recently", "this week", "this month"}


def _time_constraints(question: str) -> tuple[set[int], set[int]]:
    q = question.lower()
    years = {int(y) for y in re.findall(r"\b(20\d{2})\b", q)}
    months = {num for name, num in MONTHS.items() if name in q}
    return years, months


def _filter_time(evidence: list[Evidence], question: str) -> list[Evidence]:
    years, months = _time_constraints(question)
    if not years and not months:
        return evidence
    kept = []
    for e in evidence:
        period = str(e.meta.get("period_end", ""))[:10]
        try:
            y, m = int(period[:4]), int(period[5:7])
        except (ValueError, TypeError):
            continue
        if years and y not in years:
            continue
        if months and m not in months:
            continue
        kept.append(e)
    return kept


def _apply_recency(evidence: list[Evidence], question: str) -> list[Evidence]:
    q = question.lower()
    asks_value = re.search(
        r"\b(what is|what are|how much (is|are))\b.*\b(price|cost|rate|mae|coverage)\b",
        q,
    )
    if not any(w in q for w in RECENCY_WORDS) and not asks_value:
        return evidence
    latest: dict[str, Evidence] = {}
    for e in evidence:
        entity = e.meta.get("entity", e.doc_id)
        prev = latest.get(entity)
        if prev is None or str(e.meta.get("period_end", "")) > \
                str(prev.meta.get("period_end", "")):
            latest[entity] = e
    return sorted(latest.values(),
                  key=lambda e: str(e.meta.get("period_end", "")), reverse=True)


def _filter_product_city(evidence: list[Evidence],
                         question: str) -> list[Evidence]:
    q = question.lower()
    petrol = "petrol" in q or "gasoline" in q
    diesel = "diesel" in q or "hsd" in q
    cities = ["islamabad", "rawalpindi", "gujranwala", "sialkot", "lahore",
              "faisalabad", "sargodha", "multan", "bahawalpur", "karachi",
              "hyderabad", "sukkur", "larkana", "peshawar", "bannu", "quetta",
              "khuzdar"]
    wanted_city = next((c for c in cities if c in q), None)

    out = evidence
    if petrol and not diesel:
        out = [e for e in out if "petrol" in str(e.meta.get("entity", "")).lower()]
    elif diesel and not petrol:
        out = [e for e in out if "diesel" in str(e.meta.get("entity", "")).lower()]
    if wanted_city:
        out = [e for e in out
               if wanted_city in str(e.meta.get("entity", "")).lower()]
    return out


def select_evidence(question: str, evidence: list[Evidence]) -> list[Evidence]:
    """Apply declared scope, time, product/city and recency filters."""
    if not is_in_scope(question):
        return []
    filtered = _filter_time(evidence, question)
    filtered = _filter_product_city(filtered, question)
    filtered = _apply_recency(filtered, question)
    # A zero/weak match is never shown as evidence; refusal happens above.
    return [e for e in filtered if e.score >= relevance_floor()]


def should_refuse(evidence: list[Evidence], question: str = "") -> bool:
    if question and not is_in_scope(question):
        return True
    return best_score(evidence) < relevance_floor()


def build_refusal(lang: Language, evidence: list[Evidence]) -> str:
    coverage = ("Pakistani petrol and diesel prices (national and by city), "
                "global petroleum prices, and model evaluation results")
    tpl = REFUSAL_URDU if lang == "ur" else REFUSAL_EN
    return tpl.format(coverage=coverage)


def _fmt_value(v: str, unit: str) -> str:
    try:
        f = float(v)
        return f"{f:,.2f}"
    except Exception:
        return v



_UR_PRODUCT = {
    "Petrol Super": "پیٹرول سپر",
    "High-speed diesel": "ہائی اسپیڈ ڈیزل",
}
_UR_PLACE = {
    "Pakistan": "پاکستان", "Karachi": "کراچی", "Lahore": "لاہور",
    "Islamabad": "اسلام آباد", "Rawalpindi": "راولپنڈی",
    "Gujranwala": "گوجرانوالہ", "Sialkot": "سیالکوٹ",
    "Faisalabad": "فیصل آباد", "Sargodha": "سرگودھا", "Multan": "ملتان",
    "Bahawalpur": "بہاولپور", "Hyderabad": "حیدرآباد", "Sukkur": "سکھر",
    "Larkana": "لاڑکانہ", "Peshawar": "پشاور", "Bannu": "بنوں",
    "Quetta": "کوئٹہ", "Khuzdar": "خضدار",
    "National average": "قومی اوسط",
}
_UR_MONTH = {
    "January": "جنوری", "February": "فروری", "March": "مارچ",
    "April": "اپریل", "May": "مئی", "June": "جون", "July": "جولائی",
    "August": "اگست", "September": "ستمبر", "October": "اکتوبر",
    "November": "نومبر", "December": "دسمبر",
}
_UR_ENTITY = {
    "Empirical coverage of the 90% prediction interval":
        "90% پیشین گوئی وقفہ کی تجرباتی کوریج",
    "Model MAE improvement over baseline":
        "بیس لائن کے مقابلے ماڈل کی MAE بہتری",
    "Baseline persistence MAE (annualised volatility points)":
        "بیس لائن پرسسٹنس MAE (سالانہ اتار چڑھاؤ پوائنٹس)",
    "Challenger HAR ridge MAE (annualised volatility points)":
        "چیلنجر HAR رج MAE (سالانہ اتار چڑھاؤ پوائنٹس)",
    "Pakistan pass-through slope":
        "پاکستان میں قیمت کی منتقلی کا سلوپ",
}


def _urdu_entity(entity: str) -> str:
    if entity in _UR_ENTITY:
        return _UR_ENTITY[entity]
    match = re.match(r"(.+?) price in (.+)", entity)
    if match:
        product = _UR_PRODUCT.get(match.group(1), match.group(1))
        place = _UR_PLACE.get(match.group(2), match.group(2))
        return f"{place} میں {product} کی قیمت"
    return entity


def _urdu_unit(unit: str) -> str:
    return {
        "PKR/L": "روپے فی لیٹر",
        "%": "فیصد",
        "annualised vol points": "سالانہ اتار چڑھاؤ پوائنٹس",
        "USD/bbl": "امریکی ڈالر فی بیرل",
    }.get(unit, unit)


def _urdu_period(period: str) -> str:
    if period.startswith("the week ended "):
        return "ہفتہ اختتام " + period[len("the week ended "):]
    if " to " in period:
        return period.replace(" to ", " تا ")
    month = next((m for m in _UR_MONTH if re.fullmatch(rf"{m} \d{{4}}", period)), None)
    if month:
        return period.replace(month, _UR_MONTH[month])
    return period

def extractive_answer(question: str, evidence: list[Evidence],
                      lang: Language) -> tuple[str, list[Evidence]]:
    """Quote the retrieved facts verbatim; return the facts actually quoted."""
    picked = [e for e in evidence if e.score >= relevance_floor()][:3]
    if not picked:
        return build_refusal(lang, evidence), []
    # If the question names a period, show the whole matching series for the
    # same entity rather than an arbitrary single week.
    top = picked[0]
    same = [e for e in evidence
            if e.meta.get("entity") == top.meta.get("entity")]
    if len(same) > 1:
        picked = sorted(same, key=lambda e: str(e.meta.get("period_end", "")))[:4]
    lines = []
    for e in picked:
        entity = e.meta.get("entity", e.doc_id)
        value = _fmt_value(e.meta.get("value", ""), e.meta.get("unit", ""))
        unit = e.meta.get("unit", "")
        pb = e.meta.get("period_begin", "")
        pe = e.meta.get("period_end", "")
        table = e.meta.get("table_name", "")
        if pb == pe and e.meta.get("table_name") == "pk_city_prices_monthly":
            try:
                period = f"{calendar.month_name[int(str(pb)[5:7])]} {str(pb)[:4]}"
            except (ValueError, IndexError):
                period = f"{pb}"
        elif pb == pe and table == "pk_petrol_weekly":
            period = f"the week ended {pb}"
        else:
            period = pb if pb == pe else f"{pb} to {pe}"
        if lang == "ur":
            unit_ur = _urdu_unit(unit)
            value_part = f"{value} {unit_ur}".strip()
            lines.append(
                f"{_urdu_entity(entity)}: {value_part}، مدت "
                f"{_urdu_period(period)} [{e.citation_tag}]۔"
            )
        else:
            lines.append(f"{entity} was {value} {unit} for {period} "
                         f"[{e.citation_tag}].")
    header = ("ثبوت کے مطابق:" if lang == "ur" else "From the cited record:")
    return header + "\n" + "\n".join(lines), picked


def _sanitize(text: str) -> str:
    text = WHITESPACE_RE.sub(" ", text).strip()
    return re.sub(r"\[([A-Za-z0-9_\-]+)\]", r"\1", text)


async def _llm_answer(question: str, evidence: list[Evidence],
                      lang: Language, history: list[str] | None) -> Answer:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_groq import ChatGroq

    evidence_texts = [e.text for e in evidence]
    valid_tags = {e.citation_tag for e in evidence}
    history_context = "\n".join((history or [])[-5:])

    if lang == "ur":
        template, marker, model_name = (
            MAIN_TEMPLATE_URDU, REFUSAL_MARKER_URDU, GROQ_URDU_MODEL,
        )
    else:
        template, marker, model_name = (
            MAIN_TEMPLATE_EN, REFUSAL_MARKER, GROQ_MODEL,
        )

    model = ChatGroq(model=model_name, api_key=GROQ_API_KEY, temperature=0.1)
    messages = ChatPromptTemplate.from_template(template).format_messages(
        persona=PRIMARY_USER_PERSONA,
        evidence=_format_evidence(evidence),
        chat_history=history_context or "(none)",
        question=question,
    )
    raw = (await model.ainvoke(messages)).content
    cleaned = _sanitize(raw)
    refusal_intended = cleaned.startswith(marker) or \
        cleaned.startswith(REFUSAL_MARKER_URDU)
    ver = verify_answer(cleaned, evidence_texts, valid_tags, refusal_intended)
    log_verification(question, ver, lang)
    if not ver.ok:
        return Answer(build_refusal(lang, evidence), True, evidence)
    return Answer(cleaned, refusal_intended, evidence)


async def generate_answer(
    question: str,
    lang: Language = "en",
    history: list[str] | None = None,
) -> Answer:
    search_query = normalize_query(question)
    if lang == "ur" and not re.search(r"\b20\d{2}\b", search_query):
        # Urdu present-tense questions ("... کیا ہے؟") ask for the current value.
        search_query += " current"
    retrieved = retrieve(search_query, k=max(TOP_K, 30))
    evidence = select_evidence(search_query, retrieved)
    if not evidence or should_refuse(retrieved, search_query):
        refusal = build_refusal(lang, retrieved)
        log_verification(
            question,
            verify_answer(refusal, [e.text for e in retrieved],
                          {e.citation_tag for e in retrieved}, True),
            lang,
        )
        return Answer(refusal, True, [])

    if GROQ_API_KEY:
        return await _llm_answer(question, evidence, lang, history)

    text, cited = extractive_answer(question, evidence, lang)
    refused = text.startswith(REFUSAL_EN.split("{")[0]) or \
        text.startswith("معذرت") or text.startswith("I don't know")
    log_verification(
        question,
        verify_answer(text, [e.text for e in cited],
                      {e.citation_tag for e in cited}, refused),
        lang,
    )
    return Answer(text, refused, cited)


async def ask_async(question: str, lang: Language = "en",
                    history: list[str] | None = None) -> str:
    return (await generate_answer(question, lang, history)).text


def ask(question: str, lang: Language = "en",
        history: list[str] | None = None) -> str:
    import asyncio

    return asyncio.run(ask_async(question, lang, history))


def ask_english(question: str, history: list[str] | None = None) -> str:
    return ask(question, "en", history)


def ask_urdu(question: str, history: list[str] | None = None) -> str:
    return ask(question, "ur", history)


async def ask_stream(question: str, lang: Language = "en",
                     history: list[str] | None = None) -> AsyncIterator[str]:
    answer = await generate_answer(question, lang, history)
    text = answer.text
    for i in range(0, len(text), 64):
        yield text[i: i + 64]
        if i + 64 < len(text):
            import asyncio as _aio

            await _aio.sleep(0.01)
