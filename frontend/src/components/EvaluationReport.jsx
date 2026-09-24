import React from 'react';
import MarkdownText from './MarkdownText';

export default function EvaluationReport({
  report,
  paper,
  marks,
  copyToClipboard,
  copiedType,
  onReset,
}) {
  if (!report) return null;

  return (
    <div className="report-content-flow">
      {/* Scorecard Hero */}
      <div className="scorecard-hero">
        <div className="score-main">
          <span className="score-context">{paper} • {marks} MARKS EVALUATION</span>
          <div className="score-digits">
            <span className="score-number">{report.scorecard.total_score}</span>
            <span className="score-total">/ {report.scorecard.max_marks} Marks</span>
          </div>
          <div className="score-badges">
            <span className="verdict-badge">{report.scorecard.benchmark_verdict}</span>
            <span className="percentage-badge">{report.scorecard.percentage}% Calibrated Score</span>
          </div>
        </div>
      </div>

      {/* Penalties Alert if any */}
      {report.scorecard.penalties_applied && report.scorecard.penalties_applied.length > 0 && (
        <div className="error-banner">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
          <div>
            <strong>Penalties Applied:</strong> {report.scorecard.penalties_applied.join(' | ')}
          </div>
        </div>
      )}

      {/* 5-Parameter Dimension Breakdown */}
      <div>
        <h3 className="section-title">📊 Parameter-Wise Scorecard Breakdown</h3>
        <div className="dimensions-grid">
          {Object.entries(report.scorecard.dimensions || {}).map(([dimName, ds]) => (
            <div key={dimName} className="dimension-card">
              <div className="dim-top">
                <span className="dim-name">{dimName}</span>
                <span className="dim-weight">{ds.weight_pct}% Weight</span>
              </div>
              <div className="dim-score-row">
                <span className="dim-raw-score">{ds.raw_score_out_of_10}/10</span>
                <span className="dim-effective">{ds.effective_marks.toFixed(2)} marks</span>
              </div>
              <div className="dim-progress-track">
                <div
                  className="dim-progress-bar"
                  style={{ width: `${(ds.raw_score_out_of_10 / 10) * 100}%` }}
                ></div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Model Rewrites */}
      <div>
        <h3 className="section-title">✍️ Model Introduction & Conclusion Rewrites</h3>
        <div className="rewrites-section">
          <div className="rewrite-card">
            <div className="rewrite-header">
              <span className="rewrite-tag">Model Intro Rewrite</span>
              <button
                className="copy-btn"
                onClick={() => copyToClipboard(report.intro_evaluation?.model_intro_rewrite, 'intro')}
              >
                {copiedType === 'intro' ? 'Copied!' : 'Copy'}
              </button>
            </div>
            <div className="rewrite-body">
              <MarkdownText text={report.intro_evaluation?.model_intro_rewrite || 'N/A'} />
            </div>
          </div>

          <div className="rewrite-card">
            <div className="rewrite-header">
              <span className="rewrite-tag">Model Conclusion Rewrite</span>
              <button
                className="copy-btn"
                onClick={() => copyToClipboard(report.conclusion_evaluation?.model_conclusion_rewrite, 'conclusion')}
              >
                {copiedType === 'conclusion' ? 'Copied!' : 'Copy'}
              </button>
            </div>
            <div className="rewrite-body">
              <MarkdownText text={report.conclusion_evaluation?.model_conclusion_rewrite || 'N/A'} />
            </div>
          </div>
        </div>
      </div>

      {/* Steps for a Good Answer */}
      {report.transformation_roadmap && (
        <div>
          <h3 className="section-title">🚀 Steps for a Good Answer</h3>
          <div className="roadmap-container">
            {report.transformation_roadmap.current_level_summary && (
              <div className="roadmap-summary">
                <strong>Current Assessment:</strong>{' '}
                <MarkdownText text={report.transformation_roadmap.current_level_summary} inline />
              </div>
            )}
            <div className={report.transformation_roadmap.step_2_topper_answer && report.transformation_roadmap.step_2_topper_answer.length > 0 ? "roadmap-columns" : "roadmap-single-column"}>
              <div className="roadmap-col">
                <div className="col-header step1">Key Action Steps to Reach 55%+ (Solid Answer)</div>
                <ul className="roadmap-list">
                  {(report.transformation_roadmap.good_answer_steps || report.transformation_roadmap.step_1_good_answer)?.map((item, idx) => (
                    <li key={idx} className="roadmap-item">
                      <span className="item-bullet">•</span>
                      <div className="roadmap-item-content">
                        <MarkdownText text={item} />
                      </div>
                    </li>
                  ))}
                </ul>
              </div>

              {report.transformation_roadmap.step_2_topper_answer && report.transformation_roadmap.step_2_topper_answer.length > 0 && (
                <div className="roadmap-col">
                  <div className="col-header step2">Step 2: Additions to reach 70%+ (Topper Level)</div>
                  <ul className="roadmap-list">
                    {report.transformation_roadmap.step_2_topper_answer?.map((item, idx) => (
                      <li key={idx} className="roadmap-item">
                        <span className="item-bullet">•</span>
                        <div className="roadmap-item-content">
                          <MarkdownText text={item} />
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Top Value Additions */}
      {report.top_value_additions && report.top_value_additions.length > 0 && (
        <div>
          <h3 className="section-title">💡 Top Value Additions</h3>
          <div className="value-additions-grid">
            {report.top_value_additions.map((va, idx) => (
              <div key={idx} className="va-card">
                <div className="va-number">{idx + 1}</div>
                <div className="va-text">
                  <MarkdownText text={va} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Knowledge & Factual Accuracy Audit */}
      {report.knowledge_evaluation && (
        <div>
          <div className="section-header-row">
            <h3 className="section-title">🔍 Knowledge & Factual Accuracy Audit</h3>
            {report.knowledge_evaluation.factual_accuracy_score !== undefined && (
              <span className="section-score-badge">
                Accuracy Score: {report.knowledge_evaluation.factual_accuracy_score}/10
              </span>
            )}
          </div>

          {/* Claims Checked List */}
          {report.knowledge_evaluation.claims_checked && report.knowledge_evaluation.claims_checked.length > 0 ? (
            <div className="facts-list">
              {report.knowledge_evaluation.claims_checked.map((claim, idx) => {
                const verdictLower = (claim.verdict || 'unverified').toLowerCase();
                return (
                  <div key={idx} className={`fact-item verdict-${verdictLower}`}>
                    <div className="fact-top">
                      <span className={`fact-verdict ${verdictLower}`}>
                        {claim.verdict}
                      </span>
                      <span className="fact-claim">
                        "<MarkdownText text={claim.claim} inline />"
                      </span>
                    </div>
                    {claim.correction && (
                      <div className="fact-correction">
                        <strong>Correction:</strong>{' '}
                        <MarkdownText text={claim.correction} inline />
                      </div>
                    )}
                    {claim.grounded_evidence && (
                      <div className="fact-evidence">
                        <strong>Evidence:</strong>{' '}
                        <MarkdownText text={claim.grounded_evidence} inline />
                      </div>
                    )}
                    {claim.source_citation && (
                      <div className="fact-source">
                        <strong>Source / Benchmark:</strong> {claim.source_citation}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="empty-facts-notice">No specific factual claims extracted for verification.</div>
          )}
        </div>
      )}

      {/* Pedagogical Actionable Improvements */}
      {(() => {
        const allImprovements = [
          // ...(report.demand_evaluation?.improvements || []),
          // ...(report.structure_evaluation?.improvements || []),
        ];

        if (allImprovements.length === 0) return null;

        return (
          <div>
            <h3 className="section-title">🎯 Actionable Improvements & Snippets</h3>
            <div className="improvements-list">
              {allImprovements.map((imp, idx) => (
                <div key={idx} className="improvement-card">
                  <div className="imp-header">
                    <span className="imp-section">{imp.section}</span>
                    <span className="imp-impact">⚠️ {imp.mark_impact}</span>
                  </div>
                  <div className="imp-issue">
                    <MarkdownText text={imp.issue_detected} inline />
                  </div>
                  <div className="imp-prescription">
                    <MarkdownText text={imp.prescription} />
                  </div>
                  {imp.plug_and_play_snippet && (
                    <div className="imp-snippet">
                      <MarkdownText text={imp.plug_and_play_snippet} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })()}

      {onReset && (
        <div className="results-footer">
          <button className="new-eval-btn" onClick={onReset}>
            Evaluate Another Answer Copy
          </button>
        </div>
      )}
    </div>
  );
}
