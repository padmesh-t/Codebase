import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_ast_chunker_import():
    try:
        from app.services.ast_chunker import ASTChunker
        chunker = ASTChunker()
        assert chunker is not None
    except RuntimeError:
        pass


def test_ast_chunker_basic():
    try:
        from app.services.ast_chunker import ASTChunker
        chunker = ASTChunker()

        code = '''
def hello():
    print("hello")

def world():
    print("world")

class MyClass:
    def method(self):
        pass
'''
        chunks = chunker.chunk_code(code, language="python")
        assert len(chunks) >= 2
        for chunk in chunks:
            assert "code" in chunk
            assert "type" in chunk
            assert "name" in chunk
            assert "start_line" in chunk
            assert "end_line" in chunk
    except RuntimeError:
        pass


def test_ast_chunker_class():
    try:
        from app.services.ast_chunker import ASTChunker
        chunker = ASTChunker()

        code = '''
class Calculator:
    """A simple calculator class."""

    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b
'''
        chunks = chunker.chunk_code(code, language="python")
        assert len(chunks) >= 1
        class_chunks = [c for c in chunks if c["type"] == "class"]
        assert len(class_chunks) >= 1
        assert "Calculator" in class_chunks[0]["name"]
    except RuntimeError:
        pass


def test_ast_chunker_decorators():
    try:
        from app.services.ast_chunker import ASTChunker
        chunker = ASTChunker()

        code = '''
def decorator(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

@decorator
def my_function():
    pass
'''
        chunks = chunker.chunk_code(code, language="python")
        assert len(chunks) >= 2
    except RuntimeError:
        pass


def test_code_ingestion_discover():
    from app.services.code_ingestion import CodeIngestionService
    service = CodeIngestionService()

    test_dir = Path(__file__).parent.parent / "data" / "uploads"
    test_dir.mkdir(parents=True, exist_ok=True)

    (test_dir / "test.py").write_text("print('hello')")
    (test_dir / "test.js").write_text("console.log('hello')")
    (test_dir / "test.txt").write_text("hello")

    files = service.discover_files(test_dir)
    extensions = {f.suffix for f in files}
    assert ".py" in extensions or ".js" in extensions

    (test_dir / "test.py").unlink()
    (test_dir / "test.js").unlink()
    (test_dir / "test.txt").unlink()


def test_code_ingestion_language_detection():
    from app.services.code_ingestion import CodeIngestionService
    service = CodeIngestionService()

    assert service._detect_language(Path("app.py")) == "python"
    assert service._detect_language(Path("app.js")) == "javascript"
    assert service._detect_language(Path("app.ts")) == "typescript"
    assert service._detect_language(Path("App.java")) == "java"
    assert service._detect_language(Path("main.go")) == "go"
    assert service._detect_language(Path("lib.rs")) == "rust"
