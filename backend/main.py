from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Tuple
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


def extract_improved_answer(critique: str, fallback_answer: str) -> str:
    if "### Улучшенный ответ:" in critique:
        parts = critique.split("### Улучшенный ответ:")
        if len(parts) > 1:
            improved = parts[1].split("###")[0].strip()
            if improved:
                return improved

    for marker in ["Улучшенный ответ:", "Исправленный ответ:", "Оптимизированный ответ:"]:
        if marker in critique:
            parts = critique.split(marker)
            if len(parts) > 1:
                improved = parts[1].strip().split("###")[0].strip()
                if improved:
                    return improved

    paragraphs = [p.strip() for p in critique.split("\n\n") if p.strip()]
    if len(paragraphs) > 1:
        last = paragraphs[-1]
        if len(last.split()) > 5 and not last.startswith(("###", "- ", "* ")):
            return last

    return fallback_answer


async def generate_response(prompt: str, model: str = "gpt-4", temperature: float = 0.3) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature
    )
    return response.choices[0].message.content.strip()


async def generate_critique(answer: str, context: str, question: str) -> Tuple[str, str]:
    critique_prompt = f"""
    Ты - строгий критик. Проанализируй ответ по критериям:
    1. Точность
    2. Полнота
    3. Логичность
    4. Ясность

    Контекст:
    {context}

    Вопрос: {question}

    Ответ:
    {answer}

    ### Вердикт:
    [Оценка]

    ### Замечания:
    - [Замечание 1]
    - ...

    ### Улучшенный ответ:
    [Новый ответ здесь]
    """
    critique = await generate_response(critique_prompt, temperature=0.7)
    improved = extract_improved_answer(critique, answer)
    return critique, improved


async def deep_think_process(context: str, question: str) -> dict:
    generator_prompt = f"""
    Ты - ассистент. Ответь на вопрос, строго опираясь на документы.

    Контекст:
    {context}

    Вопрос: {question}

    Ответ должен быть:
    1. Точный
    2. Полный
    3. Структурированный
    4. Проверяемый
    """
    initial_answer = await generate_response(generator_prompt)
    critique, final_answer = await generate_critique(initial_answer, context, question)
    return {
        "initial_answer": initial_answer,
        "critique": critique,
        "final_answer": final_answer,
        "context_snippets": context.split('\n---\n')[:3]
    }


@app.api_route("/chat/new", methods=["GET", "POST"])
def create_new_chat(request: Request):
    chat_id = str(uuid4())
    chats[chat_id] = {
        "chunks": [],
        "index": None,
        "client": client
    }
    logger.info(f"Создан новый чат: {chat_id}")
    return {"chat_id": chat_id}


@app.post("/upload")
async def upload_files(chat_id: str = Form(...), files: List[UploadFile] = File(...)):
    if chat_id not in chats:
        raise HTTPException(status_code=404, detail="Чат не найден")

    all_chunks, error_files = [], []

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
                if chunks:
                    all_chunks.extend(chunks)
                else:
                    error_files.append(f"Не удалось извлечь текст: {file.filename}")
            finally:
                os.unlink(tmp_path)

        except Exception as e:
            error_files.append(f"Ошибка: {file.filename} — {str(e)}")

    if not all_chunks:
        raise HTTPException(status_code=400, detail={"message": "Ничего не загружено", "errors": error_files})

    temp_db = VectorDB(client=client)
    temp_db.set_chunks(all_chunks)
    temp_db.build_faiss_index()

    chats[chat_id]["chunks"] = all_chunks
    chats[chat_id]["index"] = temp_db.index

    return {
        "status": "success",
        "chat_id": chat_id,
        "files_uploaded": [f.filename for f in files],
        "total_chunks": len(all_chunks),
        "warnings": error_files or None
    }


@app.post("/chat")
async def chat_endpoint(question: dict):
    chat_id = question.get("chat_id")
    if not chat_id or chat_id not in chats:
        raise HTTPException(status_code=404, detail="Неверный chat_id")

    user_question = question.get("question", "").strip()
    if not user_question:
        raise HTTPException(status_code=400, detail="Вопрос не может быть пустым")

    chat_data = chats[chat_id]
    if not chat_data["index"]:
        raise HTTPException(status_code=400, detail="Документы не загружены")

    temp_db = VectorDB(client=client)
    temp_db.index = chat_data["index"]
    temp_db.chunks = chat_data["chunks"]

    context = "\n---\n".join(temp_db.search_similar_chunks(user_question))

    deep_think = question.get("deep_think", False)
    if deep_think:
        result = await deep_think_process(context, user_question)
        return {
            "status": "success",
            "mode": "deep_think",
            "answer": result["final_answer"],
            "initial_answer": result["initial_answer"],
            "critique": result["critique"],
            "context_snippets": result["context_snippets"]
        }
    else:
        answer = await generate_response(f"""
        Контекст:
        {context}

        Вопрос: {user_question}

        Ответь кратко, точно, только по фактам из контекста.
        """)
        return {
            "status": "success",
            "mode": "standard",
            "answer": answer,
            "context_snippets": context.split("\n---\n")[:2]
        }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "total_chats": len(chats)
    }
