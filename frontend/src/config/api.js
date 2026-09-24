/**
 * Centralized API Configuration & Endpoints Module
 *
 * Configured via environment variables:
 * - VITE_API_BASE_URL (primary)
 * - VITE_API_URL / VITE_BACKEND_URL (fallbacks)
 *
 * Defaults to empty string (relative paths for Vite proxy during local development).
 */

const rawBaseUrl =
  import.meta.env.VITE_API_BASE_URL ??
  import.meta.env.VITE_API_URL ??
  import.meta.env.VITE_BACKEND_URL ??
  '';

/**
 * Normalized API Base URL with trailing slashes stripped.
 * e.g. "https://answer-writing-evaluation.onrender.com"
 */
export const API_BASE_URL = (typeof rawBaseUrl === 'string' ? rawBaseUrl.trim() : '').replace(/\/+$/, '');

/**
 * Builds a complete URL for a given API endpoint path.
 *
 * @param {string} path - Endpoint path, e.g. "/api/evaluations"
 * @returns {string} Fully qualified URL or relative path
 */
export function getApiUrl(path) {
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  if (!API_BASE_URL) {
    return cleanPath;
  }
  return `${API_BASE_URL}${cleanPath}`;
}

/**
 * Resolves PDF URLs that might be returned as relative paths from the backend.
 * Full URLs (such as Supabase storage links or blob URLs) are preserved as-is.
 *
 * @param {string|null|undefined} url
 * @returns {string|null}
 */
export function resolvePdfUrl(url) {
  if (!url) return null;
  if (url.startsWith('blob:') || url.startsWith('http://') || url.startsWith('https://') || url.startsWith('data:')) {
    return url;
  }
  return getApiUrl(url);
}

/**
 * Dictionary of all backend API endpoints.
 */
export const API_ENDPOINTS = {
  health: getApiUrl('/api/health'),
  evaluations: getApiUrl('/api/evaluations'),
  evaluationById: (evalId) => getApiUrl(`/api/evaluations/${evalId}`),
  evaluate: getApiUrl('/api/evaluate'),
  evaluateSample: getApiUrl('/api/evaluate-sample'),
};

/**
 * Returns a human-friendly label of the active backend connection.
 */
export function getBackendHostLabel() {
  if (!API_BASE_URL) {
    return 'Local Proxy';
  }
  try {
    const url = new URL(API_BASE_URL);
    return url.hostname;
  } catch {
    return API_BASE_URL;
  }
}
