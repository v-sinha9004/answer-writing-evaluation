import React, { useState } from 'react';

export default function PdfViewer({ pdfUrl, filename }) {
  const [iframeLoaded, setIframeLoaded] = useState(false);

  if (!pdfUrl) {
    return (
      <div className="pdf-viewer-empty">
        <div className="pdf-empty-icon">📄</div>
        <h4 className="pdf-empty-title">Original Answer Copy PDF Not Available</h4>
        <p className="pdf-empty-desc">
          This evaluation record was saved prior to cloud PDF storage or evaluated without an uploaded PDF file.
        </p>
      </div>
    );
  }

  // Optimize URL for native PDF viewer with parameters
  const viewerUrl = pdfUrl.includes('#') ? pdfUrl : `${pdfUrl}#toolbar=1&navpanes=0&view=FitH`;

  return (
    <div className="pdf-viewer-panel">
      {/* Sleek Top Toolbar */}
      <div className="pdf-viewer-toolbar">
        <div className="pdf-toolbar-left">
          <span className="pdf-pill-badge">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
              <polyline points="10 9 9 9 8 9"></polyline>
            </svg>
            Answer Copy
          </span>
          <span className="pdf-filename" title={filename || 'Candidate Answer Copy'}>
            {filename || 'Candidate Answer Copy.pdf'}
          </span>
        </div>

        <div className="pdf-toolbar-actions">
          <a
            href={pdfUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="pdf-tool-btn"
            title="Open PDF in new tab"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
              <polyline points="15 3 21 3 21 9"></polyline>
              <line x1="10" y1="14" x2="21" y2="3"></line>
            </svg>
            <span>New Tab</span>
          </a>

          <a
            href={pdfUrl}
            download={filename || 'candidate_answer.pdf'}
            className="pdf-tool-btn pdf-download-btn"
            title="Download PDF copy"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            <span>Download</span>
          </a>
        </div>
      </div>

      {/* Frame Container */}
      <div className="pdf-frame-wrapper">
        {!iframeLoaded && (
          <div className="pdf-loading-overlay">
            <div className="pulse-spinner-small"></div>
            <span>Loading answer copy PDF...</span>
          </div>
        )}
        <iframe
          src={viewerUrl}
          title="Candidate Answer Copy"
          className="pdf-iframe"
          onLoad={() => setIframeLoaded(true)}
        />
      </div>
    </div>
  );
}
