# main.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from backend.app import VectorBackend
import os
import tempfile

app = FastAPI()
backend = VectorBackend()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_EXTENSIONS = {
    ".docx": backend.load_docx_chunks,
    ".pdf": backend.load_pdf_chunks,
    ".xlsx": backend.load_xlsx_chunks
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

        # Создаём FAISS индекс из всех чанков
        backend.build_faiss_index()

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
    if not backend.index:
        raise HTTPException(status_code=400, detail="Документы не загружены")

    user_question = question.get("question", "").strip()
    if not user_question:
        raise HTTPException(status_code=400, detail="Вопрос не должен быть пустым")

    try:
        top_chunks = backend.search_similar_chunks(user_question)
        context = "\n---\n".join(top_chunks)

        prompt = f"""
        Ты работаешь как ассистент, который отвечает на вопросы на основе загруженных документов. Ответ должен быть точным, ясным и структурированным. Прочитай предоставленный контекст и ответь на вопрос, используя его информацию.

        Контекст:
        {context}
        
        Вопрос: {user_question}
        
        ответ должен быть максимально точным.
        """

        response = backend.client.chat.completions.create(
            model="gpt-4o",  # Модель, которая будет использоваться
            messages=[{
                "role": "user",
                "content": prompt
            }],
            temperature=0.3  # Оптимальное значение для точных и структурированных ответов
        )

        # Форматирование ответа: с правильными разделами
        answer = response.choices[0].message.content.strip()

        # Теперь гарантируем, что вывод будет более структурированным
        formatted_answer = answer.replace("- ", "\n- ").replace("\n\n",
                                                                "\n")  # Стандартизируем список и убираем лишние отступы

        # Пример: если нет четких разделений, можно добавить их вручную
        formatted_answer = formatted_answer.replace("—", "\n—")  # Добавление нового абзаца перед длинными списками

        return {"answer": formatted_answer}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка обработки запроса: {str(e)}")


@app.get("/health")
def health_check():
    """Проверка статуса сервиса."""
    return {"status": "ok"}
