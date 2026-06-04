import streamlit as st
import requests
import json
import time

API_BASE_URL = "http://localhost:8000"


def parse_content(content: str) -> str:
    """Parse JSON content and render as readable markdown."""
    if not content:
        return ""
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            parts = []
            for key, value in data.items():
                if value is None:
                    continue
                label = key.replace("_", " ").title()
                if isinstance(value, list):
                    items = []
                    for v in value:
                        if isinstance(v, dict):
                            item_parts = []
                            for k2, v2 in v.items():
                                if v2 is not None:
                                    item_parts.append(f"{k2}: {v2}")
                            items.append(" | ".join(item_parts))
                        else:
                            items.append(str(v))
                    parts.append(f"**{label}:**\n" + "\n".join(f"- {item}" for item in items))
                elif isinstance(value, dict):
                    sub_parts = []
                    for k2, v2 in value.items():
                        if v2 is not None:
                            sub_parts.append(f"**{k2.replace('_', ' ').title()}:** {v2}")
                    parts.append("\n".join(sub_parts))
                else:
                    parts.append(f"**{label}:** {value}")
            return "\n\n".join(parts)
        return str(data)
    except (json.JSONDecodeError, TypeError):
        cleaned = content.strip()
        if cleaned.startswith("{") or cleaned.startswith("["):
            try:
                data = json.loads(cleaned)
                return parse_content(json.dumps(data))
            except (json.JSONDecodeError, TypeError):
                pass
        return content


def format_finding_description(description: str) -> str:
    """Format a finding description for display."""
    if not description:
        return "No description available."
    try:
        data = json.loads(description)
        if isinstance(data, dict):
            parts = []
            for key, value in data.items():
                if value is None:
                    continue
                label = key.replace("_", " ").title()
                if isinstance(value, list):
                    items = []
                    for v in value:
                        if isinstance(v, dict):
                            item_parts = []
                            for k2, v2 in v.items():
                                if v2 is not None:
                                    item_parts.append(f"{k2}: {v2}")
                            items.append(" | ".join(item_parts))
                        else:
                            items.append(str(v))
                    parts.append(f"**{label}:**\n" + "\n".join(f"- {item}" for item in items))
                elif isinstance(value, dict):
                    sub_parts = []
                    for k2, v2 in value.items():
                        if v2 is not None:
                            sub_parts.append(f"**{k2.replace('_', ' ').title()}:** {v2}")
                    parts.append("\n".join(sub_parts))
                else:
                    parts.append(f"**{label}:** {value}")
            return "\n\n".join(parts)
        return str(data)
    except (json.JSONDecodeError, TypeError):
        pass
    cleaned = description.strip()
    if cleaned.startswith("{") or cleaned.startswith("["):
        try:
            data = json.loads(cleaned)
            return format_finding_description(json.dumps(data))
        except (json.JSONDecodeError, TypeError):
            pass
    return description

st.set_page_config(
    page_title="Codebase Intelligence",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 Codebase Intelligence")
st.markdown("*Multi-agent code review with debate-based consensus*")

if "active_tab" not in st.session_state:
    st.session_state.active_tab = "Analyze"

tab1, tab2, tab3, tab4 = st.tabs(["Analyze", "Report", "Debate", "Agent Perspectives"])

with tab1:
    st.header("Submit Codebase for Analysis")

    input_method = st.radio(
        "Input Method",
        ["Git URL", "Upload Archive"],
        horizontal=True,
    )

    git_url = None
    uploaded_file = None
    project_name = None

    if input_method == "Git URL":
        git_url = st.text_input("Git Repository URL", placeholder="https://github.com/user/repo.git")
        project_name = st.text_input("Project Name (optional)", placeholder="my-project")
    else:
        uploaded_file = st.file_uploader(
            "Upload project archive",
            type=["zip", "tar.gz", "tgz"],
            help="Upload a .zip or .tar.gz archive of your project",
        )

    if st.button("Start Analysis", type="primary"):
        if not git_url and not uploaded_file:
            st.error("Please provide a Git URL or upload a file.")
        else:
            with st.spinner("Submitting project..."):
                try:
                    if git_url:
                        resp = requests.post(
                            f"{API_BASE_URL}/analyze",
                            params={"git_url": git_url, "project_name": project_name},
                            timeout=600,
                        )
                    else:
                        files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                        resp = requests.post(
                            f"{API_BASE_URL}/analyze",
                            files=files,
                            timeout=600,
                        )

                    if resp.status_code == 200:
                        data = resp.json()
                        st.session_state.project_id = data["project_id"]
                        st.success(f"Analysis started! Project ID: {data['project_id']}")
                    else:
                        st.error(f"Error: {resp.json().get('error', 'Unknown error')}")
                except requests.exceptions.ConnectionError:
                    st.error("Cannot connect to backend. Make sure the API is running on port 8000.")
                except Exception as e:
                    st.error(f"Error: {e}")

    if "project_id" in st.session_state:
        st.divider()
        st.subheader("Analysis Progress")

        progress_bar = st.progress(0)
        status_text = st.empty()

        for _ in range(100):
            try:
                resp = requests.get(
                    f"{API_BASE_URL}/projects/{st.session_state.project_id}/status",
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    progress = data.get("progress_percent", 0)
                    status = data.get("status", "unknown")
                    progress_bar.progress(progress / 100)
                    status_text.text(f"Status: {status} ({progress}%)")

                    if status in ("completed", "failed"):
                        if status == "completed":
                            st.success("Analysis complete! Go to the Report tab.")
                        else:
                            st.error(f"Analysis failed: {data.get('error', 'Unknown')}")
                        break
                time.sleep(2)
            except Exception:
                break

with tab2:
    st.header("Consensus Report")

    if "project_id" in st.session_state:
        if st.button("Load Report"):
            with st.spinner("Loading report..."):
                try:
                    resp = requests.get(
                        f"{API_BASE_URL}/projects/{st.session_state.project_id}/report",
                        timeout=30,
                    )
                    if resp.status_code == 200:
                        report = resp.json()
                        st.session_state.report = report
                    else:
                        st.error("Report not ready yet.")
                except Exception as e:
                    st.error(f"Error: {e}")

        if "report" in st.session_state:
            report = st.session_state.report

            col1, col2 = st.columns(2)
            with col1:
                score = report.get("overall_score", 0)
                st.metric("Code Quality Score", f"{score}/10")
            with col2:
                confidence = report.get("confidence", 0)
                st.metric("Confidence", f"{confidence:.0%}")

            st.subheader("Executive Summary")
            st.write(report.get("executive_summary", "No summary available."))

            for severity, label, color in [
                ("critical_issues", "Critical Issues", "🔴"),
                ("high_issues", "High Priority Issues", "🟠"),
                ("medium_issues", "Medium Priority Issues", "🟡"),
                ("low_issues", "Low Priority Issues", "🟢"),
            ]:
                issues = report.get(severity, [])
                if issues:
                    st.subheader(f"{color} {label} ({len(issues)})")
                    for issue in issues:
                        title = issue.get("title", "Unknown")
                        issue_severity = issue.get("severity", "medium")
                        description = issue.get("description", "")
                        formatted_desc = format_finding_description(description)
                        with st.expander(f"**{title}** [{issue_severity}]"):
                            st.markdown(formatted_desc)
                            if issue.get("evidence"):
                                evidence_list = issue["evidence"]
                                if isinstance(evidence_list, list) and evidence_list:
                                    st.subheader("Evidence")
                                    for evidence in evidence_list:
                                        if isinstance(evidence, dict):
                                            file_info = evidence.get("file", evidence.get("file_path", ""))
                                            lines = evidence.get("lines", [])
                                            if file_info:
                                                if lines:
                                                    st.code(f"{file_info}:{lines}", language=None)
                                                else:
                                                    st.code(file_info, language=None)
                                        else:
                                            st.code(str(evidence), language=None)
                            if issue.get("file_path"):
                                st.caption(f"File: {issue['file_path']}")
                            if issue.get("line_number"):
                                st.caption(f"Line: {issue['line_number']}")

            positives = report.get("positive_observations", [])
            if positives:
                st.subheader("✅ Positive Observations")
                for pos in positives:
                    st.markdown(f"- {pos}")

            agent_summary = report.get("agent_summary", {})
            if agent_summary:
                st.subheader("📋 Agent Summary")
                for agent, summary in agent_summary.items():
                    st.markdown(f"**{agent}**: {summary}")
    else:
        st.info("Run an analysis first to see the report.")

with tab3:
    st.header("Debate Transcript")

    if "project_id" in st.session_state:
        if st.button("Load Debate"):
            with st.spinner("Loading debate..."):
                try:
                    resp = requests.get(
                        f"{API_BASE_URL}/projects/{st.session_state.project_id}/debate",
                        timeout=30,
                    )
                    if resp.status_code == 200:
                        debate = resp.json()
                        st.session_state.debate = debate
                    else:
                        st.error("Debate not available.")
                except Exception as e:
                    st.error(f"Error: {e}")

        if "debate" in st.session_state:
            debate = st.session_state.debate
            st.caption(f"Total messages: {debate.get('total_messages', 0)}")

            messages = debate.get("messages", [])
            phase_colors = {
                "opening": "🔵",
                "challenge": "🟠",
                "revision": "🟢",
                "synthesis": "🟣",
            }

            current_phase = None
            for msg in messages:
                phase = msg.get("phase", "unknown")
                if phase != current_phase:
                    current_phase = phase
                    st.subheader(f"{phase_colors.get(phase, '⚪')} Phase: {phase.title()}")

                with st.expander(f"**{msg.get('agent', 'Unknown')}** - Round {msg.get('round_num', 0)}"):
                    content = msg.get("content", "")
                    st.markdown(format_finding_description(content))

                    findings = msg.get("findings", [])
                    if findings:
                        st.subheader("Findings")
                        for f in findings:
                            st.markdown(
                                f"- **[{f.get('severity', 'medium')}]** "
                                f"{f.get('title', 'Unknown')}"
                            )
    else:
        st.info("Run an analysis first to see the debate transcript.")

with tab4:
    st.header("Agent Perspectives")

    if "project_id" in st.session_state and "debate" in st.session_state:
        debate = st.session_state.debate
        messages = debate.get("messages", [])

        agent_names = list(set(msg.get("agent", "Unknown") for msg in messages))
        selected_agent = st.selectbox("Select Agent", agent_names)

        if selected_agent:
            agent_messages = [m for m in messages if m.get("agent") == selected_agent]
            for msg in agent_messages:
                phase = msg.get("phase", "unknown")
                st.markdown(f"**Round {msg.get('round_num', 0)} - {phase.title()}**")
                content = msg.get("content", "")
                st.markdown(format_finding_description(content))
                st.divider()
    else:
        st.info("Run an analysis first to see agent perspectives.")

with st.sidebar:
    st.header("System Status")
    try:
        resp = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if resp.status_code == 200:
            health = resp.json()
            st.success("API: Connected")
        else:
            st.error("API: Error")
    except Exception:
        st.error("API: Disconnected")

    try:
        resp = requests.get(f"{API_BASE_URL}/health/llm", timeout=5)
        if resp.status_code == 200:
            llm_health = resp.json()
            if llm_health.get("connected"):
                st.success("LLM: Connected")
            elif not llm_health.get("api_key_set"):
                st.warning("LLM: API key not set")
                st.caption("Set OPENROUTER_API_KEY in backend/.env")
            else:
                st.error(f"LLM: {llm_health.get('error', 'Not connected')}")
    except Exception:
        st.warning("LLM: Status unknown")

    st.divider()
    st.header("Configuration")
    st.text(f"Backend: {API_BASE_URL}")

    if "project_id" in st.session_state:
        st.divider()
        st.header("Current Project")
        st.text(f"ID: {st.session_state.project_id}")
        if st.button("New Analysis"):
            del st.session_state.project_id
            if "report" in st.session_state:
                del st.session_state.report
            if "debate" in st.session_state:
                del st.session_state.debate
            st.rerun()
