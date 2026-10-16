/**
 * Moral Voting Utilities (client-side)
 *
 * Pure-JS port of the harmed-group logic in
 * backend/modules/simulation_logic.py's SimulationEngine.simulate_outcome(),
 * plus a Nash/variance voting heuristic over crowd credences. Used by
 * StatsPanel, which shows what the dataset itself says about a scenario
 * (Nash/variance recommendation, harmed group/count) without any network
 * round-trip, since both are pure functions of data already returned by
 * GET /api/mm/scenarios/random.
 */

/**
 * Compute Nash or variance voting recommendation from moral credences.
 *
 * Nash voting (split >= 0.30, i.e. >= 70/30):
 *   One framework dominates strongly. The recommendation is the dominant
 *   framework's preferred action.
 *
 * Variance voting (split < 0.30, i.e. close to 50/50):
 *   Frameworks are nearly tied. Picks whichever action creates the smaller
 *   total weighted disagreement across both frameworks.
 *
 * @param {{deontological: number, utilitarian: number}} credences
 * @returns {{method: string, recommendation: string, split: number, deont_pct: number, util_pct: number}}
 */
export function computeVoting(credences) {
  const d = credences?.deontological ?? 0.5;
  const u = credences?.utilitarian   ?? 0.5;
  const split = Math.abs(d - u);

  let method, recommendation;
  if (split >= 0.30) {
    method = 'nash';
    recommendation = d > u ? 'stay' : 'swerve';
  } else {
    method = 'variance';
    // cost of "stay"   = u  (utilitarian disagrees)
    // cost of "swerve" = d  (deontological disagrees)
    recommendation = u <= d ? 'stay' : 'swerve';
  }

  return {
    method,
    recommendation,
    split: Math.round(split * 10000) / 10000,
    deont_pct: Math.round(d * 1000) / 10,
    util_pct: Math.round(u * 1000) / 10,
  };
}

/**
 * Resolve which group is harmed by a given action, and the counts on each side.
 *
 * @param {{pedestrians: string[], passengers: string[]}} scenario
 * @param {'stay'|'swerve'} action
 */
export function simulateOutcome(scenario, action) {
  const pedestrians = scenario.pedestrians ?? [];
  const passengers  = scenario.passengers  ?? [];

  if (action === 'stay') {
    return {
      harmed_group: 'pedestrians',
      harmed_count: pedestrians.length,
      saved_group:  'passengers',
      saved_count:  passengers.length,
    };
  }
  return {
    harmed_group: 'passengers',
    harmed_count: passengers.length,
    saved_group:  'pedestrians',
    saved_count:  pedestrians.length,
  };
}
