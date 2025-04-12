from backend.chat import VectorBackend

def main():
    app = VectorBackend()
    chunks = app.load_first_docx()  # Автозагрузка первого файла
    index, _ = app.build_faiss_index(chunks)
    app.chat()

if __name__ == "__main__":
    main()