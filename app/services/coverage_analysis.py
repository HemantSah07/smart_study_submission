# app/services/coverage_analysis.py
import json
import numpy as np
from app.services.rag_embeddings import get_embedder
from app.models import MaterialChunk, ModuleDescriptor

def compute_coverage(user_id: int, subject_id: int, similarity_threshold: float = 0.35):
    descriptor = ModuleDescriptor.query.filter_by(user_id=user_id, subject_id=subject_id).first()
    if not descriptor or not descriptor.topics_json:
        return []

    try:
        topics = json.loads(descriptor.topics_json)
    except Exception:
        return []

    if not isinstance(topics, list) or not topics:
        return []

    chunks = MaterialChunk.query.filter_by(user_id=user_id, subject_id=subject_id).all()
    if not chunks:
        return [{'topic': str(t), 'covered': False, 'file_count': 0, 'max_similarity': 0.0} for t in topics]

    model = get_embedder()
    chunk_vectors = np.array([json.loads(c.embedding_json) for c in chunks])
    norms = np.linalg.norm(chunk_vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1e-10
    chunk_vectors_norm = chunk_vectors / norms

    results = []
    for topic in topics:
        topic_vec = model.encode(str(topic))
        t_norm = np.linalg.norm(topic_vec)
        if t_norm == 0:
            t_norm = 1e-10
        topic_vec_norm = topic_vec / t_norm
        similarities = chunk_vectors_norm @ topic_vec_norm
        matches = int((similarities >= similarity_threshold).sum())
        results.append({
            'topic': str(topic),
            'covered': matches > 0,
            'file_count': matches,
            'max_similarity': float(similarities.max()) if len(similarities) > 0 else 0.0,
        })
    return results
