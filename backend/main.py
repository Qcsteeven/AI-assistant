# backend/main.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Tuple
from backend.document_loader import DocumentLoader
from backend.vector_db import VectorDB
import os
import tempfile
import asyncio

app = FastAPI()
loader = DocumentLoader()
db = VectorDB()

# CORS middleware
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


async def generate_response(prompt: str, model: str = "gpt-4", temperature: float = 0.3) -> str:
    """Генерация ответа с помощью LLM."""
    response = db.client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature
    )
    return response.choices[0].message.content.strip()


async def generate_critique(answer: str, context: str, question: str) -> Tuple[str, str]:
    """Генерация критики ответа с надежным извлечением улучшенной версии."""
    critique_prompt = f"""
    Ты - строгий критик ответов. Проверь следующий ответ по критериям:
    1. Точность (соответствие контексту)
    2. Полнота (охват всех аспектов вопроса)
    3. Логичность (отсутствие противоречий)
    4. Ясность (понятность изложения)

    Контекст:
    {context}

    Вопрос: {question}

    Ответ для проверки:
    {answer}

    Сформируй свой ответ в следующем строгом формате:

    ### Вердикт:
    [Краткая оценка качества ответа]

    ### Замечания:
    - [Конкретное замечание 1]
    - [Конкретное замечание 2]
    - ...

    ### Улучшенный ответ:
    [Полный текст улучшенного ответа здесь]
    """

    critique = await generate_response(critique_prompt, temperature=0.7)

    # Надежное извлечение улучшенного ответа
    improved_answer = extract_improved_answer(critique, answer)

    return critique, improved_answer


def extract_improved_answer(critique: str, fallback_answer: str) -> str:
    """Извлекает улучшенный ответ из критики с несколькими уровнями резервирования."""
    # 1. Пытаемся найти по строгому разделителю
    if "### Улучшенный ответ:" in critique:
        parts = critique.split("### Улучшенный ответ:")
        if len(parts) > 1:
            improved = parts[1].split("###")[0].strip()  # Берем текст до следующего заголовка
            if improved:
                return improved

    # 2. Пробуем альтернативные варианты разделителей
    for marker in ["Улучшенный ответ:", "Исправленный ответ:", "Оптимизированный ответ:"]:
        if marker in critique:
            parts = critique.split(marker)
            if len(parts) > 1:
                improved = parts[1].strip()
                # Удаляем возможные последующие заголовки
                improved = improved.split("\n\n")[0].split("###")[0].strip()
                if improved:
                    return improved

    # 3. Пытаемся найти последний значительный блок текста
    paragraphs = [p.strip() for p in critique.split("\n\n") if p.strip()]
    if len(paragraphs) > 1:
        last_paragraph = paragraphs[-1]
        # Проверяем, что это похоже на ответ (а не на замечание)
        if (len(last_paragraph.split()) > 5 and
                not last_paragraph.startswith(("###", "- ", "* "))):
            return last_paragraph

    # 4. Если ничего не найдено, возвращаем исходный ответ
    return fallback_answer


async def deep_think_process(context: str, question: str) -> dict:
    """Процесс DeepThink с генерацией и проверкой ответа."""
    # Основной промпт для генератора
    generator_prompt = f"""
    Ты - ассистент, отвечающий на вопросы строго на основе предоставленных документов.
    Контекст:
    {context}

    Вопрос: {question}

    Сформулируй ответ, который:
    1. Точно соответствует информации из контекста
    2. Полностью раскрывает вопрос
    3. Изложен четко и структурированно
    4. Содержит только проверяемые факты
    """

    # Генерируем первоначальный ответ
    initial_answer = await generate_response(generator_prompt)

    # Получаем критику и улучшенный ответ
    critique, final_answer = await generate_critique(initial_answer, context, question)

    return {
        "initial_answer": initial_answer,
        "critique": critique,
        "final_answer": final_answer,
        "context_snippets": context.split('\n---\n')[:3]  # Возвращаем первые 3 чанка для отладки
    }


@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Загрузка и обработка файлов."""
    all_chunks = []

    try:
        for file in files:
            ext = os.path.splitext(file.filename)[-1].lower()

            if ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(status_code=400, detail=f"Файл '{file.filename}' имеет неподдерживаемое расширение")

            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(await file.read())
                file_path = tmp.name

            load_method = ALLOWED_EXTENSIONS[ext]
            chunks = load_method(file_path)
            all_chunks.extend(chunks)

            os.unlink(file_path)

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
    """Обработка вопросов с возможностью DeepThink."""
    if not db.index:
        raise HTTPException(status_code=400, detail="Документы не загружены")

    user_question = question.get("question", "").strip()
    if not user_question:
        raise HTTPException(status_code=400, detail="Вопрос не должен быть пустым")

    deep_think = question.get("deep_think", False)

    try:
        top_k = 7 if deep_think else 5
        top_chunks = db.search_similar_chunks(user_question, k=top_k)
        context = "\n---\n".join(top_chunks)

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
            prompt = f"""
            Ответь на вопрос строго на основе предоставленного контекста.
            Контекст:
            {context}

            Вопрос: {user_question}

            Ответ должен быть:
            - Точно соответствовать контексту
            - Содержать только факты из документов
            - Быть кратким и информативным
            """

            answer = await generate_response(prompt)
            return {
                "status": "success",
                "mode": "standard",
                "answer": answer,
                "context_snippets": context.split('\n---\n')[:2]
            }

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=f"Ошибка обработки запроса: {str(e)}")


@app.get("/health")
def health_check():
    """Проверка статуса сервиса."""
    return {
        "status": "ok",
        "index_ready": db.index is not None,
        "chunks_loaded": len(db.chunks) if db.chunks else 0
    }
