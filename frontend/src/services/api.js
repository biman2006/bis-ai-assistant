/**
 * BIS AI Assistant — API service layer
 * Connects to the FastAPI backend for all operations.
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

async function apiFetch(path, options = {}) {
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
  } catch {
    throw new Error('Unable to reach the BIS backend. Start the FastAPI server on http://localhost:8000 and try again.');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

// ── Chat ──────────────────────────────────────────────────────────────────────

export async function sendChat({ query, session_id, language = 'en' }) {
  return apiFetch('/chat', {
    method: 'POST',
    body: JSON.stringify({ query, session_id, language }),
  });
}

// ── Standards ─────────────────────────────────────────────────────────────────

export async function searchStandards(q, limit = 10) {
  return apiFetch(`/standards/search?q=${encodeURIComponent(q)}&limit=${limit}`);
}

// ── QCOs ─────────────────────────────────────────────────────────────────────

export async function searchQCOs(q, limit = 10) {
  return apiFetch(`/qcos/search?q=${encodeURIComponent(q)}&limit=${limit}`);
}

// ── Documents ─────────────────────────────────────────────────────────────────

export async function listDocuments(page = 1, pageSize = 20) {
  return apiFetch(`/documents?page=${page}&page_size=${pageSize}`);
}

export async function uploadDocument(formData) {
  const res = await fetch(`${API_BASE}/documents/upload`, {
    method: 'POST',
    body: formData, // No Content-Type header — let browser set multipart boundary
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Upload error: ${res.status}`);
  }
  return res.json();
}

export async function addDocumentURL({ url, title, source_type = 'BIS', document_type = 'webpage' }) {
  return apiFetch('/documents/url', {
    method: 'POST',
    body: JSON.stringify({ url, title, source_type, document_type }),
  });
}

export async function deleteDocument(id) {
  return apiFetch(`/documents/${id}`, { method: 'DELETE' });
}

export async function reindexDocument(id) {
  return apiFetch(`/documents/${id}/reindex`, { method: 'POST' });
}

// ── Health ────────────────────────────────────────────────────────────────────

export async function getHealth() {
  return apiFetch('/health');
}

// ── Semantic Search ───────────────────────────────────────────────────────────

export async function semanticSearch(query, top_k = 5) {
  return apiFetch('/search', {
    method: 'POST',
    body: JSON.stringify({ query, top_k }),
  });
}
