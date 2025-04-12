from .app import VectorBackend

def cli_main():
    """Старая консольная версия (для тестов)"""
    app = VectorBackend()
    chunks = app.load_first_docx()
    index, _ = app.build_faiss_index(chunks)
    app.chat()

if __name__ == "__main__":
    cli_main()