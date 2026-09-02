"""
app.py — command-line interface for the MGC document assistant.

Usage:
    export GEMINI_API_KEY=AIza...
    python3 app.py
    python3 app.py "What's the transfer fee?"      # single question, no loop
"""

import sys

from rag import Retriever, answer_question


def print_answer(question: str, retriever: Retriever):
    print(f"\nQ: {question}")
    try:
        answer, retrieved, evidence = answer_question(question, retriever)
    except RuntimeError as e:
        print(f"\n[Error] {e}")
        return

    print(f"\n{answer}\n")
    print(f"Evidence: {evidence}")
    if retrieved:
        print("Retrieved context used:")
        seen = set()
        for r in retrieved:
            cite = r.chunk.citation()
            if cite in seen:
                continue
            seen.add(cite)
            print(f"  • {cite}  (score {r.score:.2f})")
    print("-" * 70)


def main():
    retriever = Retriever()

    if len(sys.argv) > 1:
        print_answer(" ".join(sys.argv[1:]), retriever)
        return

    print("MGC Document Assistant (type 'quit' to exit)\n")
    while True:
        try:
            q = input("Ask a question: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q or q.lower() in ("quit", "exit"):
            break
        print_answer(q, retriever)


if __name__ == "__main__":
    main()
