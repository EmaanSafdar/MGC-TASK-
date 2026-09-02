"""
rag.py — retrieval + grounded generation.

Retrieval: TF-IDF + cosine similarity (scikit-learn). This is a deliberate
choice over sentence-transformers/FAISS: the corpus is 3 short documents
(~22 chunks total), so a heavy neural embedding model buys nothing here and
costs a slow first-run download from Hugging Face. TF-IDF is a legitimate
"lightweight local vector search" for a corpus this size, runs instantly
with no network access, and is trivial to swap out later (see
`build_index` / `search` below — that's the only place a FAISS+
sentence-transformers version would plug in) if the real document set grows.

Generation: calls the Gemini API (google-genai SDK) with a strict grounding
system prompt and only the retrieved chunks as context.
"""

import os
import re
import socket
from dataclasses import dataclass

from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ingest import Chunk, load_chunks

load_dotenv()  # reads GEMINI_API_KEY from a .env file in this folder, if present

# Force IPv4-only DNS resolution. On some networks IPv6 routes are broken/blackholed,
# and Python's http stack (unlike curl) doesn't fall back to IPv4 quickly — it just
# hangs until the IPv6 attempt times out. This skips IPv6 entirely.
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_only_getaddrinfo(*args, **kwargs):
    return [ai for ai in _orig_getaddrinfo(*args, **kwargs) if ai[0] == socket.AF_INET]
socket.getaddrinfo = _ipv4_only_getaddrinfo

SIMILARITY_THRESHOLD = 0.08  # below this, we treat retrieval as "insufficient evidence"
TOP_K = 5


@dataclass
class RetrievedChunk:
    chunk: Chunk
    score: float


class Retriever:
    def __init__(self):
        self.chunks: list[Chunk] = load_chunks()
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.matrix = self.vectorizer.fit_transform([c.text for c in self.chunks])

    def search(self, query: str, top_k: int = TOP_K) -> list[RetrievedChunk]:
        q_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(q_vec, self.matrix)[0]
        ranked = sorted(zip(self.chunks, sims), key=lambda x: x[1], reverse=True)
        return [RetrievedChunk(chunk=c, score=float(s)) for c, s in ranked[:top_k]]


SYSTEM_PROMPT = """You are the MGC Developments document assistant.

Your job is to answer salesperson questions using ONLY the information
contained in the provided MGC document excerpts below. You have no other
knowledge of MGC Aurora Heights beyond what is given to you here.

STRICT RULES:
1. Never invent, estimate, assume, or hallucinate information.
2. Do not use general world knowledge (typical rental yields, typical
   transfer fees elsewhere, etc.) to answer factual questions about MGC.
3. If the requested information cannot be found in the provided excerpts,
   clearly say it is not available in the provided documents, and suggest
   who the salesperson should ask (if the documents name someone, e.g. the
   marketing manager).
4. If two excerpts contain conflicting information (e.g. different values
   for the same fee), DO NOT silently pick one. State both values, name
   the document each came from, and say the authoritative figure cannot be
   determined from the provided documents.
5. If an excerpt explicitly says something is unconfirmed, pending, "to be
   announced", or "ongoing", preserve that status word-for-word in spirit —
   do not upgrade it to a confirmed fact.
6. For calculations, use only numbers explicitly present in the excerpts.
   Show your calculation step by step. If a premium or stacking rule is
   given in the text (e.g. "premiums are cumulative"), follow it exactly
   rather than guessing how values combine.
7. Every factual claim must be followed by its source, in this exact form:
   (Source: <document name> — Section: <section name>)
8. If you are not confident the excerpts answer the question, say so
   plainly rather than producing a confident but unsupported answer.

A cautious, well-sourced "I don't have that in the documents" is always
better than a fluent guess.
"""


def build_user_prompt(question: str, retrieved: list[RetrievedChunk]) -> str:
    context_blocks = []
    for r in retrieved:
        context_blocks.append(
            f"[Excerpt from {r.chunk.source}, Section: {r.chunk.section}]\n{r.chunk.text}"
        )
    context = "\n\n---\n\n".join(context_blocks)
    return (
        f"Here are the most relevant excerpts retrieved from the MGC documents "
        f"for this question:\n\n{context}\n\n"
        f"---\n\nSalesperson's question: {question}\n\n"
        f"Answer following the STRICT RULES above."
    )


def answer_question(question: str, retriever: Retriever, top_k: int = TOP_K):
    """Returns (answer_text, retrieved_chunks, evidence_level)."""
    retrieved = retriever.search(question, top_k=top_k)
    best_score = retrieved[0].score if retrieved else 0.0

    if best_score < SIMILARITY_THRESHOLD:
        return (
            "I couldn't find reliable supporting information for this question "
            "in the provided MGC documents. Please check with the marketing "
            "manager or the relevant department.",
            [],
            "Insufficient",
        )

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. "
            "Please add it to your .env file."
        )

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    user_prompt = build_user_prompt(question, retrieved)

    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=700,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    answer_text = resp.text

    evidence = "Strong" if best_score >= 0.15 else "Moderate"
    return answer_text, retrieved, evidence


if __name__ == "__main__":
    r = Retriever()
    for q in [
        "What's the base price of a 2-bed in Block B?",
        "What's the total for a Margalla-facing corner unit on floor 15, 2-bed Block B?",
        "What's the transfer fee?",
        "What's the rental yield on a 1-bed?",
        "Who is the anchor tenant?",
    ]:
        print("Q:", q)
        for rc in r.search(q, top_k=4):
            print(f"   {rc.score:.3f}  {rc.chunk.citation()}")
        print()
