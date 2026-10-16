"""
Voting Module — Nash and Variance voting over moral theories.

Implements Equations 2–4 from Ecoffet & Lehman (2021):
  - Nash voting:     score[a] = Σ_i C_i * Q_i(a)
  - Variance voting: score[a] = Σ_i C_i * (Q_i(a) − μ_i) / sqrt(σ_i² + ε)

Only two theories are used:
  Deontological → "stay"  action has Q=+1, "swerve" has Q=−1
  Utilitarian   → "stay"  action has Q=−1, "swerve" has Q=+1

Credence dispersion (variance of the two credences) determines which
voting method is applied:
  dispersion > threshold (0.04) → Nash   (one theory clearly dominant)
  dispersion ≤ threshold        → Variance (genuine moral uncertainty)
"""

import math
from typing import Dict

ACTIONS = ["stay", "swerve"]
THEORIES = ["deontological", "utilitarian"]


def compute_q_values() -> Dict[str, Dict[str, float]]:
    """
    Return the fixed Q-value table for the two moral theories.

    Returns:
        {
          "deontological": {"stay": 1.0, "swerve": -1.0},
          "utilitarian":   {"stay": -1.0, "swerve": 1.0}
        }
    """
    return {
        "deontological": {"stay": 1.0, "swerve": -1.0},
        "utilitarian":   {"stay": -1.0, "swerve": 1.0},
    }


def nash_vote(credences: Dict[str, float], q_values: Dict[str, Dict[str, float]]) -> str:
    """
    Nash voting: weighted sum of Q-values across theories.

    score[a] = Σ_i C_i * Q_i(a)
    Returns the action with the highest score; ties broken in favour of "stay".

    Args:
        credences:  {"deontological": C_d, "utilitarian": C_u}
        q_values:   output of compute_q_values()

    Returns:
        "stay" or "swerve"
    """
    scores: Dict[str, float] = {}
    for action in ACTIONS:
        scores[action] = sum(
            credences.get(theory, 0.0) * q_values[theory][action]
            for theory in THEORIES
        )
    return max(ACTIONS, key=lambda a: (scores[a], ACTIONS.index(a) == 0))


def variance_vote(
    credences: Dict[str, float],
    q_values: Dict[str, Dict[str, float]],
    epsilon: float = 1e-6,
) -> str:
    """
    Variance voting: credence-weighted normalised Q-values.

    For each theory i:
        μ_i  = mean(Q_i("stay"), Q_i("swerve"))   — mean across actions
        σ_i² = variance of Q_i values across actions
        score[a] += C_i * (Q_i(a) − μ_i) / sqrt(σ_i² + ε)

    Returns the action with the highest score; ties broken in favour of "stay".

    Args:
        credences:  {"deontological": C_d, "utilitarian": C_u}
        q_values:   output of compute_q_values()
        epsilon:    small constant for numerical stability

    Returns:
        "stay" or "swerve"
    """
    scores: Dict[str, float] = {a: 0.0 for a in ACTIONS}

    for theory in THEORIES:
        q = q_values[theory]
        q_vals = [q[a] for a in ACTIONS]
        mu = sum(q_vals) / len(q_vals)
        var = sum((v - mu) ** 2 for v in q_vals) / len(q_vals)
        denom = math.sqrt(var + epsilon)
        c = credences.get(theory, 0.0)
        for action in ACTIONS:
            scores[action] += c * (q[action] - mu) / denom

    return max(ACTIONS, key=lambda a: (scores[a], ACTIONS.index(a) == 0))


def compute_credence_dispersion(credences: Dict[str, float]) -> float:
    """
    Compute variance of the credence distribution across theories.

    For two theories summing to 1.0:
        Var([C_d, C_u]) = ((C_d − mean)² + (C_u − mean)²) / 2

    High dispersion → one theory dominates → use Nash voting.
    Low  dispersion → genuine uncertainty  → use Variance voting.

    Examples:
        [0.9, 0.1] → 0.16   (one theory clearly dominant)
        [0.5, 0.5] → 0.0    (pure uncertainty)

    Args:
        credences: {"deontological": C_d, "utilitarian": C_u}

    Returns:
        Variance value (float ≥ 0)
    """
    values = [credences.get(t, 0.0) for t in THEORIES]
    n = len(values)
    mean = sum(values) / n
    return sum((v - mean) ** 2 for v in values) / n


def select_voting_method(dispersion: float, threshold: float = 0.04) -> str:
    """
    Choose Nash or Variance voting based on credence dispersion.

    Args:
        dispersion: Output of compute_credence_dispersion()
        threshold:  Boundary value (default 0.04)

    Returns:
        "nash" if dispersion > threshold else "variance"
    """
    return "nash" if dispersion > threshold else "variance"
