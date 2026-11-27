# app/services/rag_retrieval.py
import faiss
import numpy as np
import json
from app.models import MaterialChunk
from app.services.rag_embeddings import get_embedder

def retrieve_relevant_chunks(user_id: int, subject_id: int, query: str, top_k: int = 5) -> list[str]:
    """
    Builds an in-memory FAISS index from this subject's chunks and
    returns the top_k most relevant chunk texts for the query.
    """
    rows = MaterialChunk.query.filter_by(user_id=user_id, subject_id=subject_id).all()
    if not rows:
        return []

    vectors = np.array([json.loads(r.embedding_json) for r in rows]).astype('float32')
    index = faiss.IndexFlatL2(vectors.shape[1])
    index.add(vectors)

    query_vector = get_embedder().encode(query).astype('float32').reshape(1, -1)
    k = min(top_k, len(rows))
    distances, indices = index.search(query_vector, k)

    return [rows[i].chunk_text for i in indices[0]]


RAG_MIN_SIMILARITY_THRESHOLD = 0.40


def retrieve_relevant_chunks_with_metadata(user_id: int, subject_id: int = None, query: str = "", top_k: int = 3, chapter_id: int = None, topic_id: int = None) -> list[dict]:
    """
    Builds an in-memory FAISS index from authorized subject chunks and returns
    structured chunk metadata objects including L2 distance and similarity scores.
    If subject_id is None, searches across all study materials belonging to user_id.
    """
    query_filter = MaterialChunk.query.filter_by(user_id=user_id)
    if subject_id:
        query_filter = query_filter.filter_by(subject_id=subject_id)
    rows = query_filter.all()
    if not rows:
        return []

    if chapter_id or topic_id:
        filtered_rows = []
        for r in rows:
            mat = r.material
            if mat:
                if chapter_id and mat.chapter_id != chapter_id:
                    continue
                if topic_id and mat.topic_id != topic_id:
                    continue
            filtered_rows.append(r)
        if filtered_rows:
            rows = filtered_rows

    vectors = np.array([json.loads(r.embedding_json) for r in rows]).astype('float32')
    index = faiss.IndexFlatL2(vectors.shape[1])
    index.add(vectors)

    query_vector = get_embedder().encode(query).astype('float32').reshape(1, -1)
    k = min(top_k, len(rows))
    distances, indices = index.search(query_vector, k)

    results = []
    for idx_pos, i in enumerate(indices[0]):
        dist = float(distances[0][idx_pos])
        sim_score = round(1.0 / (1.0 + dist), 4)
        chunk_obj = rows[i]
        mat = chunk_obj.material

        results.append({
            "chunk_text": chunk_obj.chunk_text,
            "distance": round(dist, 4),
            "similarity_score": sim_score,
            "material_id": chunk_obj.material_id,
            "filename": mat.filename if mat else "Study Document",
            "relative_folder_path": mat.relative_folder_path if mat else None,
            "chapter_title": mat.chapter.title if (mat and mat.chapter) else None,
            "topic_title": mat.topic.title if (mat and mat.topic) else None,
        })

    return results
