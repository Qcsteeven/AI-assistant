# backend/vector_db.py
from typing import List, Optional
import faiss
import numpy as np
import os
import pickle
from openai import OpenAI


class VectorDB:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.__init__()
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'is_initialized'):
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.index: Optional[faiss.Index] = None
            self.embeddings: List[List[float]] = []
            self.chunks: List[str] = []
            self.is_initialized = True

    def set_chunks(self, chunks: List[str]):
        self.chunks = chunks

    def get_embedding(self, text: str) -> List[float]:
        response = self.client.embeddings.create(
            input=[text],
            model="text-embedding-ada-002"
        )
        return response.data[0].embedding

    def build_faiss_index(self):
        self.embeddings = [self.get_embedding(chunk) for chunk in self.chunks]
        dim = len(self.embeddings[0])
        self.index = faiss.IndexFlatL2(dim)
        self.index.add(np.array(self.embeddings).astype("float32"))
        return self.index

    def save_index(self, index_file: str, embeddings_file: str, chunks_file: str):
        if self.index:
            faiss.write_index(self.index, index_file)
            with open(embeddings_file, 'wb') as ef:
                pickle.dump(self.embeddings, ef)
            with open(chunks_file, 'wb') as cf:
                pickle.dump(self.chunks, cf)

    def load_index(self, index_file: str, embeddings_file: str, chunks_file: str):
        self.index = faiss.read_index(index_file)
        with open(embeddings_file, 'rb') as ef:
            self.embeddings = pickle.load(ef)
        with open(chunks_file, 'rb') as cf:
            self.chunks = pickle.load(cf)

    def search_similar_chunks(self, query: str, k: int = 3) -> List[str]:
        if not self.index:
            raise ValueError("Индекс не инициализирован")
        query_vec = np.array([self.get_embedding(query)]).astype("float32")
        _, indices = self.index.search(query_vec, k)
        return [self.chunks[i] for i in indices[0]]