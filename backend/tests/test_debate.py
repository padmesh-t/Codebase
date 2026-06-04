import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_debate_graph_builds():
    from app.chains.debate_engine import build_debate_graph
    graph = build_debate_graph()
    app = graph.compile()
    assert app is not None


def test_debate_graph_nodes():
    from app.chains.debate_engine import build_debate_graph
    graph = build_debate_graph()

    expected_nodes = [
        "security_opening", "performance_opening",
        "architecture_opening", "testing_opening",
        "security_challenge", "performance_challenge",
        "architecture_challenge", "testing_challenge",
        "security_revision", "performance_revision",
        "architecture_revision", "testing_revision",
        "moderator",
    ]

    for node in expected_nodes:
        assert node in graph.nodes, f"Missing node: {node}"


def test_agent_retrieval_queries():
    from app.agents.security_agent import security_agent
    from app.agents.performance_agent import performance_agent
    from app.agents.architecture_agent import architecture_agent
    from app.agents.testing_agent import testing_agent

    for agent in [security_agent, performance_agent, architecture_agent, testing_agent]:
        queries = agent.get_retrieval_queries()
        assert len(queries) > 0
        assert all(isinstance(q, str) for q in queries)


def test_agent_system_prompts():
    from app.agents.security_agent import security_agent
    from app.agents.performance_agent import performance_agent
    from app.agents.architecture_agent import architecture_agent
    from app.agents.testing_agent import testing_agent

    for agent in [security_agent, performance_agent, architecture_agent, testing_agent]:
        assert len(agent.system_prompt) > 100
        assert agent.name is not None
        assert agent.role is not None


def test_moderator_agent():
    from app.agents.moderator_agent import moderator_agent
    assert moderator_agent.name == "Debate Moderator"
    assert len(moderator_agent.system_prompt) > 100
