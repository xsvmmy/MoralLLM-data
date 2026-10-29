import React, { useState, useEffect } from 'react';
import { getRandomScenario } from '../utils/api';
import { computeVoting, simulateOutcome } from '../utils/moralVoting';
import './StatsPanel.css';

const delay = (ms) => new Promise(r => setTimeout(r, ms));

// ── Legal status badge ──────────────────────────────────────────────────────
function LegalBadge({ tl }) {
  if (!tl || tl === 'None') {
    return <span className="rl-badge badge-amber">No signal</span>;
  }
  if (tl === 'Green') {
    return <span className="rl-badge badge-green">Walk (legal)</span>;
  }
  return <span className="rl-badge badge-red">Don't Walk (illegal)</span>;
}

/**
 * StatsPanel — pure Moral Machine dataset viewer.
 *
 * Shows a scenario, its crowd credences, and what the dataset itself says
 * (the Nash/variance recommendation, and what the crowd actually chose).
 * Deliberately has no RL agent involvement: computeVoting/simulateOutcome
 * are pure client-side functions (see utils/moralVoting.js), so nothing
 * here ever calls a backend agent or updates any Q-table.
 *
 * Props:
 *   scenario    — initial scenario loaded by the parent
 *   dataset     — filename of the currently active CSV dataset, so "Next
 *                 Scenario" stays within it instead of falling back to the
 *                 backend's default dataset
 *   onRLStep        — callback to drive road animation in the AV sim windows
 *   onScenarioChange — (optional) called whenever "Next Scenario" loads a new
 *                      scenario, so the parent's response_id tracking (used
 *                      to keep the LLM section in sync) stays current
 */
function StatsPanel({ scenario, dataset, onRLStep, onScenarioChange }) {
  const [currentScenario, setCurrentScenario] = useState(scenario);
  useEffect(() => { setCurrentScenario(scenario); }, [scenario]);

  const [simulating, setSimulating] = useState(false);
  const [loadingNext, setLoadingNext] = useState(false);
  const [error, setError] = useState(null);

  const vote = currentScenario ? computeVoting(currentScenario.credences) : null;

  // ── Simulate: compute the Nash/variance action and animate it, no network call ──
  const handleSimulate = async () => {
    if (!currentScenario || simulating) return;
    setSimulating(true);
    setError(null);

    try {
      const action  = vote.recommendation;
      const outcome = simulateOutcome(currentScenario, action);
      const simResult = { action, ...outcome };

      onRLStep({ phase: 'deciding',  scenario: currentScenario, result: simResult, episodeNum: null, totalEpisodes: null });
      await delay(650);
      onRLStep({ phase: 'animating', scenario: currentScenario, result: simResult, episodeNum: null, totalEpisodes: null });
      await delay(850);
      onRLStep({ phase: 'result',    scenario: currentScenario, result: simResult, episodeNum: null, totalEpisodes: null });
    } catch (e) {
      setError(e.message || 'Failed to simulate scenario');
      onRLStep({ phase: 'done' });
    } finally {
      setSimulating(false);
    }
  };

  // ── Load a new random scenario ──
  const handleNextScenario = async () => {
    setLoadingNext(true);
    setError(null);
    try {
      const nextSc = await getRandomScenario(dataset);
      setCurrentScenario(nextSc);
      onRLStep({ phase: 'scenario', scenario: nextSc, episodeNum: null, totalEpisodes: null });
      onScenarioChange?.(nextSc);
    } catch (e) {
      setError(e.message || 'Failed to load scenario');
      onRLStep({ phase: 'done' });
    } finally {
      setLoadingNext(false);
    }
  };

  if (!currentScenario) return null;

  const lane2IsBarrier = currentScenario.lane2_is_barrier ?? currentScenario.barrier ?? false;

  return (
    <div className="rl-panel">

      {/* ── Header ── */}
      <div className="rl-panel-header">
        <h3>MM Scenarios</h3>
        <p className="rl-subtitle">
          Browse real Moral Machine dilemmas. This is raw dataset data only, no RL agent involved.
        </p>
      </div>

      {/* ── Controls ── */}
      <div className="rl-section">
        <div className="rl-section-title">Controls</div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <button
            className="rl-btn rl-btn-run"
            onClick={handleSimulate}
            disabled={simulating || loadingNext}
          >
            {simulating ? '⏳ Simulating…' : loadingNext ? '⏳ Loading…' : '▶ Simulate'}
          </button>
          <button
            className="rl-btn rl-btn-next"
            onClick={handleNextScenario}
            disabled={simulating || loadingNext}
          >
            ⏭ Next Scenario
          </button>
        </div>
      </div>

      {error && <div className="rl-error">{error}</div>}

      {/* ── Current Scenario ── */}
      <div className="rl-section">
        <div className="rl-section-title">Current Scenario</div>

        {currentScenario.scenario_type && (
          <div className="rl-scenario-context">
            <span className={`rl-type-badge type-${(currentScenario.scenario_type || 'random').toLowerCase().replace(' ', '-')}`}>
              {currentScenario.scenario_type}
            </span>
            {currentScenario.ped_ped != null && (
              <span className="rl-pedped-badge">
                {currentScenario.ped_ped ? 'Ped vs Ped' : 'Ped vs Passenger'}
              </span>
            )}
          </div>
        )}

        <div className="rl-scenario-info">
          <div className="rl-info-row">
            <span className="rl-label">Response ID</span>
            <span className="rl-value mono">{currentScenario.response_id}</span>
          </div>
          <div className="rl-info-row">
            <span className="rl-label">Pedestrians (lane 1)</span>
            <span className="rl-value">
              {currentScenario.pedestrians.join(', ')}
              <span className="rl-count"> ×{currentScenario.pedestrians.length}</span>
            </span>
          </div>
          <div className="rl-info-row">
            <span className="rl-label">
              {lane2IsBarrier ? 'Barricade (lane 2)' : 'Swerve group (lane 2)'}
            </span>
            <span className="rl-value">
              {currentScenario.passengers.join(', ')}
              {!lane2IsBarrier && <span className="rl-count"> ×{currentScenario.passengers.length}</span>}
            </span>
          </div>
          <div className="rl-info-row">
            <span className="rl-label">Crossing</span>
            <LegalBadge tl={currentScenario.traffic_light} />
          </div>
          {currentScenario.diff_n_chars > 0 && (
            <div className="rl-info-row">
              <span className="rl-label">Size difference</span>
              <span className="rl-value">
                {currentScenario.diff_n_chars} more character{currentScenario.diff_n_chars !== 1 ? 's' : ''} in one lane
              </span>
            </div>
          )}
        </div>
      </div>

      {/* ── Crowd Credences ── */}
      <div className="rl-section">
        <div className="rl-credence-row">
          <span className="rl-credence-label">Stay</span>
          <div className="rl-bar-track">
            <div className="rl-bar deont" style={{ width: `${vote.deont_pct}%` }} />
          </div>
          <span className="rl-credence-pct">{vote.deont_pct}%</span>
        </div>
        <div className="rl-credence-row">
          <span className="rl-credence-label">Swerve</span>
          <div className="rl-bar-track">
            <div className="rl-bar util" style={{ width: `${vote.util_pct}%` }} />
          </div>
          <span className="rl-credence-pct">{vote.util_pct}%</span>
        </div>
        <div className="rl-compare" style={{ marginTop: 12 }}>
          <div className="rl-compare-side">
            <div className="rl-compare-label">Human Choice</div>
            <div className={`rl-compare-choice action-${currentScenario.human_choice}`}>
              {currentScenario.human_choice === 'stay' ? 'Stay' : 'Swerve'}
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}

export default StatsPanel;
