import React, { useState, useRef, useEffect } from 'react';
import PdfViewer from './components/PdfViewer';
import EvaluationReport from './components/EvaluationReport';
import { API_ENDPOINTS, resolvePdfUrl, getBackendHostLabel } from './config/api';
import './App.css';

const PAPERS = [
  { id: 'GS-1', label: 'GS 1 • History, Geography, Art & Culture, Society' },
  { id: 'GS-2', label: 'GS 2 • Polity, Constitution, Governance, Social Justice, IR' },
  { id: 'GS-3', label: 'GS 3 • Economy, Agri, Science & Tech, Environment, Security' },
  { id: 'GS-4', label: 'GS 4 • Ethics, Integrity & Aptitude' },
];

export default function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [isDragActive, setIsDragActive] = useState(false);
  const [paper, setPaper] = useState('GS-1');
  const [marks, setMarks] = useState(15);
  const [showQuestionInput, setShowQuestionInput] = useState(false);
  const [questionText, setQuestionText] = useState('');

  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [error, setError] = useState(null);
  const [report, setReport] = useState(null);
  const [copiedType, setCopiedType] = useState(null);

  // View Mode: 'split' | 'report' | 'pdf'
  const [viewMode, setViewMode] = useState('split');
  const [localPdfBlobUrl, setLocalPdfBlobUrl] = useState(null);

  // History & Database Persistence State
  const [historyOpen, setHistoryOpen] = useState(false);
  const [evaluationsList, setEvaluationsList] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedEvaluationMeta, setSelectedEvaluationMeta] = useState(null);
  const [historyPaperFilter, setHistoryPaperFilter] = useState('ALL');
  const [deletingId, setDeletingId] = useState(null);

  const fileInputRef = useRef(null);

  // Derive active PDF URL and filename from available sources
  const activePdfUrl =
    report?.pdf_url ||
    selectedEvaluationMeta?.pdf_url ||
    localPdfBlobUrl;

  const activePdfFilename =
    report?.filename ||
    selectedEvaluationMeta?.filename ||
    selectedFile?.name ||
    'Candidate Answer Copy.pdf';

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        setError('Please select a valid PDF file (.pdf)');
        return;
      }
      if (localPdfBlobUrl) {
        URL.revokeObjectURL(localPdfBlobUrl);
      }
      setSelectedFile(file);
      setLocalPdfBlobUrl(URL.createObjectURL(file));
      setError(null);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragActive(true);
  };

  const handleDragLeave = () => {
    setIsDragActive(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragActive(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        setError('Please drop a valid PDF file (.pdf)');
        return;
      }
      if (localPdfBlobUrl) {
        URL.revokeObjectURL(localPdfBlobUrl);
      }
      setSelectedFile(file);
      setLocalPdfBlobUrl(URL.createObjectURL(file));
      setError(null);
    }
  };

  const handleRemoveFile = () => {
    if (localPdfBlobUrl) {
      URL.revokeObjectURL(localPdfBlobUrl);
      setLocalPdfBlobUrl(null);
    }
    setSelectedFile(null);
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
  };

  const fetchEvaluations = async () => {
    try {
      setHistoryLoading(true);
      const res = await fetch(API_ENDPOINTS.evaluations);
      if (res.ok) {
        const data = await res.json();
        setEvaluationsList(data);
      }
    } catch (err) {
      console.error('Failed to load history:', err);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    fetchEvaluations();
  }, []);

  const formatDate = (isoStr) => {
    if (!isoStr) return '';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoStr;
    }
  };

  const handleSelectEvaluation = async (evalId) => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch(API_ENDPOINTS.evaluationById(evalId));
      if (!res.ok) throw new Error('Could not load evaluation record');
      const data = await res.json();
      const rawPdfLink = data.pdf_url || data.report?.pdf_url;
      const pdfLink = resolvePdfUrl(rawPdfLink);
      const loadedReport = {
        ...data.report,
        pdf_url: pdfLink,
      };
      setReport(loadedReport);
      setSelectedEvaluationMeta({
        id: data.id,
        created_at: data.created_at,
        paper: data.paper,
        marks: data.marks,
        question_text: data.question_text,
        filename: data.filename,
        pdf_url: pdfLink,
      });
      setPaper(data.paper || 'GS-1');
      setMarks(data.marks || 15);
      setViewMode(pdfLink ? 'split' : 'report');
      setHistoryOpen(false);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      console.error(err);
      setError('Failed to load saved evaluation.');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteEvaluation = async (e, evalId) => {
    e.stopPropagation();
    if (!window.confirm('Delete this evaluation record from database?')) return;
    setDeletingId(evalId);
    try {
      const res = await fetch(API_ENDPOINTS.evaluationById(evalId), { method: 'DELETE' });
      if (res.ok) {
        setEvaluationsList((prev) => prev.filter((item) => item.id !== evalId));
        if (selectedEvaluationMeta?.id === evalId) {
          resetAll();
        }
      }
    } catch (err) {
      console.error('Failed to delete evaluation:', err);
    } finally {
      setDeletingId(null);
    }
  };

  const filteredEvaluations = historyPaperFilter === 'ALL'
    ? evaluationsList
    : evaluationsList.filter((item) => item.paper === historyPaperFilter);

  const startPipelineTimer = () => {
    setLoadingStep(0);
    const interval = setInterval(() => {
      setLoadingStep((prev) => {
        if (prev < 4) return prev + 1;
        return prev;
      });
    }, 2400);
    return interval;
  };

  const handleEvaluate = async () => {
    if (!selectedFile) {
      setError('Please upload an answer copy PDF to evaluate.');
      return;
    }

    setLoading(true);
    setError(null);
    const timer = startPipelineTimer();

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('paper', paper);
      formData.append('marks', marks.toString());
      if (questionText.trim()) {
        formData.append('question', questionText.trim());
      }

      const res = await fetch(API_ENDPOINTS.evaluate, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: 'Evaluation server failed' }));
        throw new Error(errorData.detail || `Server returned error ${res.status}`);
      }

      const data = await res.json();
      const resolvedPdf = resolvePdfUrl(data.pdf_url);
      setReport({ ...data, pdf_url: resolvedPdf });
      setSelectedEvaluationMeta({
        id: data.id,
        created_at: data.created_at,
        filename: selectedFile.name,
        paper: paper,
        marks: marks,
        pdf_url: resolvedPdf,
      });
      setViewMode('split');
      fetchEvaluations();
    } catch (err) {
      console.error(err);
      setError(err.message || 'An error occurred during evaluation.');
    } finally {
      clearInterval(timer);
      setLoading(false);
    }
  };

  const handleEvaluateSample = async () => {
    setLoading(true);
    setError(null);
    const timer = startPipelineTimer();

    try {
      const formData = new FormData();
      formData.append('paper', paper);
      formData.append('marks', marks.toString());

      const res = await fetch(API_ENDPOINTS.evaluateSample, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: 'Sample evaluation failed' }));
        throw new Error(errorData.detail || `Server returned error ${res.status}`);
      }

      const data = await res.json();
      const resolvedPdf = resolvePdfUrl(data.pdf_url);
      setReport({ ...data, pdf_url: resolvedPdf });
      setSelectedEvaluationMeta({
        id: data.id,
        created_at: data.created_at,
        filename: 'Sample Copy (Press in India)',
        paper: paper,
        marks: marks,
        pdf_url: resolvedPdf,
      });
      setViewMode(resolvedPdf ? 'split' : 'report');
      fetchEvaluations();
    } catch (err) {
      console.error(err);
      setError(err.message || 'Failed to evaluate sample answer.');
    } finally {
      clearInterval(timer);
      setLoading(false);
    }
  };

  const copyToClipboard = (text, type) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedType(type);
    setTimeout(() => setCopiedType(null), 2000);
  };

  const resetAll = () => {
    if (localPdfBlobUrl) {
      URL.revokeObjectURL(localPdfBlobUrl);
      setLocalPdfBlobUrl(null);
    }
    setReport(null);
    setSelectedFile(null);
    setError(null);
    setSelectedEvaluationMeta(null);
    setViewMode('split');
  };

  return (
    <div className="app-container">
      {/* Top Navbar */}
      <header className="app-header">
        <div className="brand">
          <div className="brand-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
            </svg>
          </div>
          <span className="brand-name">CivilEval AI</span>
        </div>

        <div className="header-actions">
          <div className="header-badge" title={`Active Backend: ${getBackendHostLabel()}`}>
            <span className="status-dot"></span>
            <span>API: {getBackendHostLabel()}</span>
          </div>

          <button
            type="button"
            className="history-nav-btn"
            onClick={() => { setHistoryOpen(true); fetchEvaluations(); }}
            title="View saved evaluations"
          >
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"></circle>
              <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
            <span>Past Evaluations</span>
            {evaluationsList.length > 0 && (
              <span className="history-badge-count">{evaluationsList.length}</span>
            )}
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className={`main-content ${report ? (viewMode === 'split' && activePdfUrl ? 'workspace-split' : (viewMode === 'pdf' ? 'workspace-pdf-full' : 'workspace-report-full')) : ''}`}>
        {!report && (
          <div className="hero">
            <h1 className="hero-title">UPSC Mains Answer Evaluator</h1>
            <p className="hero-subtitle">
              Upload your handwritten or typed answer copy in PDF format. Our multi-agent judge panel
              performs calibrated scoring, RAG fact-verification, and generates model rewrites.
            </p>
          </div>
        )}

        <div className={`evaluator-card ${report && viewMode === 'split' && activePdfUrl ? 'split-card' : ''}`}>
          {loading ? (
            <div className="loading-container">
              <div className="pulse-spinner"></div>
              <h2 className="loading-title">Evaluating Answer Copy...</h2>
              <p className="loading-subtitle">The multi-agent panel is concurrently analyzing your submission</p>

              <div className="pipeline-steps">
                <div className={`pipeline-step ${loadingStep >= 0 ? 'active' : ''}`}>
                  <span className="step-icon">📄</span>
                  <span>Extracting text & handwritten OCR from PDF</span>
                </div>
                <div className={`pipeline-step ${loadingStep >= 1 ? 'active' : ''}`}>
                  <span className="step-icon">🎯</span>
                  <span>Demand & Directive Agent checking sub-parts fulfillment</span>
                </div>
                <div className={`pipeline-step ${loadingStep >= 2 ? 'active' : ''}`}>
                  <span className="step-icon">🏛️</span>
                  <span>Structure, Intro & Conclusion Agents scoring organization</span>
                </div>
                <div className={`pipeline-step ${loadingStep >= 3 ? 'active' : ''}`}>
                  <span className="step-icon">📚</span>
                  <span>Knowledge & Fact Agent verifying claims against RAG store</span>
                </div>
                <div className={`pipeline-step ${loadingStep >= 4 ? 'active' : ''}`}>
                  <span className="step-icon">⚖️</span>
                  <span>Master Arbiter Agent synthesizing calibrated scores & roadmap</span>
                </div>
              </div>
            </div>
          ) : report ? (
            /* Results View */
            <div className="results-container">
              <div className="results-header-bar">
                <button className="back-btn" onClick={resetAll}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="19" y1="12" x2="5" y2="12"></line>
                    <polyline points="12 19 5 12 12 5"></polyline>
                  </svg>
                  <span>Evaluate Another Copy</span>
                </button>

                {/* View Mode Switcher Pills */}
                {activePdfUrl && (
                  <div className="view-mode-selector">
                    <button
                      type="button"
                      className={`view-mode-btn ${viewMode === 'split' ? 'active' : ''}`}
                      onClick={() => setViewMode('split')}
                      title="Side-by-side view with PDF copy"
                    >
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                        <line x1="12" y1="3" x2="12" y2="21"></line>
                      </svg>
                      <span>Side-by-Side</span>
                    </button>
                    <button
                      type="button"
                      className={`view-mode-btn ${viewMode === 'report' ? 'active' : ''}`}
                      onClick={() => setViewMode('report')}
                      title="Evaluation report only"
                    >
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                        <polyline points="14 2 14 8 20 8"></polyline>
                        <line x1="16" y1="13" x2="8" y2="13"></line>
                        <line x1="16" y1="17" x2="8" y2="17"></line>
                      </svg>
                      <span>Report Only</span>
                    </button>
                    <button
                      type="button"
                      className={`view-mode-btn ${viewMode === 'pdf' ? 'active' : ''}`}
                      onClick={() => setViewMode('pdf')}
                      title="Original PDF answer copy only"
                    >
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
                        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
                      </svg>
                      <span>PDF Only</span>
                    </button>
                  </div>
                )}

                <div className="results-header-actions">
                  <button
                    type="button"
                    className="history-switch-btn"
                    onClick={() => { setHistoryOpen(true); fetchEvaluations(); }}
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="10"></circle>
                      <polyline points="12 6 12 12 16 14"></polyline>
                    </svg>
                    <span>Past Evaluations ({evaluationsList.length})</span>
                  </button>
                  <span className="time-badge">Evaluated in {report.total_latency_seconds}s</span>
                  {report.trace_url && (
                    <a
                      href={report.trace_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="langfuse-trace-link"
                      title="Inspect full execution trace in Langfuse dashboard"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <circle cx="11" cy="11" r="8"></circle>
                        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                      </svg>
                      <span>Langfuse Trace ↗</span>
                    </a>
                  )}
                </div>
              </div>

              {selectedEvaluationMeta && (
                <div className="saved-eval-indicator">
                  <div className="saved-eval-left">
                    <span className="saved-eval-pill">💾 Database Record</span>
                    <span className="saved-eval-meta">
                      <strong>ID:</strong> {selectedEvaluationMeta.id} &bull; <strong>Saved:</strong> {formatDate(selectedEvaluationMeta.created_at)}
                      {selectedEvaluationMeta.filename ? ` • ${selectedEvaluationMeta.filename}` : ''}
                      {activePdfUrl ? ' • 📄 PDF Attached' : ''}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="history-reopen-btn"
                    onClick={() => { setHistoryOpen(true); fetchEvaluations(); }}
                  >
                    View All Saved &rarr;
                  </button>
                </div>
              )}

              {/* View Layout Switch */}
              {viewMode === 'split' && activePdfUrl ? (
                <div className="eval-split-layout">
                  <div className="eval-pdf-column">
                    <PdfViewer pdfUrl={activePdfUrl} filename={activePdfFilename} />
                  </div>
                  <div className="eval-report-column">
                    <EvaluationReport
                      report={report}
                      paper={paper}
                      marks={marks}
                      copyToClipboard={copyToClipboard}
                      copiedType={copiedType}
                      onReset={resetAll}
                    />
                  </div>
                </div>
              ) : viewMode === 'pdf' && activePdfUrl ? (
                <div className="eval-full-pdf-layout">
                  <PdfViewer pdfUrl={activePdfUrl} filename={activePdfFilename} />
                </div>
              ) : (
                <div className="eval-single-report-layout">
                  <EvaluationReport
                    report={report}
                    paper={paper}
                    marks={marks}
                    copyToClipboard={copyToClipboard}
                    copiedType={copiedType}
                    onReset={resetAll}
                  />
                </div>
              )}
            </div>
          ) : (
            /* Upload & Configuration View */
            <>
              {/* Dropzone */}
              <div className="dropzone-container">
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  accept=".pdf,application/pdf"
                  style={{ display: 'none' }}
                />

                {!selectedFile ? (
                  <div
                    className={`dropzone ${isDragActive ? 'drag-active' : ''}`}
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                  >
                    <div className="upload-icon-circle">
                      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                        <polyline points="17 8 12 3 7 8"></polyline>
                        <line x1="12" y1="3" x2="12" y2="15"></line>
                      </svg>
                    </div>
                    <div className="upload-title">Click to upload or drag a PDF here</div>
                    <div className="upload-hint">Handwritten or typed answer copies • PDF up to 25MB</div>
                  </div>
                ) : (
                  <div className="file-selected-box">
                    <div className="file-info">
                      <div className="pdf-icon-badge">PDF</div>
                      <div className="file-details">
                        <span className="file-name">{selectedFile.name}</span>
                        <span className="file-size">{formatFileSize(selectedFile.size)}</span>
                      </div>
                    </div>
                    <div className="file-actions">
                      <button className="change-btn" onClick={() => fileInputRef.current?.click()}>
                        Change
                      </button>
                      <button className="remove-btn" onClick={handleRemoveFile}>
                        Remove
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Configuration Controls */}
              <div className="config-row">
                {/* 1. Paper Dropdown */}
                <div className="config-group">
                  <label className="config-label" htmlFor="paper-select">
                    <span>Select Paper</span>
                  </label>
                  <div className="paper-select-wrapper">
                    <select
                      id="paper-select"
                      className="paper-select"
                      value={paper}
                      onChange={(e) => setPaper(e.target.value)}
                    >
                      {PAPERS.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.label}
                        </option>
                      ))}
                    </select>
                    <div className="select-chevron">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <polyline points="6 9 12 15 18 9"></polyline>
                      </svg>
                    </div>
                  </div>
                </div>

                {/* 2. Aesthetic Marks Segmented Control */}
                <div className="config-group">
                  <label className="config-label">
                    <span>Question Marks</span>
                    <span className="config-label-hint">Preset word limits</span>
                  </label>
                  <div className="marks-segmented-control">
                    <button
                      type="button"
                      className={`segmented-pill ${marks === 10 ? 'active' : ''}`}
                      onClick={() => setMarks(10)}
                    >
                      <span className="pill-title">10 Marks</span>
                      <span className="pill-desc">150 Words • 2 Pages</span>
                    </button>
                    <button
                      type="button"
                      className={`segmented-pill ${marks === 15 ? 'active' : ''}`}
                      onClick={() => setMarks(15)}
                    >
                      <span className="pill-title">15 Marks</span>
                      <span className="pill-desc">250 Words • 3 Pages</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Optional Question Override */}
              <div className="question-override-section">
                <button
                  type="button"
                  className="question-toggle-btn"
                  onClick={() => setShowQuestionInput(!showQuestionInput)}
                >
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.2"
                    style={{ transform: showQuestionInput ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s ease' }}
                  >
                    <polyline points="9 18 15 12 9 6"></polyline>
                  </svg>
                  <span>{showQuestionInput ? 'Hide Question statement' : '+ Specify Question statement (Optional - auto-detected from PDF)'}</span>
                </button>

                {showQuestionInput && (
                  <textarea
                    className="question-textarea"
                    placeholder="Enter the UPSC question statement here if not clearly legible on the first page of the PDF..."
                    value={questionText}
                    onChange={(e) => setQuestionText(e.target.value)}
                  />
                )}
              </div>

              {/* Bottom Action Row */}
              <div className="action-row">
                <button
                  type="button"
                  className="sample-test-btn"
                  onClick={handleEvaluateSample}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polygon points="5 3 19 12 5 21 5 3"></polygon>
                  </svg>
                  <span>Try Sample Answer</span>
                </button>

                <button
                  type="button"
                  className="evaluate-btn"
                  disabled={!selectedFile}
                  onClick={handleEvaluate}
                >
                  <span>Evaluate Answer</span>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="5" y1="12" x2="19" y2="12"></line>
                    <polyline points="12 5 19 12 12 19"></polyline>
                  </svg>
                </button>
              </div>

              {/* Error Banner */}
              {error && (
                <div className="error-banner">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="8" x2="12" y2="12"></line>
                    <line x1="12" y1="16" x2="12.01" y2="16"></line>
                  </svg>
                  <span>{error}</span>
                </div>
              )}
            </>
          )}
        </div>
      </main>

      {/* Slide-over Evaluation History Drawer */}
      {historyOpen && (
        <div className="history-drawer-backdrop" onClick={() => setHistoryOpen(false)}>
          <aside className="history-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-header">
              <div className="drawer-title-group">
                <div className="drawer-title-row">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10"></circle>
                    <polyline points="12 6 12 12 16 14"></polyline>
                  </svg>
                  <h2 className="drawer-title">Evaluation History</h2>
                </div>
                <p className="drawer-subtitle">
                  {evaluationsList.length} saved {evaluationsList.length === 1 ? 'copy' : 'copies'} in database
                </p>
              </div>
              <button
                type="button"
                className="close-drawer-btn"
                onClick={() => setHistoryOpen(false)}
                aria-label="Close history"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            </div>

            {/* Paper Filter Bar */}
            <div className="history-filters">
              {['ALL', 'GS-1', 'GS-2', 'GS-3', 'GS-4'].map((p) => (
                <button
                  key={p}
                  type="button"
                  className={`filter-pill ${historyPaperFilter === p ? 'active' : ''}`}
                  onClick={() => setHistoryPaperFilter(p)}
                >
                  {p}
                </button>
              ))}
            </div>

            {/* History Items List */}
            <div className="history-list">
              {historyLoading ? (
                <div className="history-loading">
                  <div className="pulse-spinner-small"></div>
                  <span>Loading saved evaluations...</span>
                </div>
              ) : filteredEvaluations.length === 0 ? (
                <div className="history-empty">
                  <div className="history-empty-icon">📁</div>
                  <h3 className="history-empty-title">No evaluations found</h3>
                  <p className="history-empty-desc">
                    {historyPaperFilter === 'ALL'
                      ? 'Evaluated answer copies will be automatically saved into the database and listed here for instant access.'
                      : `No evaluations found under ${historyPaperFilter}.`}
                  </p>
                </div>
              ) : (
                filteredEvaluations.map((item) => {
                  const isSelected = selectedEvaluationMeta?.id === item.id;
                  return (
                    <div
                      key={item.id}
                      className={`history-card ${isSelected ? 'active-card' : ''}`}
                      onClick={() => handleSelectEvaluation(item.id)}
                    >
                      <div className="card-top-row">
                        <div className="card-tags">
                          <span className="history-paper-tag">{item.paper}</span>
                          <span className="history-marks-tag">{item.marks} Marks</span>
                          {item.pdf_url && (
                            <span className="history-pdf-tag" title="PDF Copy Attached">
                              📄 PDF
                            </span>
                          )}
                        </div>
                        <span className="history-date">{formatDate(item.created_at)}</span>
                      </div>

                      <div className="card-question-preview" title={item.question_text || item.filename}>
                        {item.question_text || item.filename || 'UPSC Answer Submission'}
                      </div>

                      <div className="card-bottom-row">
                        <div className="history-score-group">
                          <span className="history-score-val">
                            {item.total_score} <span className="history-score-denom">/ {item.max_marks}</span>
                          </span>
                          <span className="history-pct-pill">{item.percentage}%</span>
                          <span className="history-verdict-pill">{item.benchmark_verdict}</span>
                        </div>

                        <button
                          type="button"
                          className="delete-history-btn"
                          title="Delete this evaluation"
                          disabled={deletingId === item.id}
                          onClick={(e) => handleDeleteEvaluation(e, item.id)}
                        >
                          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <polyline points="3 6 5 6 21 6"></polyline>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                          </svg>
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
