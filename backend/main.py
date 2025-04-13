from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from backend.document_loader import DocumentLoader
from backend.vector_db import VectorDB
from openai import OpenAI
import os
import tempfile
from uuid import uuid4
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
loader = DocumentLoader()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

chats = {}  # chat_id -> {"chunks": ..., "index": ..., "client": ...}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_EXTENSIONS = {
    ".docx": loader.load_docx_chunks,
    ".pdf": loader.load_pdf_chunks,
    ".xlsx": loader.load_xlsx_chunks
}

@app.post("/chat/new")
@app.get("/chat/new")  # Добавляем поддержку GET
def create_new_chat():
    chat_id = str(uuid4())
    chats[chat_id] = {
        "chunks": [],
        "index": None,
        "client": client
    }
    logger.info(f"Создан новый чат: {chat_id}")
    return {"chat_id": chat_id}

@app.post("/upload")
async def upload_files(
    chat_id: str = Form(...),
    files: List[UploadFile] = File(...)
):
    logger.info(f"Получен запрос на загрузку для чата: {chat_id}")
    
    if chat_id not in chats:
        raise HTTPException(status_code=404, detail="Чат не найден")

    all_chunks = []
    error_files = []

    for file in files:
        try:
            ext = os.path.splitext(file.filename)[-1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                error_files.append(f"Неподдерживаемый формат: {file.filename}")
                continue

            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                content = await file.read()
                if not content:
                    error_files.append(f"Пустой файл: {file.filename}")
                    continue
                
                tmp.write(content)
                tmp_path = tmp.name

            try:
                chunks = ALLOWED_EXTENSIONS[ext](tmp_path)
                if chunks:  # Добавляем только если есть чанки
                    all_chunks.extend(chunks)
                else:
                    error_files.append(f"Не удалось извлечь текст: {file.filename}")
            finally:
                os.unlink(tmp_path)

        except Exception as e:
            error_files.append(f"Ошибка обработки {file.filename}: {str(e)}")
            continue

    if not all_chunks:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Не удалось извлечь текст ни из одного файла",
                "errors": error_files
            }
        )

    try:
        temp_db = VectorDB(client=client)
        temp_db.set_chunks(all_chunks)
        temp_db.build_faiss_index()

        chats[chat_id].update({
            "chunks": all_chunks,
            "index": temp_db.index
        })

        return {
            "status": "success",
            "chat_id": chat_id,
            "files_uploaded": [f.filename for f in files],
            "total_chunks": len(all_chunks),
            "warnings": error_files if error_files else None
        }

    except Exception as e:
        logger.error(f"Ошибка индексирования: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка индексирования: {str(e)}")
        

@app.post("/chat")
async def chat_endpoint(question: dict):
    chat_id = question.get("chat_id")
    if not chat_id or chat_id not in chats:
        raise HTTPException(
            status_code=404,
            detail="Неверный идентификатор чата"
        )

    user_question = question.get("question", "").strip()
    if not user_question:
        raise HTTPException(
            status_code=400,
            detail="Вопрос не может быть пустым"
        )

    chat_data = chats[chat_id]
    if not chat_data["index"]:
        raise HTTPException(
            status_code=400,
            detail="Документы не загружены для этого чата"
        )

    try:
        temp_db = VectorDB(client=client)
        temp_db.index = chat_data["index"]
        temp_db.chunks = chat_data["chunks"]

        context = "\n---\n".join(
            temp_db.search_similar_chunks(user_question)
        )

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{
                "role": "system",
                "content": "Ты ассистент, отвечающий на вопросы по документам."
            }, {
                "role": "user",
                "content": f"Контекст:\n{context}\n\nВопрос: {user_question}"
            }],
            temperature=0.3
        )

        return {
            "answer": response.choices[0].message.content
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка генерации ответа: {str(e)}"
        )



@app.api_route("/chat/new", methods=["GET", "POST"])
def create_new_chat():
    if request.method not in ["POST", "GET"]:
        return JSONResponse(
            status_code=405,
            content={"detail": "Method Not Allowed"},
            headers={"Allow": "POST, GET"}
        )
    
    chat_id = str(uuid4())
    chats[chat_id] = {
        "chunks": [],
        "index": None,
        "client": client
    }
    return {"chat_id": chat_id}

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "total_chats": len(chats)
    }