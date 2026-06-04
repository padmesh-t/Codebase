import { useState, useEffect } from 'react'
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_REACT_APP_BACKEND_BASEURL || 'http://localhost:8000'

interface ProjectStatus {
  project_id: string
  status: string
  file_count: number
  chunk_count: number
  progress_percent: number
  error?: string
}

interface Finding {
  agent: string
  category: string
  severity: string
  title: string
  description: string
  evidence: string[]
  confidence: number
  file_path?: string
  line_number?: number
}

interface Report {
  executive_summary: string
  overall_score: number
  confidence: number
  critical_issues: Finding[]
  high_issues: Finding[]
  medium_issues: Finding[]
  low_issues: Finding[]
  positive_observations: string[]
  agent_summary: Record<string, string>
}

interface DebateMessage {
  agent: string
  phase: string
  round_num: number
  content: string
  findings: Finding[]
}

interface Debate {
  project_id: string
  messages: DebateMessage[]
  total_messages: number
}

function App() {
  const [activeTab, setActiveTab] = useState<'analyze' | 'report' | 'debate' | 'perspectives'>('analyze')
  const [projectId, setProjectId] = useState<string | null>(null)
  const [inputMethod, setInputMethod] = useState<'git' | 'upload'>('git')
  const [gitUrl, setGitUrl] = useState('')
  const [projectName, setProjectName] = useState('')
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const [projectStatus, setProjectStatus] = useState<ProjectStatus | null>(null)
  const [report, setReport] = useState<Report | null>(null)
  const [debate, setDebate] = useState<Debate | null>(null)
  const [selectedAgent, setSelectedAgent] = useState<string>('')

  const [apiConnected, setApiConnected] = useState(false)
  const [llmConnected, setLlmConnected] = useState(false)

  useEffect(() => {
    checkHealth()
  }, [])

  useEffect(() => {
    if (projectId && projectStatus?.status !== 'completed' && projectStatus?.status !== 'failed') {
      const interval = setInterval(() => checkStatus(), 2000)
      return () => clearInterval(interval)
    }
  }, [projectId, projectStatus?.status])

  const checkHealth = async () => {
    try {
      const resp = await axios.get(`${API_BASE_URL}/health`)
      setApiConnected(resp.data.status === 'healthy')
    } catch {
      setApiConnected(false)
    }

    try {
      const resp = await axios.get(`${API_BASE_URL}/health/llm`)
      setLlmConnected(resp.data.connected)
    } catch {
      setLlmConnected(false)
    }
  }

  const checkStatus = async () => {
    if (!projectId) return
    try {
      const resp = await axios.get(`${API_BASE_URL}/projects/${projectId}/status`)
      setProjectStatus(resp.data)
    } catch {
    }
  }

  const startAnalysis = async () => {
    if (!gitUrl && !uploadedFile) {
      setError('Please provide a Git URL or upload a file.')
      return
    }

    setLoading(true)
    setError(null)
    setSuccess(null)

    try {
      let resp
      if (inputMethod === 'git' && gitUrl) {
        resp = await axios.post(`${API_BASE_URL}/analyze`, null, {
          params: { git_url: gitUrl, project_name: projectName || undefined }
        })
      } else if (uploadedFile) {
        const formData = new FormData()
        formData.append('file', uploadedFile)
        resp = await axios.post(`${API_BASE_URL}/analyze`, formData)
      }

      if (resp?.data) {
        setProjectId(resp.data.project_id)
        setSuccess(`Analysis started! Project ID: ${resp.data.project_id}`)
      }
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to start analysis')
    } finally {
      setLoading(false)
    }
  }

  const loadReport = async () => {
    if (!projectId) return
    try {
      const resp = await axios.get(`${API_BASE_URL}/projects/${projectId}/report`)
      setReport(resp.data)
    } catch {
      setError('Report not ready yet')
    }
  }

  const loadDebate = async () => {
    if (!projectId) return
    try {
      const resp = await axios.get(`${API_BASE_URL}/projects/${projectId}/debate`)
      setDebate(resp.data)
    } catch {
      setError('Debate not available')
    }
  }

  const resetAnalysis = () => {
    setProjectId(null)
    setProjectStatus(null)
    setReport(null)
    setDebate(null)
    setSuccess(null)
    setError(null)
  }

  const renderAnalysisTab = () => (
    <div>
      <h2>Submit Codebase for Analysis</h2>

      <div className="radio-group">
        <label>
          <input
            type="radio"
            value="git"
            checked={inputMethod === 'git'}
            onChange={() => setInputMethod('git')}
          />
          Git URL
        </label>
        <label>
          <input
            type="radio"
            value="upload"
            checked={inputMethod === 'upload'}
            onChange={() => setInputMethod('upload')}
          />
          Upload Archive
        </label>
      </div>

      {inputMethod === 'git' ? (
        <div className="form-group">
          <label>Git Repository URL</label>
          <input
            type="text"
            value={gitUrl}
            onChange={(e) => setGitUrl(e.target.value)}
            placeholder="https://github.com/user/repo.git"
          />
        </div>
      ) : (
        <div className="form-group">
          <label>Upload project archive</label>
          <input
            type="file"
            accept=".zip,.tar.gz,.tgz"
            onChange={(e) => setUploadedFile(e.target.files?.[0] || null)}
          />
        </div>
      )}

      <div className="form-group">
        <label>Project Name (optional)</label>
        <input
          type="text"
          value={projectName}
          onChange={(e) => setProjectName(e.target.value)}
          placeholder="my-project"
        />
      </div>

      {error && <div className="error">{error}</div>}
      {success && <div className="success">{success}</div>}

      <button
        className="btn-primary"
        onClick={startAnalysis}
        disabled={loading || (!gitUrl && !uploadedFile)}
      >
        {loading ? 'Submitting...' : 'Start Analysis'}
      </button>

      {projectId && projectStatus && (
        <div className="card" style={{ marginTop: '30px' }}>
          <h3>Analysis Progress</h3>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${projectStatus.progress_percent}%` }}
            />
          </div>
          <p>Status: {projectStatus.status} ({projectStatus.progress_percent}%)</p>
          {projectStatus.status === 'completed' && (
            <p className="success">Analysis complete! Go to the Report tab.</p>
          )}
          {projectStatus.status === 'failed' && (
            <p className="error">Analysis failed: {projectStatus.error}</p>
          )}
        </div>
      )}
    </div>
  )

  const renderReportTab = () => (
    <div>
      <h2>Consensus Report</h2>

      {!report && (
        <button className="btn-primary" onClick={loadReport} disabled={!projectId}>
          Load Report
        </button>
      )}

      {report && (
        <>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-value">{report.overall_score}/10</div>
              <div className="stat-label">Code Quality Score</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{Math.round(report.confidence * 100)}%</div>
              <div className="stat-label">Confidence</div>
            </div>
          </div>

          <div className="card">
            <h3>Executive Summary</h3>
            <p>{report.executive_summary}</p>
          </div>

          {[
            { issues: report.critical_issues, label: 'Critical Issues', color: 'critical' },
            { issues: report.high_issues, label: 'High Priority Issues', color: 'high' },
            { issues: report.medium_issues, label: 'Medium Priority Issues', color: 'medium' },
            { issues: report.low_issues, label: 'Low Priority Issues', color: 'low' },
          ].map(({ issues, label, color }) =>
            issues.length > 0 && (
              <div key={label}>
                <h3>{label} ({issues.length})</h3>
                {issues.map((issue, idx) => (
                  <div key={idx} className="finding-card">
                    <div className="finding-header">
                      <div className="finding-title">{issue.title}</div>
                      <span className={`severity-badge severity-${color}`}>
                        {issue.severity}
                      </span>
                    </div>
                    <div className="finding-description">{issue.description}</div>
                    {issue.evidence.length > 0 && (
                      <div className="finding-evidence">
                        {issue.evidence.map((e, i) => (
                          <div key={i}>{e}</div>
                        ))}
                      </div>
                    )}
                    <div className="finding-meta">
                      {issue.file_path && <span>File: {issue.file_path}</span>}
                      {issue.line_number && <span>Line: {issue.line_number}</span>}
                      <span>Confidence: {Math.round(issue.confidence * 100)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            )
          )}

          {report.positive_observations.length > 0 && (
            <div className="card">
              <h3>Positive Observations</h3>
              <ul>
                {report.positive_observations.map((obs, idx) => (
                  <li key={idx}>{obs}</li>
                ))}
              </ul>
            </div>
          )}

          {Object.keys(report.agent_summary).length > 0 && (
            <div className="card">
              <h3>Agent Summary</h3>
              {Object.entries(report.agent_summary).map(([agent, summary]) => (
                <div key={agent} style={{ marginBottom: '15px' }}>
                  <strong>{agent}:</strong> {summary}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )

  const renderDebateTab = () => (
    <div>
      <h2>Debate Transcript</h2>

      {!debate && (
        <button className="btn-primary" onClick={loadDebate} disabled={!projectId}>
          Load Debate
        </button>
      )}

      {debate && (
        <>
          <p>Total messages: {debate.total_messages}</p>

          {debate.messages.map((msg, idx) => (
            <div key={idx} className="debate-message">
              <div className="message-header">
                <span className="agent-name">{msg.agent}</span>
                <span className={`phase-badge phase-${msg.phase}`}>
                  {msg.phase}
                </span>
              </div>
              <div className="message-content">{msg.content}</div>
              {msg.findings.length > 0 && (
                <div style={{ marginTop: '15px' }}>
                  <strong>Findings:</strong>
                  {msg.findings.map((f, i) => (
                    <div key={i} style={{ marginTop: '5px' }}>
                      <span className={`severity-badge severity-${f.severity}`}>
                        {f.severity}
                      </span>{' '}
                      {f.title}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </>
      )}
    </div>
  )

  const renderPerspectivesTab = () => {
    if (!debate) {
      return <p>Load debate first to see agent perspectives.</p>
    }

    const agentNames = [...new Set(debate.messages.map(m => m.agent))]
    const agentMessages = debate.messages.filter(m => m.agent === selectedAgent)

    return (
      <div>
        <h2>Agent Perspectives</h2>

        <div className="form-group">
          <label>Select Agent</label>
          <select value={selectedAgent} onChange={(e) => setSelectedAgent(e.target.value)}>
            <option value="">Choose an agent</option>
            {agentNames.map(name => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
        </div>

        {selectedAgent && agentMessages.map((msg, idx) => (
          <div key={idx} className="debate-message">
            <div className="message-header">
              <span className="agent-name">{msg.agent}</span>
              <span className={`phase-badge phase-${msg.phase}`}>
                Round {msg.round_num} - {msg.phase}
              </span>
            </div>
            <div className="message-content">{msg.content}</div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="container">
      <div className="header">
        <h1>Codebase Intelligence</h1>
        <p>Multi-agent code review with debate-based consensus</p>
      </div>

      <div className="tabs">
        {(['analyze', 'report', 'debate', 'perspectives'] as const).map(tab => (
          <button
            key={tab}
            className={`tab ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      <div className="main-content">
        {activeTab === 'analyze' && renderAnalysisTab()}
        {activeTab === 'report' && renderReportTab()}
        {activeTab === 'debate' && renderDebateTab()}
        {activeTab === 'perspectives' && renderPerspectivesTab()}
      </div>

      <div className="sidebar">
        <div className="sidebar-section">
          <div className="sidebar-title">System Status</div>
          <div className="status-indicator">
            <div className={`status-dot ${apiConnected ? '' : 'disconnected'}`} />
            <span>API: {apiConnected ? 'Connected' : 'Disconnected'}</span>
          </div>
          <div className="status-indicator">
            <div className={`status-dot ${llmConnected ? '' : 'disconnected'}`} />
            <span>LLM: {llmConnected ? 'Connected' : 'Disconnected'}</span>
          </div>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-title">Configuration</div>
          <p>Backend: {API_BASE_URL}</p>
        </div>

        {projectId && (
          <div className="sidebar-section">
            <div className="sidebar-title">Current Project</div>
            <p>ID: {projectId}</p>
            <button onClick={resetAnalysis} style={{ marginTop: '10px' }}>
              New Analysis
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
