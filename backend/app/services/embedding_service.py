from typing import List, Optional, Any


class EmbeddingService:
    """
    Generates semantic embeddings for document chunks
    using the all-MiniLM-L6-v2 sentence-transformer model.
    """

    MODEL_NAME = "all-MiniLM-L6-v2"

    def __init__(self):
        # Lazy import SentenceTransformer to prevent 60-second module import freeze on Windows startup
        from sentence_transformers import SentenceTransformer
        try:
            self.model = SentenceTransformer(self.MODEL_NAME, local_files_only=True)
        except Exception:
            self.model = SentenceTransformer(self.MODEL_NAME)


    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate an embedding for a single text chunk.
        """

        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        embedding = self.model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True
        )

        return embedding.tolist()

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple chunks.
        """

        if not texts:
            return []

        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True
        )

        return embeddings.tolist()
