from app.logging_config import get_logger
from app.services.vector_store import vector_store_service

logger = get_logger("base_agent")


class BaseAgent:
    def __init__(self, name: str, role: str, system_prompt: str):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt

    def retrieve_context(self, query: str, project_id: str, top_k: int = 10) -> str:
        try:
            results = vector_store_service.similarity_search(query, project_id, top_k)
            return self._format_context(results)
        except Exception as e:
            logger.warning(f"Retrieval failed for {self.name}: {e}")
            return "No context available."

    def _format_context(self, results: list) -> str:
        if not results:
            return "No context available."
        parts = []
        for i, (doc, score) in enumerate(results):
            meta = doc.metadata
            file_path = meta.get("file_path", "unknown")
            line_range = meta.get("line_range", "")
            name = meta.get("name", "")
            relevance = 1 - score

            header = f"[{i+1}] {file_path}"
            if name:
                header += f" :: {name}"
            if line_range:
                header += f" (lines {line_range})"
            header += f" [relevance: {relevance:.2f}]"

            parts.append(f"{header}\n{doc.page_content}")
        return "\n\n---\n\n".join(parts)

    def _build_prompt(self, task: str, context: str, extra_instructions: str = "") -> str:
        parts = [
            self.system_prompt,
            "",
            f"YOUR ROLE: {self.role}",
            "",
        ]
        if extra_instructions:
            parts.append(extra_instructions)
            parts.append("")
        parts.extend([
            "RELEVANT CODE CONTEXT:",
            context,
            "",
            "TASK:",
            task,
            "",
            "Respond in the exact JSON format requested. Be specific with file paths and line numbers.",
        ])
        return "\n".join(parts)
