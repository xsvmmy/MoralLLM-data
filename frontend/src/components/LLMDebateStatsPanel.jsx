import React from 'react';
import './StatsPanel.css';

// ── Legal status badge — mirrors LLMStatsPanel's, with an "unknown" state
// for when no matching Human scenario is loaded to read the signal from. ──
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
 * LLMDebateStatsPanel — rightmost section of the stats row.
 *
 * Shows a multi-LLM debate's final stay/swerve verdict for a scenario,
 * loaded from an LLM debate result CSV (see modules/llm_debate_loader.py on
 * the backend) and looked up by the same response_id the Human section
 * currently has loaded, so all three sections stay comparable.
 *
 * Pedestrians/swerve-group/crossing are read from the matched Human
 * scenario (richer, structured data) when the IDs line up; otherwise this
 * falls back to the raw description text the debate CSV itself carries.
 *
 * Props:
 *   data            — matched debate result dict, or null if nothing loaded
 *   stats           — { total, stay_count, swerve_count, parse_error_count,
 *                       stay_pct, swerve_pct } for the whole loaded dataset
 *                       (not scenario-specific), or null
 *   humanScenario   — the Human section's current scenario, for cross-referencing
 *   loading         — true while a load is in flight
 *   error           — error message string, or null
 */
function LLMDebateStatsPanel({ data, stats, humanScenario, loading, error }) {
  const matchesHuman = !!(data && humanScenario && humanScenario.response_id === data.response_id);
  const isParseError = data?.debate_judgment === 'parse_error';

  return (
    <div className="rl-panel">
      <div className="rl-panel-header">
        <h3>LLM Debate</h3>
        <p className="rl-subtitle">
          A multi-LLM debate's final stay/swerve verdict for this scenario.
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
          <p className="rl-hint" style={{ margin: 0 }}>Press Load CSV above to pick an LLM debate dataset.</p>
        </div>
      )}

      {data && !loading && (
        <>
          <div className="rl-section">
            <div className="rl-section-title">Current Scenario</div>

            <div className="rl-scenario-context">
              <span className="rl-type-badge type-debate">{data.model || 'Unknown model'}</span>
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

          {stats && (
            <div className="rl-section">
              <div className="rl-credence-row">
                <span className="rl-credence-label">Stay</span>
                <div className="rl-bar-track">
                  <div className="rl-bar deont" style={{ width: `${stats.stay_pct}%` }} />
                </div>
                <span className="rl-credence-pct">{stats.stay_pct}%</span>
              </div>
              <div className="rl-credence-row">
                <span className="rl-credence-label">Swerve</span>
                <div className="rl-bar-track">
                  <div className="rl-bar util" style={{ width: `${stats.swerve_pct}%` }} />
                </div>
                <span className="rl-credence-pct">{stats.swerve_pct}%</span>
              </div>
            </div>
          )}

          <div className="rl-section">
            <div className="rl-compare">
              <div className="rl-compare-side">
                <div className="rl-compare-label">LLM Debate Choice</div>
                {isParseError ? (
                  <div className="rl-compare-choice action-parse-error">Parse Error</div>
                ) : (
                  <div className={`rl-compare-choice action-${data.debate_judgment}`}>
                    {data.debate_judgment === 'stay' ? 'Stay' : 'Swerve'}
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default LLMDebateStatsPanel;
