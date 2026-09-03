import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ExternalLink, BookOpen, AlertTriangle } from 'lucide-react';

// ── Intent label map ──────────────────────────────────────────────────────────
const INTENT_LABELS = {
  GENERAL_BIS: 'BIS Overview',
  STANDARD_SEARCH: 'Standard Search',
  PRODUCT_STANDARD: 'Product Standard',
  MANDATORY_CERTIFICATION: 'Mandatory Certification',
  QCO: 'Quality Control Order',
  CERTIFICATION_PROCESS: 'Certification Process',
  LICENCE: 'Licence',
  BIS_MARK: 'BIS Mark',
  CONSUMER_QUERY: 'Consumer Query',
  MANUFACTURER_QUERY: 'Manufacturer Query',
  DOCUMENT_SEARCH: 'Document Search',
  REGULATORY_QUERY: 'Regulatory',
  UNKNOWN: 'General',
};

// ── Source Card ────────────────────────────────────────────────────────────────
function SourceCard({ source }) {
  const badgeClass = source.source_type === 'BIS' ? 'bis' :
                     source.source_type === 'GOVERNMENT' ? 'gov' : 'other';
  const content = (
    <div className="source-card">
      <span className={`source-badge ${badgeClass}`}>{source.source_type}</span>
      <div className="source-info">
        <div className="source-name">{source.title}</div>
        <div className="source-meta">
          {source.is_number && <span>IS: {source.is_number} · </span>}
          {source.section && <span>{source.section} · </span>}
          {source.page && <span>Page {source.page} · </span>}
          {source.last_verified && <span>Verified: {source.last_verified}</span>}
          {source.relevance_score != null && (
            <span> · Score: {(source.relevance_score * 100).toFixed(0)}%</span>
          )}
        </div>
      </div>
      <ExternalLink size={13} className="source-arrow" />
    </div>
  );

  if (source.url) {
    return (
      <a href={source.url} target="_blank" rel="noopener noreferrer" style={{ display: 'block', textDecoration: 'none' }}>
        {content}
      </a>
    );
  }
  return content;
}

// ── Product Info Card ──────────────────────────────────────────────────────────
function ProductInfoCard({ info }) {
  if (!info) return null;
  return (
    <div className="product-info-card">
      <div className="product-info-title">
        <BookOpen size={13} />
        Product Compliance Overview
      </div>
      <div className="product-flow">
        {info.product && (
          <div className="flow-row">
            <span className="flow-label">Product</span>
            <span className="flow-value">{info.product}</span>
          </div>
        )}
        {info.product && <div className="flow-arrow">↓</div>}
        {info.applicable_standard && (
          <div className="flow-row">
            <span className="flow-label">Applicable Standard</span>
            <span className="flow-value">{info.applicable_standard}</span>
          </div>
        )}
        {info.standard_title && (
          <div className="flow-row">
            <span className="flow-label">Standard Title</span>
            <span className="flow-value">{info.standard_title}</span>
          </div>
        )}
        {info.certification_scheme && (
          <div className="flow-row">
            <span className="flow-label">Certification Scheme</span>
            <span className="flow-value">{info.certification_scheme}</span>
          </div>
        )}
        {info.qco_status && (
          <>
            <div className="flow-arrow">↓</div>
            <div className="flow-row">
              <span className="flow-label">QCO Status</span>
              <span className="flow-value">{info.qco_status}</span>
            </div>
          </>
        )}
        {info.mandatory_status && (
          <>
            <div className="flow-arrow">↓</div>
            <div className="flow-row">
              <span className="flow-label">Certification Status</span>
              <span className={`flow-value ${info.mandatory_status?.toLowerCase().includes('mandatory') ? 'mandatory' : info.mandatory_status?.toLowerCase().includes('voluntary') ? 'voluntary' : ''}`}>
                {info.mandatory_status}
              </span>
            </div>
          </>
        )}
        {info.effective_date && (
          <div className="flow-row">
            <span className="flow-label">Effective Date</span>
            <span className="flow-value">{info.effective_date}</span>
          </div>
        )}
        {info.next_steps?.length > 0 && (
          <>
            <div className="flow-arrow">↓</div>
            <div className="flow-row" style={{ flexDirection: 'column', alignItems: 'flex-start' }}>
              <span className="flow-label" style={{ marginBottom: 6 }}>Next Steps</span>
              <ol style={{ paddingLeft: 18, fontSize: 13, lineHeight: 1.6, color: 'var(--color-gray-700)' }}>
                {info.next_steps.map((step, i) => <li key={i}>{step}</li>)}
              </ol>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ── Chat Message ───────────────────────────────────────────────────────────────
export default function ChatMessage({ message }) {
  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';

  const confidenceClass = message.confidence_level
    ? `badge-confidence-${message.confidence_level.toLowerCase()}`
    : 'badge-confidence-none';

  const time = message.timestamp
    ? new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '';

  return (
    <div className={`chat-message ${isUser ? 'user' : 'assistant'}`}>
      {!isUser && (
        <div className="message-avatar avatar-assistant">BIS</div>
      )}

      <div className="message-content-wrapper">
        <div className="message-meta">
          <span className="message-role">{isUser ? 'You' : 'BIS Assistant'}</span>
          {time && <span className="message-time">{time}</span>}
          {isAssistant && message.latency_ms && (
            <span className="message-time">{(message.latency_ms / 1000).toFixed(1)}s</span>
          )}
        </div>

        <div className="message-bubble">
          <div className="markdown-content">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>

          {/* Product info card */}
          {isAssistant && message.product_info && (
            <ProductInfoCard info={message.product_info} />
          )}

          {/* Badges */}
          {isAssistant && (message.intent || message.confidence_level) && (
            <div className="message-badges">
              {message.intent && message.intent !== 'UNKNOWN' && (
                <span className="badge badge-intent">
                  {INTENT_LABELS[message.intent] || message.intent}
                </span>
              )}
              {message.confidence_level && (
                <span className={`badge ${confidenceClass}`} title={message.confidence_reason || undefined}>
                  {message.confidence_level.charAt(0).toUpperCase() + message.confidence_level.slice(1)} confidence
                  {message.confidence != null ? ` (${(message.confidence * 100).toFixed(0)}%)` : ''}
                </span>
              )}
              {message.retrieved_chunks != null && (
                <span className="badge" style={{ background: 'var(--color-gray-100)', color: 'var(--color-gray-500)', border: '1px solid var(--color-gray-200)' }}>
                  {message.retrieved_chunks} sources retrieved
                </span>
              )}
            </div>
          )}

          {/* Sources */}
          {isAssistant && message.sources?.length > 0 && (
            <div className="sources-section">
              <div className="sources-title">
                <BookOpen size={11} />
                Official Sources
              </div>
              <div className="source-cards">
                {message.sources.map((src, i) => (
                  <SourceCard key={i} source={src} />
                ))}
              </div>
            </div>
          )}

          {/* Disclaimer for regulatory content */}
          {isAssistant && message.disclaimer && (
            <div style={{ marginTop: 12, padding: '8px 12px', background: 'var(--color-warning-50)', border: '1px solid var(--color-warning-100)', borderRadius: 'var(--radius-sm)', fontSize: 11, color: 'var(--color-warning-600)', display: 'flex', gap: 7, alignItems: 'flex-start' }}>
              <AlertTriangle size={12} style={{ marginTop: 1, flexShrink: 0 }} />
              <span>{message.disclaimer}</span>
            </div>
          )}
        </div>
      </div>

      {isUser && (
        <div className="message-avatar avatar-user">U</div>
      )}
    </div>
  );
}
