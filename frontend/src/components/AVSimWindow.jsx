import React, { useState, useRef, useEffect } from 'react';
import CharacterSVG from './CharacterSVG';
import CarSVG from './CarSVG';
import CrossingSignalSVG from './CrossingSignalSVG';

/**
 * AVSimWindow — one labeled AV-sim window ("Human" / "LLM" / "LLM Debate").
 *
 * Renders the two-lane road for whatever scenario/action/harmedGroup/
 * animPhase it's given, plus its own "Load CSV" dropdown. All three windows
 * are currently fed the same values and the same dataset list by
 * Visualization (picking a dataset here loads it into all three — see
 * onLoadCSV), but each instance is self-contained so a future step can give
 * each its own dataset/action/outcome without touching this component.
 *
 * Props:
 *   label           — header text ("Human" | "LLM" | "LLM Debate")
 *   datasets        — string[] of .csv filenames available to load
 *   activeDataset   — filename currently loaded for this window, or null —
 *                     highlighted in the dropdown so it's obvious at a glance
 *   onLoadCSV       — (datasetFilename) => void, called when a menu item is picked
 *   loadingScenario — true while a dataset load is in flight (disables the button)
 *   scenario        — scenario dict (lane1_chars, lane2_chars, traffic_light, …) or null
 *   action          — "stay" | "swerve" | undefined — THIS window's own recorded
 *                      choice (human_choice / llm_judgment / debate_judgment),
 *                      independent of the other two windows
 *   harmedGroup     — "pedestrians" | "passengers" | undefined
 *   animPhase       — "initial" | "action" | "result"
 *   isDeciding      — true while the decision is being computed (badge overlay)
 *   isLoading       — true while the initial scenario is still being fetched
 *   noVerdictLabel  — text shown at the 'result' phase when this window has no
 *                     action yet (no data loaded, or a parse error) — default
 *                     'No verdict available'
 */
function AVSimWindow({
  label, datasets, activeDataset, onLoadCSV, loadingScenario,
  scenario, action, harmedGroup, animPhase, isDeciding, isLoading,
  noVerdictLabel = 'No verdict available',
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  // Close the dropdown on an outside click.
  useEffect(() => {
    if (!menuOpen) return;
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [menuOpen]);

  const handlePick = (filename) => {
    setMenuOpen(false);
    onLoadCSV(filename);
  };

  const toSigState = (tl) => (tl === 'Green' ? 'green' : tl === 'Red' ? 'red' : 'none');

  const lane1Chars     = scenario?.lane1_chars     ?? scenario?.pedestrians ?? [];
  const lane2Chars     = scenario?.lane2_chars     ?? (scenario?.passengers?.filter(p => p !== 'Barricade') ?? []);
  const lane1IsBarrier = scenario?.lane1_is_barrier ?? false;
  const lane2IsBarrier = scenario?.lane2_is_barrier ?? (scenario?.passengers?.includes('Barricade') ?? false);
  const passengersInAV = scenario?.passengers_in_av ?? [];
  const isPedPed        = scenario?.ped_ped ?? false;

  const lane1Signal = toSigState(
    isPedPed ? (scenario?.lane1_traffic_light ?? scenario?.traffic_light) : scenario?.traffic_light
  );
  const lane2Signal = toSigState(isPedPed ? scenario?.lane2_traffic_light : null);

  const avClass = (() => {
    if (animPhase === 'action' || animPhase === 'result') {
      if (action === 'swerve') return 'av-swerving';
      if (action === 'stay')   return 'av-staying';
    }
    return 'av-initial';
  })();

  const isLane1Harmed = animPhase === 'result' && harmedGroup === 'pedestrians';
  const isLane2Harmed = animPhase === 'result' && harmedGroup === 'passengers';
  const isAVHarmed    = (isLane1Harmed && lane1IsBarrier) || (isLane2Harmed && lane2IsBarrier);

  return (
    <div className="sim-window">
      <div className="sim-window-label">{label}</div>

      <div className="sim-window-load" ref={menuRef}>
        <button
          className="btn-load-csv-window"
          onClick={() => setMenuOpen((open) => !open)}
          disabled={loadingScenario || !datasets.length}
          title={activeDataset ? `Loaded: ${activeDataset}` : 'Load a scenario from a CSV dataset'}
        >
          {loadingScenario ? 'Loading…' : 'Load CSV'} <span className="btn-load-csv-caret">▾</span>
        </button>

        {menuOpen && (
          <div className="sim-window-dropdown">
            {datasets.length === 0 ? (
              <div className="sim-window-dropdown-empty">No CSV files found</div>
            ) : (
              datasets.map((filename) => {
                const isActive = filename === activeDataset;
                return (
                  <button
                    key={filename}
                    className={`sim-window-dropdown-item${isActive ? ' sim-window-dropdown-item-active' : ''}`}
                    onClick={() => handlePick(filename)}
                  >
                    <span className="sim-window-dropdown-check">{isActive ? '✓' : ''}</span>
                    {filename}
                  </button>
                );
              })
            )}
          </div>
        )}
      </div>

      <div className="road-container">
        <div className="road-lane-divider" />
        <div className="road-dir-arrow road-dir-1">▼</div>
        <div className="road-dir-arrow road-dir-2">▼</div>
        <div className="road-crosswalk" />

        {scenario && (
          <div className={`road-group road-group-1 ${isLane1Harmed && !lane1IsBarrier ? 'road-group-harmed' : ''}`}>
            <div className="road-group-chars">
              {lane1IsBarrier
                ? <><CharacterSVG type="Barricade" size={32} /><CharacterSVG type="Barricade" size={32} /></>
                : lane1Chars.map((p, i) => (
                    <CharacterSVG key={i} type={p} size={32} fill={isLane1Harmed ? '#ef4444' : '#e8e8e8'} />
                  ))
              }
            </div>
            {isLane1Harmed && !lane1IsBarrier && (
              <div className="road-harm-label">✕ Impact</div>
            )}
          </div>
        )}

        {scenario && (
          <>
            <div className="road-signal road-signal-left">
              <CrossingSignalSVG state={lane1Signal} height={48} />
            </div>
            <div className="road-signal road-signal-right">
              <CrossingSignalSVG state={isPedPed ? lane2Signal : lane1Signal} height={48} />
            </div>
          </>
        )}

        {scenario && isPedPed && (
          <div className="road-crosswalk-median" />
        )}

        {scenario && (
          <div className={`road-group road-group-2 ${isLane2Harmed && !lane2IsBarrier ? 'road-group-harmed' : ''}`}>
            <div className="road-group-chars">
              {lane2IsBarrier
                ? <><CharacterSVG type="Barricade" size={32} /><CharacterSVG type="Barricade" size={32} /></>
                : lane2Chars.map((p, i) => (
                    <CharacterSVG key={i} type={p} size={32} fill={isLane2Harmed ? '#ef4444' : '#e8e8e8'} />
                  ))
              }
            </div>
            {isLane2Harmed && !lane2IsBarrier && (
              <div className="road-harm-label">✕ Impact</div>
            )}
          </div>
        )}

        <div className={`road-av ${avClass} ${isAVHarmed ? 'road-av-harmed' : ''}`}>
          {!isPedPed && passengersInAV.length > 0 && (
            <div className="av-cabin">
              {passengersInAV.map((p, i) => (
                <CharacterSVG key={i} type={p} size={16} fill="#93c5fd" />
              ))}
            </div>
          )}
          <CarSVG width={34} harmed={isAVHarmed} />
        </div>

        {isLoading && (
          <div className="road-empty-overlay">
            <span>Loading scenario…</span>
          </div>
        )}

        {!isLoading && !scenario && (
          <div className="road-empty-overlay">
            <span>Press Load CSV</span>
          </div>
        )}

        {!isLoading && scenario && animPhase === 'initial' && !isDeciding && (
          <div className="road-idle-overlay">
            <span>Press Simulate below</span>
          </div>
        )}

        {animPhase === 'result' && (
          <div className="road-result-overlay">
            {action === 'stay'
              ? 'Stayed in Lane 1'
              : action === 'swerve'
                ? 'Swerved to Lane 2'
                : noVerdictLabel}
          </div>
        )}

        {isDeciding && (
          <div className="road-deciding-badge">Deciding…</div>
        )}
      </div>
    </div>
  );
}

export default AVSimWindow;
