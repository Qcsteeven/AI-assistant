# backend/main.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from backend.document_loader import DocumentLoader
from backend.vector_db import VectorDB
import os
import tempfile

app = FastAPI()
loader = DocumentLoader()
db = VectorDB()

# CORS middleware (оставляем как было)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Оригинальные разрешенные расширения (теперь методы берутся из DocumentLoader)
ALLOWED_EXTENSIONS = {
    ".docx": loader.load_docx_chunks,
    ".pdf": loader.load_pdf_chunks,
    ".xlsx": loader.load_xlsx_chunks
}

@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Загрузка и обработка нескольких .docx, .pdf, .xlsx файлов."""
    all_chunks = []

    try:
        for file in files:
            ext = os.path.splitext(file.filename)[-1].lower()

            if ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(status_code=400, detail=f"Файл '{file.filename}' имеет неподдерживаемое расширение")

            # Сохраняем файл во временный путь
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(await file.read())
                file_path = tmp.name

            # Загружаем чанки из файла
            load_method = ALLOWED_EXTENSIONS[ext]
            chunks = load_method(file_path)
            all_chunks.extend(chunks)

            # Удаляем временный файл
            os.unlink(file_path)

        # Передаем чанки в VectorDB и строим индекс
        db.set_chunks(all_chunks)
        db.build_faiss_index()

        return {
            "status": "success",
            "files_uploaded": [f.filename for f in files],
            "total_chunks": len(all_chunks)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при загрузке файлов: {str(e)}")

@app.post("/chat")
async def chat_endpoint(question: dict):
    """Получение ответа на основе загруженных документов."""
    if not db.index:
        raise HTTPException(status_code=400, detail="Документы не загружены")

    user_question = question.get("question", "").strip()
    if not user_question:
        raise HTTPException(status_code=400, detail="Вопрос не должен быть пустым")

    try:
        # Поиск релевантных чанков
        top_chunks = db.search_similar_chunks(user_question)
        context = "\n---\n".join(top_chunks)

        prompt = f"""
        Ты работаешь как ассистент, который отвечает на вопросы на основе загруженных документов. Ответ должен быть точным, ясным и структурированным. Прочитай предоставленный контекст и ответь на вопрос, используя его информацию.

        Контекст:
        {context}
        
        Вопрос: {user_question}
        
        Ответ должен быть максимально точным.
        """

        # Генерация ответа с помощью GPT (используем клиента из VectorDB)
        response = db.client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": prompt
            }],
            temperature=0.3
        )

        # Форматирование ответа
        answer = response.choices[0].message.content.strip()
        formatted_answer = answer.replace("- ", "\n- ").replace("\n\n", "\n")
        formatted_answer = formatted_answer.replace("—", "\n—")

        return {"answer": formatted_answer}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка обработки запроса: {str(e)}")

@app.get("/health")
def health_check():
    """Проверка статуса сервиса."""
    return {
        "status": "ok",
        "index_ready": db.index is not None,
        "chunks_loaded": len(db.chunks) if db.chunks else 0
    }