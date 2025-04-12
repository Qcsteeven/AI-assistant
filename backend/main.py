from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from backend.app import VectorBackend  # Импорт вашего класса
import os

app = FastAPI()
backend = VectorBackend()

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Эндпоинт для загрузки файлов"""
    try:
        # Проверка расширения файла
        if not file.filename.lower().endswith('.docx'):
            raise HTTPException(400, "Разрешены только .docx файлы")
        
        # Создаем папку data, если ее нет
        os.makedirs("/app/data", exist_ok=True)
        file_path = f"/app/data/{file.filename}"
        
        # Сохраняем файл
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Обработка документа
        chunks = backend.load_docx_chunks(file_path)
        backend.build_faiss_index(chunks)
        
        return {
            "status": "success",
            "filename": file.filename,
            "chunks": len(chunks)
        }
        
    except Exception as e:
        raise HTTPException(500, f"Ошибка обработки файла: {str(e)}")

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/chat")
async def chat_endpoint(question: dict):
    if not backend.index:
        raise HTTPException(400, "Документ не загружен")
    
    try:
        top_chunks = backend.search_similar_chunks(question.get("question", ""))
        context = "\n---\n".join(top_chunks)
        
        response = backend.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{
                "role": "user",
                "content": f"Ответь на вопрос на основе контекста:\n{context}\n\nВопрос: {question.get('question', '')}\nОтвет:"
            }]
        )
        
        return {"answer": response.choices[0].message.content}
    except Exception as e:
        raise HTTPException(500, f"Ошибка обработки запроса: {str(e)}")