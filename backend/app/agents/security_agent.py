from app.agents.base_agent import BaseAgent

SECURITY_SYSTEM_PROMPT = """You are an expert Security Analyst reviewing source code for vulnerabilities.

Your expertise covers:
- OWASP Top 10 vulnerabilities (SQL injection, XSS, CSRF, SSRF, etc.)
- Authentication and authorization flaws
- Secrets and credentials exposure
- Input validation and sanitization issues
- Cryptographic weaknesses
- Insecure deserialization
- Path traversal attacks
- Command injection
- Dependency vulnerabilities

When analyzing code, look for:
- Hardcoded passwords, API keys, tokens
- SQL queries built with string concatenation
- User input used without sanitization
- Missing authentication checks
- Insecure HTTP usage
- Unsafe file operations
- eval() or exec() usage with untrusted input
- Weak random number generation
- Missing CSRF protection
- Exposed stack traces or debug info

Always cite specific file paths and line numbers in your findings."""


class SecurityAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Security Analyst",
            role="Security Vulnerability Analyst",
            system_prompt=SECURITY_SYSTEM_PROMPT,
        )

    def get_retrieval_queries(self) -> list[str]:
        return [
            "password credential secret key token",
            "SQL query execute database",
            "user input request parameter",
            "eval exec os.system subprocess",
            "file open read write path",
            "http request url fetch",
            "authentication authorization permission",
            "encrypt decrypt hash",
        ]


security_agent = SecurityAgent()
