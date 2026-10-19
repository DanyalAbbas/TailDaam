"""RAG-based Insight Agent for HACK INSIGHT.

Honesty contract (hackathon rule 1):
- Every number in an answer comes from a gold table row snapshot stored in
  the Chroma document metadata (row_ids), never from the LLM.
- Every claim carries a citation tag like [FB21A] that resolves to a
  publisher + URL + licence.
- When retrieval confidence is low, the agent explicitly says it does not
  know instead of speculating.
"""

from rag.rag import ask, ask_stream, ask_english, ask_urdu
from rag.verify import verify_answer

__all__ = ["ask", "ask_stream", "ask_english", "ask_urdu", "verify_answer"]
