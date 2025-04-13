from typing import List, Optional, Tuple
import faiss
import numpy as np
import os
import pickle
from pathlib import Path
from openai import OpenAI
import logging

class VectorDB:
    def __init__(self, client: Optional[OpenAI] = None):
        self.client = client or OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.index: Optional[faiss.Index] = None
        self.embeddings: List[List[float]] = []
        self.chunks: List[str] = []
        self.logger = logging.getLogger(__name__)

    def set_chunks(self, chunks: List[str]):
        """Устанавливает текстовые чанки для индексирования"""
        if not chunks:
            raise ValueError("Список чанков не может быть пустым")
        self.chunks = chunks
        self.logger.info(f"Установлено {len(chunks)} чанков")

    def get_embedding(self, text: str) -> List[float]:
        """Получает эмбеддинг текста через OpenAI API"""
        try:
            response = self.client.embeddings.create(
                input=[text],
                model="text-embedding-ada-002"
            )
            return response.data[0].embedding
        except Exception as e:
            self.logger.error(f"Ошибка получения эмбеддинга: {str(e)}")
            raise

    def build_faiss_index(self) -> faiss.Index:
        """Строит индекс FAISS для текущих чанков"""
        if not self.chunks:
            raise ValueError("Нет чанков для индексирования")

        self.logger.info("Начало построения индекса...")
        self.embeddings = [self.get_embedding(chunk) for chunk in self.chunks]
        
        if not self.embeddings:
            raise ValueError("Не удалось получить эмбеддинги")

        dim = len(self.embeddings[0])
        self.index = faiss.IndexFlatL2(dim)
        self.index.add(np.array(self.embeddings).astype("float32"))
        self.logger.info(f"Индекс построен. Размерность: {dim}, Чанков: {len(self.chunks)}")
        return self.index

    def save_index(self, base_path: str) -> Tuple[str, str, str]:
        """
        Сохраняет индекс и данные на диск
        Возвращает пути к сохраненным файлам
        """
        if not self.index:
            raise ValueError("Индекс не инициализирован")

        Path(base_path).parent.mkdir(parents=True, exist_ok=True)
        
        index_file = f"{base_path}.index"
        embeddings_file = f"{base_path}_embeddings.pkl"
        chunks_file = f"{base_path}_chunks.pkl"

        try:
            # Сохраняем индекс FAISS
            faiss.write_index(self.index, index_file)
            
            # Сохраняем эмбеддинги
            with open(embeddings_file, 'wb') as ef:
                pickle.dump(self.embeddings, ef)
            
            # Сохраняем текстовые чанки
            with open(chunks_file, 'wb') as cf:
                pickle.dump(self.chunks, cf)
            
            self.logger.info(f"Данные сохранены: {index_file}, {embeddings_file}, {chunks_file}")
            return index_file, embeddings_file, chunks_file

        except Exception as e:
            self.logger.error(f"Ошибка сохранения: {str(e)}")
            raise

    def load_index(self, base_path: str) -> None:
        """
        Загружает индекс и данные с диска
        """
        index_file = f"{base_path}.index"
        embeddings_file = f"{base_path}_embeddings.pkl"
        chunks_file = f"{base_path}_chunks.pkl"

        try:
            # Проверяем существование файлов
            for f in [index_file, embeddings_file, chunks_file]:
                if not Path(f).exists():
                    raise FileNotFoundError(f"Файл не найден: {f}")

            # Загружаем индекс FAISS
            self.index = faiss.read_index(index_file)
            
            # Загружаем эмбеддинги
            with open(embeddings_file, 'rb') as ef:
                self.embeddings = pickle.load(ef)
            
            # Загружаем текстовые чанки
            with open(chunks_file, 'rb') as cf:
                self.chunks = pickle.load(cf)
            
            self.logger.info(f"Данные загружены. Чанков: {len(self.chunks)}")

        except Exception as e:
            self.logger.error(f"Ошибка загрузки: {str(e)}")
            raise

    def search_similar_chunks(self, query: str, k: int = 3) -> List[str]:
        """Ищет k наиболее похожих чанков на запрос"""
        if not self.index:
            raise ValueError("Индекс не инициализирован")
        if not query:
            raise ValueError("Запрос не может быть пустым")

        try:
            query_vec = np.array([self.get_embedding(query)]).astype("float32")
            _, indices = self.index.search(query_vec, k)
            return [self.chunks[i] for i in indices[0] if i < len(self.chunks)]
        except Exception as e:
            self.logger.error(f"Ошибка поиска: {str(e)}")
            raise