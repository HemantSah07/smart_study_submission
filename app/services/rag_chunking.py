# app/services/rag_chunking.py
def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
    """Word-count based chunking (simple, no tokenizer dependency for chunk boundaries).
    ~400 words ≈ 500-550 tokens, safely under context limits with room for prompt."""
    words = text.split()
    if not words:
        return []
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunks.append(' '.join(words[start:end]))
        start += (chunk_size - overlap)
    return chunks
