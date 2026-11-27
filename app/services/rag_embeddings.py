# app/services/rag_embeddings.py
import json
from sentence_transformers import SentenceTransformer

_model = None

def get_embedder():
    global _model
    if _model is None:
        _model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')  # 384-dim, ~80MB, local
    return _model

def embed_and_store_material(material_id: int):
    from app.models import UploadedMaterial, MaterialChunk
    from app import db
    material = UploadedMaterial.query.get(material_id)
    if not material or not material.extracted_text:
        return

    material.embedding_status = 'processing'
    db.session.commit()

    from app.services.rag_chunking import chunk_text
    chunks = chunk_text(material.extracted_text)
    model = get_embedder()

    # Clear old chunks if re-embedding
    MaterialChunk.query.filter_by(material_id=material.id).delete()

    for idx, chunk in enumerate(chunks):
        vector = model.encode(chunk).tolist()
        db.session.add(MaterialChunk(
            material_id=material.id, subject_id=material.subject_id,
            user_id=material.user_id, chunk_index=idx, chunk_text=chunk,
            token_count=len(chunk.split()), embedding_json=json.dumps(vector),
        ))

    material.embedding_status = 'ready'
    db.session.commit()
