import asyncio
import json
import operator
from typing import Annotated, TypedDict

from langgraph.graph import StateGraph, START, END

from app.config import settings
from app.logging_config import get_logger
from app.models import Finding, Severity
from app.agents.security_agent import security_agent
from app.agents.performance_agent import performance_agent
from app.agents.architecture_agent import architecture_agent
from app.agents.testing_agent import testing_agent
from app.agents.moderator_agent import moderator_agent
from app.services.vector_store import vector_store_service

logger = get_logger("debate_engine")


class AgentState(TypedDict):
    project_id: str
    codebase_summary: str
    round_num: int
    findings: Annotated[list[dict], operator.add]
    challenges: list[dict]
    revisions: Annotated[list[dict], operator.add]
    debate_messages: Annotated[list[dict], operator.add]
    report: dict | None
    agents_analyzed: int


AGENTS = [
    ("security", security_agent),
    ("performance", performance_agent),
    ("architecture", architecture_agent),
    ("testing", testing_agent),
]


def _llm_generate(prompt: str) -> str:
    import httpx
    api_key = settings.OPENROUTER_API_KEY.strip() if settings.OPENROUTER_API_KEY else ""
    if not api_key:
        return '{"error": "No API key configured"}'

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://codebase-intelligence.local",
        "X-Title": "Codebase Intelligence",
    }
    payload = {
        "model": settings.OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": settings.LLM_TEMPERATURE,
        "max_tokens": settings.LLM_MAX_TOKENS,
    }
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{settings.OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return f'{{"error": "LLM call failed: {str(e)[:100]}"}}'


def _retrieve_and_analyze(agent_name: str, agent, task: str, state: AgentState) -> dict:
    queries = agent.get_retrieval_queries()
    all_context = []
    for q in queries:
        try:
            ctx = agent.retrieve_context(q, state["project_id"], top_k=5)
            all_context.append(ctx)
        except Exception:
            continue

    context = "\n\n---\n\n".join(all_context[:3])
    if not context.strip():
        context = "No relevant code context found."

    prompt = agent._build_prompt(task, context)
    result = _llm_generate(prompt)

    findings = _parse_findings(result, agent_name)

    message = {
        "agent": agent.name,
        "phase": "opening",
        "round_num": state["round_num"],
        "content": result,
        "findings": findings,
    }

    return {
        "findings": findings,
        "debate_messages": [message],
        "agents_analyzed": state.get("agents_analyzed", 0) + 1,
    }


def _challenge_agent(agent_name: str, agent, other_findings: list[dict], state: AgentState) -> dict:
    if not other_findings:
        return {"challenges": [], "debate_messages": []}

    other_finding = other_findings[0] if other_findings else {}
    other_finding_text = json.dumps(other_finding, indent=2)

    try:
        ctx = agent.retrieve_context(
            other_finding.get("title", ""), state["project_id"], top_k=5
        )
    except Exception:
        ctx = "No context available."

    task = (
        f"You are reviewing a finding by the {other_finding.get('agent', 'unknown')}.\n\n"
        f"THEIR FINDING:\n{other_finding_text}\n\n"
        f"YOUR TASK:\n"
        f"1. Evaluate: Is this a real issue? Is the severity accurate?\n"
        f"2. Provide counter-evidence from the code context if you disagree\n"
        f"3. If valid, acknowledge and suggest if priority should change\n"
        f"4. If invalid, explain why with code evidence\n\n"
        f"Respond in JSON format with fields: "
        f'"challenge_valid" (bool), "severity_assessment" (string), '
        f'"counter_evidence" (list[string]), "revised_severity" (string), "reasoning" (string)'
    )
    prompt = agent._build_prompt(task, ctx)
    result = _llm_generate(prompt)

    challenge = {
        "challenging_agent": agent.name,
        "target_agent": other_finding.get("agent", "unknown"),
        "target_finding": other_finding.get("title", ""),
        "result": result,
    }

    message = {
        "agent": agent.name,
        "phase": "challenge",
        "round_num": state["round_num"],
        "content": result,
        "findings": [],
    }

    return {
        "challenges": [challenge],
        "debate_messages": [message],
    }


def _revision_agent(agent_name: str, agent, challenges_against: list[dict], state: AgentState) -> dict:
    if not challenges_against:
        return {"revisions": [], "debate_messages": []}

    challenge_text = json.dumps(challenges_against, indent=2)

    task = (
        f"You received challenges against your findings:\n{challenge_text}\n\n"
        f"Review the challenges and provide your final position:\n"
        f"1. Accept valid challenges and revise your findings\n"
        f"2. Defend your findings with additional evidence if the challenge is weak\n"
        f"3. Provide your revised assessment\n\n"
        f"Respond in JSON with fields: "
        f'"revised_findings" (list[Finding]), "accepted_challenges" (list[string]), '
        f'"defended_findings" (list[string])'
    )

    try:
        ctx = agent.retrieve_context(challenge_text[:200], state["project_id"], top_k=5)
    except Exception:
        ctx = "No context available."

    prompt = agent._build_prompt(task, ctx)
    result = _llm_generate(prompt)

    message = {
        "agent": agent.name,
        "phase": "revision",
        "round_num": state["round_num"],
        "content": result,
        "findings": [],
    }

    return {
        "revisions": [{"agent": agent.name, "result": result}],
        "debate_messages": [message],
    }


def _parse_findings(result: str, agent_name: str) -> list[dict]:
    try:
        if "```json" in result:
            json_str = result.split("```json")[1].split("```")[0]
        elif "```" in result:
            json_str = result.split("```")[1].split("```")[0]
        else:
            json_str = result

        parsed = json.loads(json_str)
        findings = []

        if isinstance(parsed, list):
            for item in parsed:
                normalized = _normalize_finding(item, agent_name)
                if normalized:
                    findings.append(normalized)
        elif isinstance(parsed, dict):
            if "findings" in parsed:
                for item in parsed["findings"]:
                    normalized = _normalize_finding(item, agent_name)
                    if normalized:
                        findings.append(normalized)
            elif "issues" in parsed:
                for item in parsed["issues"]:
                    normalized = _normalize_finding(item, agent_name)
                    if normalized:
                        findings.append(normalized)
            else:
                normalized = _normalize_finding(parsed, agent_name)
                if normalized:
                    findings.append(normalized)

        return findings[:settings.MAX_FINDINGS_PER_AGENT]
    except Exception as e:
        logger.warning(f"Failed to parse findings for {agent_name}: {e}")
        clean_text = _extract_clean_text(result)
        if clean_text:
            return [{
                "agent": agent_name,
                "category": agent_name,
                "severity": "medium",
                "title": f"Analysis by {agent_name}",
                "description": clean_text,
                "evidence": [],
                "confidence": 0.5,
            }]
        return []


def _extract_clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    if text.startswith("{") or text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                for key in ["description", "detail", "details", "explanation", "text", "body", "summary", "message"]:
                    if key in parsed and isinstance(parsed[key], str):
                        return parsed[key]
                if "issues" in parsed and isinstance(parsed["issues"], list) and parsed["issues"]:
                    return _extract_clean_text(json.dumps(parsed["issues"][0]))
                return json.dumps(parsed, indent=2)
            elif isinstance(parsed, list) and parsed:
                return _extract_clean_text(json.dumps(parsed[0]))
        except json.JSONDecodeError:
            pass
    lines = text.split("\n")
    clean_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("{") or line.startswith("}") or line.startswith("[") or line.startswith("]"):
            continue
        if line.startswith('"') and line.endswith('"'):
            line = line[1:-1]
        if ":" in line and len(line.split(":")[0]) < 30:
            parts = line.split(":", 1)
            key = parts[0].strip().strip('"')
            value = parts[1].strip().strip('"').strip(",")
            if key in ["severity", "confidence", "file", "lines", "type"]:
                continue
            if value:
                clean_lines.append(value)
        else:
            clean_lines.append(line)
    return " ".join(clean_lines) if clean_lines else text[:500]


def _normalize_finding(item: dict, agent_name: str) -> dict | None:
    if not isinstance(item, dict):
        return None

    severity = str(item.get("severity", "medium")).lower()
    severity_map = {
        "high": "high", "medium": "medium", "low": "low", "critical": "critical",
        "1": "critical", "2": "high", "3": "medium", "4": "low",
        "high priority": "high", "medium priority": "medium", "low priority": "low",
    }
    severity = severity_map.get(severity, "medium")

    title = (
        item.get("title")
        or item.get("issue")
        or item.get("name")
        or item.get("finding")
        or item.get("problem")
        or item.get("summary")
    )
    if not title:
        return None

    title = str(title).strip()
    if title.startswith("{") or title.startswith("["):
        clean = _extract_clean_text(title)
        if clean:
            title = clean[:200]
        else:
            title = f"Issue found by {agent_name}"

    description = (
        item.get("description")
        or item.get("detail")
        or item.get("details")
        or item.get("explanation")
        or item.get("text")
        or item.get("body")
        or ""
    )
    if isinstance(description, dict):
        for key in ["text", "description", "detail", "explanation", "body", "summary"]:
            if key in description and isinstance(description[key], str):
                description = description[key]
                break
        else:
            description = json.dumps(description, indent=2)
    elif isinstance(description, list):
        description = " ".join(str(d) for d in description)

    description = str(description).strip()
    if description.startswith("{") or description.startswith("["):
        clean = _extract_clean_text(description)
        if clean:
            description = clean

    if not description or len(description) < 10:
        return None

    evidence = item.get("evidence") or item.get("code_evidence") or item.get("code") or []
    if isinstance(evidence, str):
        evidence = [evidence]
    elif isinstance(evidence, list):
        clean_evidence = []
        for e in evidence:
            if isinstance(e, dict):
                file_path = e.get("file", e.get("file_path", ""))
                lines = e.get("lines", [])
                if file_path:
                    if lines:
                        clean_evidence.append(f"{file_path}:{lines}")
                    else:
                        clean_evidence.append(str(file_path))
            else:
                clean_evidence.append(str(e))
        evidence = clean_evidence

    file_path = item.get("file_path") or item.get("file") or item.get("location") or None
    if isinstance(file_path, dict):
        file_path = file_path.get("file") or file_path.get("path") or str(file_path)

    line_number = item.get("line_number") or item.get("line") or None
    if isinstance(line_number, list) and line_number:
        line_number = line_number[0]

    confidence = item.get("confidence", 0.5)
    try:
        confidence = float(confidence)
    except (ValueError, TypeError):
        confidence = 0.5
    if confidence > 1:
        confidence = confidence / 100

    return {
        "agent": agent_name,
        "category": agent_name,
        "severity": severity,
        "title": str(title)[:200],
        "description": str(description),
        "evidence": evidence,
        "confidence": confidence,
        "file_path": file_path,
        "line_number": line_number,
    }


def _build_agent_nodes():
    nodes = {}
    for agent_key, agent in AGENTS:

        def make_opening(ak, ag):
            def node(state: AgentState) -> dict:
                task = (
                    f"Analyze this codebase for {ak} issues.\n"
                    f"Identify the top {settings.MAX_FINDINGS_PER_AGENT} issues.\n"
                    f"For each issue provide: severity, title, description, "
                    f"evidence (file paths + line numbers), confidence.\n"
                    f"Respond in JSON format."
                )
                return _retrieve_and_analyze(ak, ag, task, state)
            return node

        def make_challenge(ak, ag):
            def node(state: AgentState) -> dict:
                other_findings = [
                    f for f in state.get("findings", [])
                    if f.get("agent") != ag.name
                ]
                return _challenge_agent(ak, ag, other_findings[:2], state)
            return node

        def make_revision(ak, ag):
            def node(state: AgentState) -> dict:
                challenges_against = [
                    c for c in state.get("challenges", [])
                    if c.get("target_agent") == ag.name
                ]
                return _revision_agent(ak, ag, challenges_against, state)
            return node

        nodes[f"{agent_key}_opening"] = make_opening(agent_key, agent)
        nodes[f"{agent_key}_challenge"] = make_challenge(agent_key, agent)
        nodes[f"{agent_key}_revision"] = make_revision(agent_key, agent)

    return nodes


def _moderator_node(state: AgentState) -> dict:
    debate_history = json.dumps(state.get("debate_messages", []), indent=2, default=str)
    all_findings = json.dumps(state.get("findings", []), indent=2, default=str)

    prompt = (
        f"{moderator_agent.system_prompt}\n\n"
        f"DEBATE HISTORY:\n{debate_history}\n\n"
        f"ALL FINDINGS FROM AGENTS:\n{all_findings}\n\n"
        f"Generate the consensus report in JSON format with fields:\n"
        f'"executive_summary" (string),\n'
        f'"overall_score" (int 1-10),\n'
        f'"confidence" (float 0.0-1.0),\n'
        f'"critical_issues" (list[Finding]),\n'
        f'"high_issues" (list[Finding]),\n'
        f'"medium_issues" (list[Finding]),\n'
        f'"low_issues" (list[Finding]),\n'
        f'"positive_observations" (list[string]),\n'
        f'"agent_summary" (dict mapping agent name to their key takeaway)'
    )
    result = _llm_generate(prompt)

    report = _parse_report(result, state)
    return {"report": report, "debate_messages": [{
        "agent": "Moderator",
        "phase": "synthesis",
        "round_num": state["round_num"],
        "content": result,
        "findings": [],
    }]}


def _parse_report(result: str, state: AgentState) -> dict:
    try:
        if "```json" in result:
            json_str = result.split("```json")[1].split("```")[0]
        elif "```" in result:
            json_str = result.split("```")[1].split("```")[0]
        else:
            json_str = result
        report = json.loads(json_str)

        for key in ["critical_issues", "high_issues", "medium_issues", "low_issues"]:
            if key in report and isinstance(report[key], list):
                report[key] = [_normalize_finding(f, f.get("agent", "moderator")) for f in report[key]]

        return report
    except Exception:
        all_findings = state.get("findings", [])
        critical = [f for f in all_findings if f.get("severity") == "critical"]
        high = [f for f in all_findings if f.get("severity") == "high"]
        medium = [f for f in all_findings if f.get("severity") == "medium"]
        low = [f for f in all_findings if f.get("severity") == "low"]

        score = max(1, 10 - len(critical) * 2 - len(high) * 1)
        return {
            "executive_summary": f"Analysis complete. Found {len(all_findings)} issues across 4 categories.",
            "overall_score": score,
            "confidence": 0.6,
            "critical_issues": critical,
            "high_issues": high,
            "medium_issues": medium,
            "low_issues": low,
            "positive_observations": [],
            "agent_summary": {},
        }


def _should_continue(state: AgentState) -> str:
    return "continue"


def build_debate_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    nodes = _build_agent_nodes()
    for name, node_fn in nodes.items():
        workflow.add_node(name, node_fn)

    workflow.add_node("moderator", _moderator_node)

    workflow.add_edge(START, "security_opening")
    workflow.add_edge("security_opening", "performance_opening")
    workflow.add_edge("performance_opening", "architecture_opening")
    workflow.add_edge("architecture_opening", "testing_opening")

    workflow.add_edge("testing_opening", "security_challenge")
    workflow.add_edge("security_challenge", "performance_challenge")
    workflow.add_edge("performance_challenge", "architecture_challenge")
    workflow.add_edge("architecture_challenge", "testing_challenge")

    workflow.add_edge("testing_challenge", "security_revision")
    workflow.add_edge("security_revision", "performance_revision")
    workflow.add_edge("performance_revision", "architecture_revision")
    workflow.add_edge("architecture_revision", "testing_revision")

    workflow.add_edge("testing_revision", "moderator")
    workflow.add_edge("moderator", END)

    return workflow


class DebateEngine:
    def __init__(self):
        self._app = None

    def _get_app(self):
        if self._app is None:
            graph = build_debate_graph()
            self._app = graph.compile()
        return self._app

    async def run(self, project_id: str, chunks: list, project_data: dict) -> dict:
        file_count = len(set(c.metadata.get("file_path", "") for c in chunks))
        codebase_summary = (
            f"Project with {file_count} files and {len(chunks)} code chunks. "
            f"Languages: {', '.join(set(c.metadata.get('language', 'unknown') for c in chunks))}"
        )

        initial_state = {
            "project_id": project_id,
            "codebase_summary": codebase_summary,
            "round_num": 1,
            "findings": [],
            "challenges": [],
            "revisions": [],
            "debate_messages": [],
            "report": None,
            "agents_analyzed": 0,
        }

        app = self._get_app()
        result = await asyncio.to_thread(app.invoke, initial_state)

        return {
            "findings": result.get("findings", []),
            "debate_messages": result.get("debate_messages", []),
            "report": result.get("report", {}),
        }


debate_engine = DebateEngine()
