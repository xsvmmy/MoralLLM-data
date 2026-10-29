/**
 * API Client Utilities
 *
 * All HTTP requests to the backend API go through fetchAPI().
 */

// Empty string routes requests through Vite's proxy (see vite.config.js)
// avoiding CORS issues regardless of which port Vite picks.
const API_BASE_URL = import.meta.env.VITE_API_URL || '';

/**
 * FastAPI error bodies carry `detail` as a plain string, a Pydantic 422
 * validation list ([{loc, msg, type}, …]), or our own {message, errors}
 * shape (see scenario_config.validate_scenario). Normalize all three into a
 * readable string instead of letting `new Error(detail)` stringify an
 * object into "[object Object]".
 */
function extractErrorMessage(detail) {
  if (!detail) return null;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg || JSON.stringify(d)).join(', ');
  }
  if (typeof detail === 'object') {
    if (detail.message) {
      return detail.errors ? `${detail.message}: ${detail.errors.join(', ')}` : detail.message;
    }
    return JSON.stringify(detail);
  }
  return String(detail);
}

async function fetchAPI(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  try {
    const response = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(extractErrorMessage(errorData.detail) || `HTTP error! status: ${response.status}`);
    }

    if (response.status === 204) return null;
    return await response.json();
  } catch (error) {
    console.error(`API Error (${endpoint}):`, error);
    throw error;
  }
}

// ── Characters ──────────────────────────────────────────────────────────────

export async function fetchCharacters() {
  return fetchAPI('/api/characters');
}

// ── Scenario CRUD ────────────────────────────────────────────────────────────

export async function createScenario(scenarioData) {
  return fetchAPI('/api/scenarios', { method: 'POST', body: JSON.stringify(scenarioData) });
}

export async function fetchScenarios(skip = 0, limit = 100) {
  return fetchAPI(`/api/scenarios?skip=${skip}&limit=${limit}`);
}

export async function fetchScenario(scenarioId) {
  return fetchAPI(`/api/scenarios/${scenarioId}`);
}

export async function updateScenario(scenarioId, updateData) {
  return fetchAPI(`/api/scenarios/${scenarioId}`, { method: 'PUT', body: JSON.stringify(updateData) });
}

export async function deleteScenario(scenarioId) {
  return fetchAPI(`/api/scenarios/${scenarioId}`, { method: 'DELETE' });
}

// ── Simulation ───────────────────────────────────────────────────────────────

export async function simulateScenario(scenarioId, action) {
  return fetchAPI(`/api/scenarios/${scenarioId}/simulate?action=${action}`, { method: 'POST' });
}

export async function fetchScenarioOutcome(scenarioId) {
  return fetchAPI(`/api/scenarios/${scenarioId}/outcome`);
}

// ── Statistics / Export ──────────────────────────────────────────────────────

export async function fetchStatistics() {
  return fetchAPI('/api/statistics');
}

export async function exportScenarios() {
  return fetchAPI('/api/export/json');
}

// ── Moral Machine CSV scenarios ──────────────────────────────────────────────

/**
 * List the .csv filenames available at the project root to load scenarios from.
 * Returns { datasets: string[] }.
 */
export async function listDatasets() {
  return fetchAPI('/api/mm/datasets');
}

/**
 * Fetch a random CSV-sourced Moral Machine scenario.
 *
 * @param {string} [datasetFilename] - which .csv to load from (defaults to
 *   filtered_responses.csv on the backend if omitted).
 */
export async function getRandomScenario(datasetFilename) {
  const query = datasetFilename ? `?dataset=${encodeURIComponent(datasetFilename)}` : '';
  return fetchAPI(`/api/mm/scenarios/random${query}`);
}

// ── LLM result CSVs ──────────────────────────────────────────────────────────

/**
 * List the .csv filenames available at the project root that already carry
 * a per-scenario LLM judgment. Returns { datasets: string[] }.
 */
export async function listLLMDatasets() {
  return fetchAPI('/api/llm/datasets');
}

/**
 * Fetch a random row from an LLM result dataset.
 */
export async function getLLMResultRandom(datasetFilename) {
  return fetchAPI(`/api/llm/scenarios/random?dataset=${encodeURIComponent(datasetFilename)}`);
}

/**
 * Fetch the LLM result for a specific response_id — used to line up the LLM
 * section with whatever scenario the Human side currently has loaded.
 */
export async function getLLMResultById(datasetFilename, responseId) {
  return fetchAPI(
    `/api/llm/scenarios/by-id?dataset=${encodeURIComponent(datasetFilename)}&response_id=${encodeURIComponent(responseId)}`
  );
}

/**
 * Fetch this model's stay/swerve dispersion across its whole dataset
 * (not scenario-specific — a summary of the loaded CSV as a whole).
 */
export async function getLLMDatasetStats(datasetFilename) {
  return fetchAPI(`/api/llm/scenarios/stats?dataset=${encodeURIComponent(datasetFilename)}`);
}

// ── LLM debate result CSVs ───────────────────────────────────────────────────

/**
 * List the .csv filenames available at the project root carrying per-scenario
 * LLM debate verdicts. Returns { datasets: string[] }.
 */
export async function listDebateDatasets() {
  return fetchAPI('/api/debate/datasets');
}

/**
 * Fetch a random row from an LLM debate result dataset.
 */
export async function getDebateResultRandom(datasetFilename) {
  return fetchAPI(`/api/debate/scenarios/random?dataset=${encodeURIComponent(datasetFilename)}`);
}

/**
 * Fetch the debate result for a specific response_id — used to line up the
 * LLM Debate section with whatever scenario the Human side currently has loaded.
 */
export async function getDebateResultById(datasetFilename, responseId) {
  return fetchAPI(
    `/api/debate/scenarios/by-id?dataset=${encodeURIComponent(datasetFilename)}&response_id=${encodeURIComponent(responseId)}`
  );
}

/**
 * Fetch this debate's stay/swerve dispersion across its whole dataset
 * (not scenario-specific — a summary of the loaded CSV as a whole).
 */
export async function getDebateDatasetStats(datasetFilename) {
  return fetchAPI(`/api/debate/scenarios/stats?dataset=${encodeURIComponent(datasetFilename)}`);
}
