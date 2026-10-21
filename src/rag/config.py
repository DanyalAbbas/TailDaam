import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

BASE_DIR = Path(__file__).resolve().parents[2]

# Data team writes final gold parquet/csvs here (make data -> data/gold).
GOLD_DIR = Path(os.getenv("GOLD_DIR", BASE_DIR / "data" / "gold"))
# Clearly-labelled mock fixture used only for plumbing tests, never eval.
MOCK_GOLD_DIR = BASE_DIR / "data" / "mock" / "gold"

CHROMA_DIR = Path(os.getenv("CHROMA_DIR", BASE_DIR / "data" / "chroma"))

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_URDU_MODEL = os.getenv("GROQ_URDU_MODEL", GROQ_MODEL)
MISTRAL_EMBED_MODEL = os.getenv("MISTRAL_EMBED_MODEL", "mistral-embed")

# Retrieve top-k evidence chunks for the answer step.
TOP_K = int(os.getenv("RAG_TOP_K", "6"))
# Chunks whose best score (0-1 cosine similarity) falls below this are treated
# as unsupported -> the agent refuses. Two floors because the embedding backends
# have different score distributions; both are configurable.
MIN_RELEVANCE_SCORE = float(os.getenv("RAG_MIN_RELEVANCE", "0.55"))
MIN_RELEVANCE_TFIDF = float(os.getenv("RAG_MIN_RELEVANCE_TFIDF", "0.08"))

PRIMARY_USER_PERSONA = (
    "A commuter or small fleet operator in Karachi who budgets for fuel and "
    "wants honest, cited answers about recent PAKISTANI petrol price changes "
    "(PKR per litre, OGRA-notified) and what drove them."
)
