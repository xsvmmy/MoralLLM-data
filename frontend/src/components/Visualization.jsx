import React, { useState, useEffect, useCallback } from 'react';
import AVSimWindow from './AVSimWindow';
import StatsPanel from './StatsPanel';
import LLMStatsPanel from './LLMStatsPanel';
import LLMDebateStatsPanel from './LLMDebateStatsPanel';
import {
  listDatasets, getRandomScenario, createScenario,
  listLLMDatasets, getLLMResultById, getLLMResultRandom, getLLMDatasetStats,
  listDebateDatasets, getDebateResultById, getDebateResultRandom, getDebateDatasetStats,
} from '../utils/api';
import './Visualization.css';

/**
 * Visualization — top-level layout: three labeled AV-sim windows side by
 * side, driven by the three-section stats row below them.
 *
 * Each window's "Load CSV" picks from its own dataset group: Human browses
 * human-data/ (Moral Machine scenarios), LLM browses LLM-data/ (per-scenario
 * LLM judgments), LLM Debate browses LLM-debate-data/ (per-scenario debate
 * verdicts). The LLM and LLM Debate sections are looked up by the SAME
 * response_id the Human side currently has loaded, and stay in sync
 * whenever that changes, so all three stay comparable. All three road
 * windows still mirror the Human scenario/action for now — only the stats
 * row is independent so far.
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
  const [llmStats, setLlmStats]             = useState(null);
  const [llmLoading, setLlmLoading]         = useState(false);
  const [llmError, setLlmError]             = useState(null);

  // ── LLM debate result state ──
  const [debateDatasets, setDebateDatasets]         = useState([]);
  const [activeDebateDataset, setActiveDebateDataset] = useState(null);
  const [debateData, setDebateData]                 = useState(null);
  const [debateStats, setDebateStats]               = useState(null);
  const [debateLoading, setDebateLoading]           = useState(false);
  const [debateError, setDebateError]               = useState(null);

  // Fetch all three dataset lists once, on mount.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [mmRes, llmRes, debateRes] = await Promise.all([
          listDatasets(), listLLMDatasets(), listDebateDatasets(),
        ]);
        if (!cancelled) {
          setDatasets(mmRes.datasets || []);
          setLlmDatasets(llmRes.datasets || []);
          setDebateDatasets(debateRes.datasets || []);
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

  // Same as above, for the LLM Debate section.
  const syncDebateForResponseId = useCallback(async (responseId, datasetFilename) => {
    if (!datasetFilename || !responseId) return;
    setDebateLoading(true);
    setDebateError(null);
    try {
      const result = await getDebateResultById(datasetFilename, responseId);
      setDebateData(result);
    } catch (err) {
      setDebateData(null);
      setDebateError(err.message || `No debate result for ${responseId}`);
    } finally {
      setDebateLoading(false);
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
      if (activeDebateDataset) syncDebateForResponseId(newScenario.response_id, activeDebateDataset);
    } catch (err) {
      setLoadError(err.message || 'Failed to load scenario');
    } finally {
      setLoadingScenario(false);
    }
  }, [activeLLMDataset, syncLLMForResponseId, activeDebateDataset, syncDebateForResponseId]);

  // StatsPanel's "Next Scenario" loads a new Human scenario internally —
  // this keeps Visualization's response_id (and the LLM/debate sections) in sync.
  const handleHumanScenarioChange = useCallback((newScenario) => {
    setScenario(newScenario);
    if (activeLLMDataset) syncLLMForResponseId(newScenario.response_id, activeLLMDataset);
    if (activeDebateDataset) syncDebateForResponseId(newScenario.response_id, activeDebateDataset);
  }, [activeLLMDataset, syncLLMForResponseId, activeDebateDataset, syncDebateForResponseId]);

  // Load an LLM result — triggered by the LLM window's "Load CSV" menu.
  // Looks up the Human side's current response_id if one is loaded,
  // otherwise falls back to a random row. Also pulls this dataset's overall
  // stay/swerve dispersion (independent of which scenario is shown).
  const handleLoadLLMCSV = useCallback(async (datasetFilename) => {
    setLlmLoading(true);
    setLlmError(null);
    try {
      const [result, stats] = await Promise.all([
        scenario?.response_id
          ? getLLMResultById(datasetFilename, scenario.response_id)
          : getLLMResultRandom(datasetFilename),
        getLLMDatasetStats(datasetFilename),
      ]);
      setLlmData(result);
      setLlmStats(stats);
    } catch (err) {
      setLlmData(null);
      setLlmStats(null);
      setLlmError(err.message || 'Failed to load LLM result');
    } finally {
      setActiveLLMDataset(datasetFilename);
      setLlmLoading(false);
    }
  }, [scenario]);

  // Load an LLM debate result — triggered by the LLM Debate window's
  // "Load CSV" menu. Same lookup-by-response_id + dataset-stats pattern.
  const handleLoadDebateCSV = useCallback(async (datasetFilename) => {
    setDebateLoading(true);
    setDebateError(null);
    try {
      const [result, stats] = await Promise.all([
        scenario?.response_id
          ? getDebateResultById(datasetFilename, scenario.response_id)
          : getDebateResultRandom(datasetFilename),
        getDebateDatasetStats(datasetFilename),
      ]);
      setDebateData(result);
      setDebateStats(stats);
    } catch (err) {
      setDebateData(null);
      setDebateStats(null);
      setDebateError(err.message || 'Failed to load LLM debate result');
    } finally {
      setActiveDebateDataset(datasetFilename);
      setDebateLoading(false);
    }
  }, [scenario]);

  // Driven by StatsPanel — each phase transition updates all three windows.
  const handleSimStep = useCallback((step) => {
    setSimStep(step.phase === 'done' ? null : step);
  }, []);

  const displayScenario = simStep?.scenario ?? scenario;

  // Shared animation TIMING only — which action each window actually shows
  // is computed independently below, from that window's own recorded choice.
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

  // Each window's own recorded choice — the decision depicted in its own
  // CSV, not a shared/derived recommendation.
  const humanAction = scenario?.human_choice === 'swerve' ? 'swerve' : scenario?.human_choice === 'stay' ? 'stay' : undefined;
  const llmAction    = llmData?.llm_judgment === 'swerve' ? 'swerve' : llmData?.llm_judgment === 'stay' ? 'stay' : undefined;
  const debateIsParseError = debateData?.debate_judgment === 'parse_error';
  const debateAction = debateData?.debate_judgment === 'swerve' ? 'swerve' : debateData?.debate_judgment === 'stay' ? 'stay' : undefined;

  const harmedGroupFor = (action) => (
    action === 'stay' ? 'pedestrians' : action === 'swerve' ? 'passengers' : undefined
  );

  // Per-window config: each browses its own dataset group and shows its own
  // recorded decision on the road.
  const windowConfigs = [
    {
      label: 'Human', datasets, activeDataset, onLoadCSV: handleLoadCSV, loading: loadingScenario,
      action: humanAction, harmedGroup: harmedGroupFor(humanAction),
      noVerdictLabel: 'No verdict available',
    },
    {
      label: 'LLM', datasets: llmDatasets, activeDataset: activeLLMDataset, onLoadCSV: handleLoadLLMCSV, loading: llmLoading,
      action: llmAction, harmedGroup: harmedGroupFor(llmAction),
      noVerdictLabel: 'No verdict available',
    },
    {
      label: 'LLM Debate', datasets: debateDatasets, activeDataset: activeDebateDataset, onLoadCSV: handleLoadDebateCSV, loading: debateLoading,
      action: debateAction, harmedGroup: harmedGroupFor(debateAction),
      noVerdictLabel: debateIsParseError ? 'Parse Error' : 'No verdict available',
    },
  ];

  return (
    <div className="visualization container">
      <div className="viz-header">
        <h2>Simulation Visualization</h2>
        {loadError && <span className="viz-load-error">{loadError}</span>}
      </div>

      <div className="sim-windows-grid">
        {windowConfigs.map(({ label, datasets: windowDatasets, activeDataset: windowActiveDataset, onLoadCSV, loading, action, harmedGroup, noVerdictLabel }) => (
          <AVSimWindow
            key={label}
            label={label}
            datasets={windowDatasets}
            activeDataset={windowActiveDataset}
            onLoadCSV={onLoadCSV}
            loadingScenario={loading}
            scenario={displayScenario}
            action={action}
            noVerdictLabel={noVerdictLabel}
            harmedGroup={harmedGroup}
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
            stats={llmStats}
            humanScenario={scenario}
            loading={llmLoading}
            error={llmError}
          />
        </div>
        <div className="stats-col">
          <LLMDebateStatsPanel
            data={debateData}
            stats={debateStats}
            humanScenario={scenario}
            loading={debateLoading}
            error={debateError}
          />
        </div>
      </div>
    </div>
  );
}

export default Visualization;
