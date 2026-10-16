import React, { useState, useEffect, useCallback } from 'react';
import AVSimWindow from './AVSimWindow';
import StatsPanel from './StatsPanel';
import LLMStatsPanel from './LLMStatsPanel';
import {
  listDatasets, getRandomScenario, createScenario,
  listLLMDatasets, getLLMResultById, getLLMResultRandom,
} from '../utils/api';
import './Visualization.css';

/**
 * Visualization — top-level layout: three labeled AV-sim windows side by
 * side, driven by the three-section stats row below them.
 *
 * The Human window's "Load CSV" picks a Moral Machine scenario CSV; the LLM
 * window's picks an LLM-result CSV, looked up by the SAME response_id the
 * Human side currently has loaded (so the two sections stay comparable).
 * LLM Debate is wired up but empty for now. All three road windows still
 * mirror the Human scenario/action for now — only the stats row's LLM
 * section is independent so far.
 */
function Visualization() {
  // ── Human (Moral Machine) state ──
  const [datasets, setDatasets]             = useState([]);
  const [activeDataset, setActiveDataset]   = useState(null);
  const [scenario, setScenario]             = useState(null);
  const [loadingScenario, setLoadingScenario] = useState(false);
  const [loadError, setLoadError]           = useState(null);
  const [simStep, setSimStep]               = useState(null);

  // ── LLM result state ──
  const [llmDatasets, setLlmDatasets]       = useState([]);
  const [activeLLMDataset, setActiveLLMDataset] = useState(null);
  const [llmData, setLlmData]               = useState(null);
  const [llmLoading, setLlmLoading]         = useState(false);
  const [llmError, setLlmError]             = useState(null);

  // Fetch both dataset lists once, on mount.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [mmRes, llmRes] = await Promise.all([listDatasets(), listLLMDatasets()]);
        if (!cancelled) {
          setDatasets(mmRes.datasets || []);
          setLlmDatasets(llmRes.datasets || []);
        }
      } catch (err) {
        if (!cancelled) setLoadError(err.message || 'Failed to list datasets');
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Re-fetch the LLM result for a given response_id against whichever LLM
  // dataset is active — keeps the LLM section lined up with the Human side.
  const syncLLMForResponseId = useCallback(async (responseId, datasetFilename) => {
    if (!datasetFilename || !responseId) return;
    setLlmLoading(true);
    setLlmError(null);
    try {
      const result = await getLLMResultById(datasetFilename, responseId);
      setLlmData(result);
    } catch (err) {
      setLlmData(null);
      setLlmError(err.message || `No LLM result for ${responseId}`);
    } finally {
      setLlmLoading(false);
    }
  }, []);

  // Load a random Human scenario from the chosen dataset — triggered by the
  // Human window's "Load CSV" menu.
  const handleLoadCSV = useCallback(async (datasetFilename) => {
    setLoadingScenario(true);
    setLoadError(null);
    setSimStep(null);
    try {
      const csvScenario = await getRandomScenario(datasetFilename);
      const created = await createScenario({
        passengers:    csvScenario.passengers,
        pedestrians:   csvScenario.pedestrians,
        traffic_light: csvScenario.traffic_light,
      });
      const newScenario = { ...csvScenario, ...created };
      setScenario(newScenario);
      setActiveDataset(datasetFilename);
      if (activeLLMDataset) syncLLMForResponseId(newScenario.response_id, activeLLMDataset);
    } catch (err) {
      setLoadError(err.message || 'Failed to load scenario');
    } finally {
      setLoadingScenario(false);
    }
  }, [activeLLMDataset, syncLLMForResponseId]);

  // StatsPanel's "Next Scenario" loads a new Human scenario internally —
  // this keeps Visualization's response_id (and the LLM section) in sync.
  const handleHumanScenarioChange = useCallback((newScenario) => {
    setScenario(newScenario);
    if (activeLLMDataset) syncLLMForResponseId(newScenario.response_id, activeLLMDataset);
  }, [activeLLMDataset, syncLLMForResponseId]);

  // Load an LLM result — triggered by the LLM window's "Load CSV" menu.
  // Looks up the Human side's current response_id if one is loaded,
  // otherwise falls back to a random row.
  const handleLoadLLMCSV = useCallback(async (datasetFilename) => {
    setLlmLoading(true);
    setLlmError(null);
    try {
      const result = scenario?.response_id
        ? await getLLMResultById(datasetFilename, scenario.response_id)
        : await getLLMResultRandom(datasetFilename);
      setLlmData(result);
    } catch (err) {
      setLlmData(null);
      setLlmError(err.message || 'Failed to load LLM result');
    } finally {
      setActiveLLMDataset(datasetFilename);
      setLlmLoading(false);
    }
  }, [scenario]);

  // Driven by StatsPanel — each phase transition updates all three windows.
  const handleSimStep = useCallback((step) => {
    setSimStep(step.phase === 'done' ? null : step);
  }, []);

  const displayScenario    = simStep?.scenario ?? scenario;
  const displayAction      = simStep?.result?.action;
  const displayHarmedGroup = simStep?.result?.harmed_group;

  const activeAnimPhase = (() => {
    if (!simStep) return 'initial';
    switch (simStep.phase) {
      case 'scenario':  return 'initial';
      case 'deciding':
      case 'animating': return 'action';
      case 'result':    return 'result';
      default:          return 'initial';
    }
  })();

  // Per-window config: Human and LLM Debate browse Moral Machine CSVs (for
  // now — LLM Debate isn't wired to anything yet), LLM browses LLM result CSVs.
  const windowConfigs = [
    { label: 'Human',      datasets,     onLoadCSV: handleLoadCSV,    loading: loadingScenario },
    { label: 'LLM',        datasets: llmDatasets, onLoadCSV: handleLoadLLMCSV, loading: llmLoading },
    { label: 'LLM Debate', datasets: [], onLoadCSV: () => {},         loading: false },
  ];

  return (
    <div className="visualization container">
      <div className="viz-header">
        <h2>Simulation Visualization</h2>
        {loadError && <span className="viz-load-error">{loadError}</span>}
      </div>

      <div className="sim-windows-grid">
        {windowConfigs.map(({ label, datasets: windowDatasets, onLoadCSV, loading }) => (
          <AVSimWindow
            key={label}
            label={label}
            datasets={windowDatasets}
            onLoadCSV={onLoadCSV}
            loadingScenario={loading}
            scenario={displayScenario}
            action={displayAction}
            harmedGroup={displayHarmedGroup}
            animPhase={activeAnimPhase}
            isDeciding={simStep?.phase === 'deciding'}
            isLoading={loadingScenario && !displayScenario}
          />
        ))}
      </div>

      <div className="stats-grid">
        <div className="stats-col">
          {scenario && (
            <StatsPanel
              scenario={scenario}
              dataset={activeDataset}
              onRLStep={handleSimStep}
              onScenarioChange={handleHumanScenarioChange}
            />
          )}
        </div>
        <div className="stats-col">
          <LLMStatsPanel
            data={llmData}
            humanScenario={scenario}
            loading={llmLoading}
            error={llmError}
          />
        </div>
        <div className="stats-col">
          <div className="rl-panel">
            <div className="rl-panel-header">
              <h3>LLM Debate</h3>
              <p className="rl-subtitle">Coming soon.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Visualization;
