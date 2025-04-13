ИИ-Асисстент для продукт-менеджеров 

## 🚀 Быстрый старт

### Предварительные требования
- Docker 20.10+
- Docker Compose 2.0+
- API ключ OpenAI

### Установка
1. Склонируйте репозиторий командой `git clone https://github.com/Qcsteeven/AI-assistant.git`
2. Создайте файл `.env` в корне проекта:
   ```ini
   OPENAI_API_KEY="your_openai_api_key_here"
   ```
   Вместо `your_openai_api_key_here` напишите свой openai ключ

### Запуск
```bash
# Сборка и запуск
docker-compose up --build 
```

[**Запустить приложение локально**](http://localhost:3000) (после выполнения шагов установки и запуска)
