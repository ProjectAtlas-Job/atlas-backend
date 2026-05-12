from __future__ import annotations

import re
from io import BytesIO


def extract_text(file_bytes: bytes, format: str) -> str:
    if format == "pdf":
        import fitz

        document = fitz.open(stream=file_bytes)
        try:
            return "\n".join(page.get_text() for page in document)
        finally:
            document.close()

    if format in {"docx", "doc"}:
        from docx import Document

        document = Document(BytesIO(file_bytes))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)

    if format in {"txt", "md"}:
        return file_bytes.decode("utf-8")

    raise ValueError(f"Unsupported resume format: {format}")


def normalise_text(raw: str) -> str:
    cleaned = "".join(character for character in raw if character.isprintable() or character in "\n\t")
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r" *\n *", "\n", cleaned)
    cleaned = re.sub(r"\n\s*\n+", "\n\n", cleaned)
    return cleaned.strip()
