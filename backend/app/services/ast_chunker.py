from app.logging_config import get_logger

logger = get_logger("ast_chunker")

try:
    import tree_sitter_python as tspython
    from tree_sitter import Language, Parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    logger.warning("tree-sitter not available, AST chunking disabled")


class ASTChunker:
    def __init__(self):
        if not TREE_SITTER_AVAILABLE:
            raise RuntimeError("tree-sitter is not installed")
        self._parsers = {}
        self._languages = {}

    def _get_parser(self, language: str) -> tuple[Parser, Language]:
        if language not in self._parsers:
            if language == "python":
                lang = Language(tspython.language())
            else:
                raise ValueError(f"Unsupported AST language: {language}")
            parser = Parser(lang)
            self._parsers[language] = parser
            self._languages[language] = lang
        return self._parsers[language], self._languages[language]

    def chunk_code(self, source_code: str, language: str = "python") -> list[dict]:
        parser, lang = self._get_parser(language)
        tree = parser.parse(bytes(source_code, "utf8"))

        chunks = []
        lines = source_code.split("\n")

        for node in tree.root_node.children:
            node_type = node.type
            if node_type in (
                "function_definition",
                "class_definition",
                "decorated_definition",
            ):
                chunk = self._extract_chunk(source_code, lines, node, node_type)
                if chunk:
                    chunks.append(chunk)

        if not chunks:
            chunks.append({
                "code": source_code,
                "type": "module",
                "name": "",
                "start_line": 1,
                "end_line": len(lines),
            })

        return chunks

    def _extract_chunk(
        self, source_code: str, lines: list[str], node, node_type: str
    ) -> dict | None:
        start_line = node.start_point[0]
        end_line = node.end_point[0]

        code_lines = lines[start_line:end_line + 1]
        code = "\n".join(code_lines)

        if not code.strip():
            return None

        name = self._get_node_name(node, lines)

        chunk_type = "function"
        if node_type == "class_definition":
            chunk_type = "class"
        elif node_type == "decorated_definition":
            for child in node.children:
                if child.type == "class_definition":
                    chunk_type = "class"
                    break
                elif child.type == "function_definition":
                    chunk_type = "function"
                    break

        return {
            "code": code,
            "type": chunk_type,
            "name": name,
            "start_line": start_line + 1,
            "end_line": end_line + 1,
        }

    def _get_node_name(self, node, lines: list[str]) -> str:
        for child in node.children:
            if child.type == "identifier":
                return lines[child.start_point[0]][child.start_point[1]:child.end_point[1]]
            if child.type == "attribute":
                return lines[child.start_point[0]][child.start_point[1]:child.end_point[1]]
        return ""


ast_chunker = ASTChunker() if TREE_SITTER_AVAILABLE else None
