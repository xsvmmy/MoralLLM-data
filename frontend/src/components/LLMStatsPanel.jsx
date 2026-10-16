import React from 'react';
import './StatsPanel.css';

// ── Legal status badge — mirrors StatsPanel's, plus an "unknown" state for
// when no matching Human scenario is loaded to read the signal from. ──
function LegalBadge({ tl }) {
  if (!tl) {
    return <span className="rl-badge badge-amber">Unknown</span>;
  }
  if (tl === 'None') {
    return <span className="rl-badge badge-amber">No signal</span>;
  }
  if (tl === 'Green') {
    return <span className="rl-badge badge-green">Walk (legal)</span>;
  }
  return <span className="rl-badge badge-red">Don't Walk (illegal)</span>;
}

/**
 * LLMStatsPanel — middle section of the stats row.
 *
 * Shows one LLM's stay/swerve judgment for a scenario, loaded from an LLM
 * result CSV (see modules/llm_results_loader.py on the backend) and looked
 * up by the same response_id the Human section currently has loaded, so the
 * two can be compared side by side.
 *
 * Pedestrians/swerve-group/crossing are read from the matched Human
 * scenario (richer, structured data) when the IDs line up; otherwise this
 * falls back to the raw description text the LLM CSV itself carries.
 *
 * Props:
 *   data            — matched LLM result dict, or null if nothing loaded
 *   humanScenario   — the Human section's current scenario, for cross-referencing
 *   loading         — true while a load is in flight
 *   error           — error message string, or null
 */
function LLMStatsPanel({ data, humanScenario, loading, error }) {
  const matchesHuman = !!(data && humanScenario && humanScenario.response_id === data.response_id);

  return (
    <div className="rl-panel">
      <div className="rl-panel-header">
        <h3>LLM Sim</h3>
        <p className="rl-subtitle">
          One LLM's stay/swerve judgment for this scenario, from a CSV of prior results.
        </p>
      </div>

      {loading && (
        <div className="rl-section">
          <p className="rl-hint" style={{ margin: 0 }}>Loading…</p>
        </div>
      )}

      {error && !loading && <div className="rl-error">{error}</div>}

      {!loading && !data && !error && (
        <div className="rl-section">
          <p className="rl-hint" style={{ margin: 0 }}>Press Load CSV above to pick an LLM results dataset.</p>
        </div>
      )}

      {data && !loading && (
        <>
          <div className="rl-section">
            <div className="rl-section-title">Current Scenario</div>

            <div className="rl-scenario-context">
              <span className="rl-type-badge type-llm">{data.model || 'Unknown model'}</span>
              {!matchesHuman && (
                <span className="rl-pedped-badge">Not matched to Human side</span>
              )}
            </div>

            <div className="rl-scenario-info">
              <div className="rl-info-row">
                <span className="rl-label">Response ID</span>
                <span className="rl-value mono">{data.response_id}</span>
              </div>
              <div className="rl-info-row">
                <span className="rl-label">Pedestrians (lane 1)</span>
                <span className="rl-value">
                  {matchesHuman
                    ? `${humanScenario.pedestrians.join(', ')} ×${humanScenario.pedestrians.length}`
                    : data.pedestrians_desc}
                </span>
              </div>
              <div className="rl-info-row">
                <span className="rl-label">Swerve group (lane 2)</span>
                <span className="rl-value">
                  {matchesHuman
                    ? `${humanScenario.passengers.join(', ')} ×${humanScenario.passengers.length}`
                    : data.swerve_desc}
                </span>
              </div>
              <div className="rl-info-row">
                <span className="rl-label">Crossing</span>
                <LegalBadge tl={matchesHuman ? humanScenario.traffic_light : null} />
              </div>
            </div>
          </div>

          <div className="rl-section">
            <div className="rl-compare">
              <div className="rl-compare-side">
                <div className="rl-compare-label">LLM Choice</div>
                <div className={`rl-compare-choice action-${data.llm_judgment}`}>
                  {data.llm_judgment === 'stay' ? 'Stay' : 'Swerve'}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default LLMStatsPanel;
