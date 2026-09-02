"""
ingest.py — turns the three MGC markdown documents into retrievable chunks.

Note on "page numbers": the source files provided for this assessment are
Markdown exports, not paginated PDFs, so there is no real page number to
preserve. Instead we chunk by section (## heading) and cite
"<document> — Section: <heading>", which is the actual, honest unit of
location in these files. If MGC later hands over the real PDFs, swap this
file's PDF_TO_TEXT step for pypdf page extraction and everything downstream
(rag.py, app.py) keeps working unchanged, because they only care about the
{text, source, section} shape below.
"""

import os
import re
from dataclasses import dataclass, field

DOCS_DIR = os.path.dirname(__file__)

# Friendly display names for the source files.
DISPLAY_NAMES = {
    "01_mgc_aurora_heights_brochure.md": "MGC Aurora Heights — Brochure",
    "02_price_list_payment_plan.md": "MGC Price List & Payment Plan",
    "03_booking_policy_faq.md": "MGC Booking Policy & Sales FAQ",
}


@dataclass
class Chunk:
    text: str
    source: str        # friendly document name
    section: str        # nearest ## heading
    chunk_id: str = field(default="")

    def citation(self) -> str:
        return f"{self.source} — Section: {self.section}"


def _split_into_sections(raw_text: str):
    """Split a markdown file into (heading, body) pairs using ## as the boundary.
    Content before the first ## (title/preamble) is kept under the file's H1 title."""
    lines = raw_text.splitlines()
    sections = []
    current_heading = None
    current_body = []

    # capture the H1 title as a fallback heading for the preamble
    title = "Overview"
    for line in lines:
        if line.startswith("# ") and title == "Overview":
            title = line.lstrip("#").strip()
            break

    current_heading = title
    for line in lines:
        if line.startswith("## "):
            if current_body:
                sections.append((current_heading, "\n".join(current_body).strip()))
            current_heading = line.lstrip("#").strip()
            current_body = []
        elif line.startswith("# "):
            continue  # already used as fallback title
        else:
            current_body.append(line)
    if current_body:
        sections.append((current_heading, "\n".join(current_body).strip()))

    return [(h, b) for h, b in sections if b.strip()]


def _chunk_section(heading: str, body: str, max_chars: int = 900):
    """Further split an overly long section into smaller chunks on blank-line
    boundaries, so no single chunk blows the context budget. Most MGC sections
    (tables, short paragraphs) fit in one chunk as-is."""
    if len(body) <= max_chars:
        return [body]

    parts = re.split(r"\n\s*\n", body)
    chunks, current = [], ""
    for part in parts:
        if len(current) + len(part) + 2 <= max_chars:
            current = f"{current}\n\n{part}".strip()
        else:
            if current:
                chunks.append(current)
            current = part
    if current:
        chunks.append(current)
    return chunks


def load_chunks() -> list[Chunk]:
    chunks: list[Chunk] = []
    for filename in sorted(os.listdir(DOCS_DIR)):
        if not filename.endswith(".md"):
            continue
        path = os.path.join(DOCS_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()

        display_name = DISPLAY_NAMES.get(filename, filename)
        sections = _split_into_sections(raw)

        for heading, body in sections:
            for i, piece in enumerate(_chunk_section(heading, body)):
                cid = f"{filename}::{heading}::{i}"
                chunks.append(Chunk(text=piece, source=display_name, section=heading, chunk_id=cid))

    return chunks


if __name__ == "__main__":
    cs = load_chunks()
    print(f"Loaded {len(cs)} chunks from {DOCS_DIR}\n")
    for c in cs:
        print(f"[{c.citation()}]")
        print(c.text[:120].replace("\n", " ") + ("..." if len(c.text) > 120 else ""))
        print()
