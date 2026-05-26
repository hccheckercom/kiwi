"""Semantic Embeddings for Pattern Similarity

Uses sentence-transformers to generate embeddings for patterns and compute
semantic similarity. Replaces Levenshtein distance with cosine similarity.
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional
import numpy as np
import pickle

sys.path.insert(0, str(Path(__file__).parent.parent))

# Lazy import to avoid loading model on module import
_model = None
_cache = {}


def get_embedding_model():
    """
    Load sentence-transformers model (all-MiniLM-L6-v2).

    Model is cached after first load.
    """
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model


def embed_pattern(pattern: str, context: str = "") -> np.ndarray:
    """
    Generate embedding for pattern + context.

    Args:
        pattern: Regex pattern or code snippet
        context: Additional context (title, category, why)

    Returns:
        384-dimensional embedding vector
    """
    model = get_embedding_model()

    # Combine pattern and context for better semantic understanding
    text = f"{pattern} {context}".strip()

    # Check cache
    cache_key = hash(text)
    if cache_key in _cache:
        return _cache[cache_key]

    # Generate embedding
    embedding = model.encode(text, convert_to_numpy=True)

    # Cache result
    _cache[cache_key] = embedding

    return embedding


def semantic_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
    """
    Cosine similarity between embeddings.

    Returns: Similarity score (0-1)
    """
    # Cosine similarity: dot product of normalized vectors
    norm1 = np.linalg.norm(emb1)
    norm2 = np.linalg.norm(emb2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(np.dot(emb1, emb2) / (norm1 * norm2))


def cluster_patterns_semantic(patterns: List[Dict], threshold: float = 0.85) -> List[List[Dict]]:
    """
    DBSCAN clustering using semantic embeddings.

    Args:
        patterns: List of pattern dicts with 'pattern', 'title', 'category'
        threshold: Similarity threshold for clustering (default 0.85)

    Returns: List of clusters, each cluster is list of pattern dicts
    """
    from sklearn.cluster import DBSCAN

    if len(patterns) < 2:
        return []

    # Generate embeddings for all patterns
    embeddings = []
    for p in patterns:
        context = f"{p.get('title', '')} {p.get('category', '')}"
        emb = embed_pattern(p.get('pattern', ''), context)
        embeddings.append(emb)

    embeddings_array = np.array(embeddings)

    # DBSCAN clustering
    # eps = 1 - threshold (distance threshold)
    # min_samples = 2 (minimum cluster size)
    clustering = DBSCAN(eps=1 - threshold, min_samples=2, metric='cosine')
    labels = clustering.fit_predict(embeddings_array)

    # Group patterns by cluster label
    clusters_dict = {}
    for idx, label in enumerate(labels):
        if label == -1:  # Noise point
            continue
        if label not in clusters_dict:
            clusters_dict[label] = []
        clusters_dict[label].append(patterns[idx])

    return list(clusters_dict.values())


def cache_embeddings_to_db(lesson_id: str, embedding: np.ndarray):
    """
    Store embedding in SQLite for faster lookups.

    Args:
        lesson_id: Lesson ID
        embedding: 384-dimensional embedding vector
    """
    from memory.db import get_connection

    conn = get_connection()
    try:

        # Serialize embedding to bytes
        embedding_bytes = pickle.dumps(embedding)

        conn.execute("""
            INSERT OR REPLACE INTO embeddings (lesson_id, embedding, created_at)
            VALUES (?, ?, datetime('now'))
        """, (lesson_id, embedding_bytes))

        conn.commit()
    finally:
        conn.close()


def load_embedding_from_db(lesson_id: str) -> Optional[np.ndarray]:
    """
    Load cached embedding from SQLite.

    Returns: Embedding vector or None if not cached
    """
    from memory.db import get_connection

    conn = get_connection()
    try:

        cursor = conn.execute("""
            SELECT embedding FROM embeddings WHERE lesson_id = ?
        """, (lesson_id,))

        row = cursor.fetchone()
    finally:
        conn.close()

    if row:
        return pickle.loads(row[0])  # nosec: internal embedding cache from Kiwi's own DB

    return None


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Test semantic embeddings')
    parser.add_argument('--compare', action='store_true', help='Compare semantic vs Levenshtein')

    args = parser.parse_args()

    if args.compare:
        from difflib import SequenceMatcher

        # Test patterns
        patterns = [
            {"pattern": "def.*without.*type", "title": "Missing type hints", "category": "python"},
            {"pattern": "function.*no.*types", "title": "No type annotations", "category": "python"},
            {"pattern": "SELECT.*WHERE.*=.*%s", "title": "SQL injection", "category": "security"},
        ]

        print("Semantic Similarity:")
        for i, p1 in enumerate(patterns):
            for j, p2 in enumerate(patterns):
                if i >= j:
                    continue
                emb1 = embed_pattern(p1['pattern'], f"{p1['title']} {p1['category']}")
                emb2 = embed_pattern(p2['pattern'], f"{p2['title']} {p2['category']}")
                sim = semantic_similarity(emb1, emb2)
                print(f"  {p1['title']} <-> {p2['title']}: {sim:.3f}")

        print("\nLevenshtein Similarity:")
        for i, p1 in enumerate(patterns):
            for j, p2 in enumerate(patterns):
                if i >= j:
                    continue
                sim = SequenceMatcher(None, p1['pattern'], p2['pattern']).ratio()
                print(f"  {p1['title']} <-> {p2['title']}: {sim:.3f}")
    else:
        # Simple test
        emb1 = embed_pattern("def.*without.*type", "Missing type hints python")
        emb2 = embed_pattern("function.*no.*types", "No type annotations python")
        sim = semantic_similarity(emb1, emb2)
        print(f"Semantic similarity: {sim:.3f}")
        print("Embeddings module OK")