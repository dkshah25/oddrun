"""Candidate selection, prioritization, and perturbation experiment runner."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from oddrun.execution import (
    BehaviorSignature,
    ExecutionResult,
    ExecutionStatus,
    run_command_subprocess,
)
from oddrun.models import SnapshotDiff
from oddrun.security import is_sensitive_key


class CandidateTier(Enum):
    """Safety tiers for environmental candidate perturbation."""

    TIER_1_SAFE = "TIER_1_SAFE"
    TIER_2_PATH = "TIER_2_PATH"
    TIER_3_OBSERVED = "TIER_3_OBSERVED"


class OutcomeClassification(Enum):
    """Outcome classification of an experiment attempt."""

    BASELINE_MATCH = "BASELINE_MATCH"
    TARGET_MATCH = "TARGET_MATCH"
    BEHAVIOR_CHANGE = "BEHAVIOR_CHANGE"
    UNSTABLE_EXPERIMENT = "UNSTABLE_EXPERIMENT"
    EXPERIMENT_ERROR = "EXPERIMENT_ERROR"
    TIMEOUT = "TIMEOUT"


@dataclass(frozen=True)
class Candidate:
    """An environmental factor hypothesis for causal experiment."""

    category: str
    key: str
    baseline_value: str | None
    target_value: str | None
    tier: CandidateTier

    @property
    def is_perturbable(self) -> bool:
        return self.tier in (CandidateTier.TIER_1_SAFE, CandidateTier.TIER_2_PATH)


@dataclass(frozen=True)
class CandidateMatrix:
    """Categorized candidates extracted from environment diffs."""

    eligible_candidates: list[Candidate]
    excluded_candidates: list[Candidate]


@dataclass(frozen=True)
class ExperimentOutcome:
    """The result of executing perturbation runs for a single Candidate."""

    candidate: Candidate
    exploratory_result: ExecutionResult
    confirmation_results: list[ExecutionResult]
    outcome_classification: OutcomeClassification
    matched_target: bool

    @property
    def total_runs(self) -> int:
        return 1 + len(self.confirmation_results)


def classify_candidate_tier(
    category: str, key: str, target_val: str | None
) -> CandidateTier:
    """Classify a difference item into safety tiers based on risk profile."""
    if category != "environment" and category != "system":
        return CandidateTier.TIER_3_OBSERVED

    key_upper = key.upper()

    if key_upper in ("PATH", "PYTHONPATH", "PYTHONHOME"):
        return CandidateTier.TIER_2_PATH

    if key_upper in ("TZ", "LANG") or key_upper.startswith("LC_"):
        return CandidateTier.TIER_1_SAFE

    if category == "system" and key == "cwd":
        if target_val and os.path.exists(target_val):
            return CandidateTier.TIER_1_SAFE
        return CandidateTier.TIER_3_OBSERVED

    if category == "environment":
        # Safe application env vars (non-sensitive)
        if not is_sensitive_key(key):
            return CandidateTier.TIER_1_SAFE

    return CandidateTier.TIER_3_OBSERVED


def rank_candidates(candidates: list[Candidate]) -> list[Candidate]:
    """Sort candidates deterministically based on priority policies."""

    def priority_key(cand: Candidate) -> tuple[int, str]:
        key_upper = cand.key.upper()
        if key_upper == "TZ":
            return (0, cand.key)
        if key_upper == "LANG" or key_upper.startswith("LC_"):
            return (1, cand.key)
        if cand.category == "environment" and cand.tier == CandidateTier.TIER_1_SAFE:
            return (2, cand.key)
        if cand.key == "cwd":
            return (3, cand.key)
        if cand.tier == CandidateTier.TIER_2_PATH:
            return (4, cand.key)
        return (5, cand.key)

    return sorted(candidates, key=priority_key)


def build_candidate_matrix(
    diff: SnapshotDiff,
    allow_path_perturbation: bool = False,
    max_experiments: int = 10,
) -> CandidateMatrix:
    """Extract and prioritize candidate hypotheses from a snapshot diff."""
    eligible: list[Candidate] = []
    excluded: list[Candidate] = []

    for item in diff.differences:
        tier = classify_candidate_tier(item.category, item.key, item.right_value)
        cand = Candidate(
            category=item.category,
            key=item.key,
            baseline_value=item.left_value,
            target_value=item.right_value,
            tier=tier,
        )

        if tier == CandidateTier.TIER_1_SAFE:
            eligible.append(cand)
        elif tier == CandidateTier.TIER_2_PATH:
            if allow_path_perturbation:
                eligible.append(cand)
            else:
                excluded.append(cand)
        else:
            excluded.append(cand)

    ranked_eligible = rank_candidates(eligible)

    if len(ranked_eligible) > max_experiments:
        # Move excess candidates beyond cap to excluded list
        excess = ranked_eligible[max_experiments:]
        ranked_eligible = ranked_eligible[:max_experiments]
        excluded.extend(excess)

    return CandidateMatrix(
        eligible_candidates=ranked_eligible,
        excluded_candidates=excluded,
    )


def run_candidate_experiment(
    candidate: Candidate,
    argv: Sequence[str],
    baseline_env: dict[str, str],
    baseline_cwd: str,
    target_signature: BehaviorSignature,
    baseline_signature: BehaviorSignature,
    timeout_seconds: float = 30.0,
) -> ExperimentOutcome:
    """Run exploratory + confirmation perturbation experiments for Candidate."""
    cmd_list = list(argv)

    # Prepare perturbed environment copy
    perturbed_env = dict(baseline_env)
    perturbed_cwd = baseline_cwd

    if candidate.category == "environment":
        if candidate.target_value is not None:
            perturbed_env[candidate.key] = candidate.target_value
        else:
            perturbed_env.pop(candidate.key, None)
    elif candidate.category == "system" and candidate.key == "cwd":
        if candidate.target_value and os.path.exists(candidate.target_value):
            perturbed_cwd = candidate.target_value

    # STEP 1: Run 1 exploratory experiment
    exploratory_res = run_command_subprocess(
        cmd_list, perturbed_env, cwd=perturbed_cwd, timeout_seconds=timeout_seconds
    )

    if exploratory_res.status == ExecutionStatus.EXEC_ERROR:
        return ExperimentOutcome(
            candidate=candidate,
            exploratory_result=exploratory_res,
            confirmation_results=[],
            outcome_classification=OutcomeClassification.EXPERIMENT_ERROR,
            matched_target=False,
        )

    if exploratory_res.status == ExecutionStatus.TIMEOUT:
        return ExperimentOutcome(
            candidate=candidate,
            exploratory_result=exploratory_res,
            confirmation_results=[],
            outcome_classification=OutcomeClassification.TIMEOUT,
            matched_target=False,
        )

    # Check if exploratory run matches target failure signature
    if not exploratory_res.behavior_signature.matches(target_signature):
        # If matches baseline signature, it had no effect
        if exploratory_res.behavior_signature.matches(baseline_signature):
            classification = OutcomeClassification.BASELINE_MATCH
        else:
            classification = OutcomeClassification.BEHAVIOR_CHANGE

        return ExperimentOutcome(
            candidate=candidate,
            exploratory_result=exploratory_res,
            confirmation_results=[],
            outcome_classification=classification,
            matched_target=False,
        )

    # STEP 2: Exploratory matched target! Run 2 confirmation runs (total 3 runs)
    confirmations: list[ExecutionResult] = []
    consistent = True

    for _ in range(2):
        res = run_command_subprocess(
            cmd_list, perturbed_env, cwd=perturbed_cwd, timeout_seconds=timeout_seconds
        )
        confirmations.append(res)
        if not res.behavior_signature.matches(target_signature):
            consistent = False

    if consistent:
        final_classification = OutcomeClassification.TARGET_MATCH
        matched = True
    else:
        final_classification = OutcomeClassification.UNSTABLE_EXPERIMENT
        matched = False

    return ExperimentOutcome(
        candidate=candidate,
        exploratory_result=exploratory_res,
        confirmation_results=confirmations,
        outcome_classification=final_classification,
        matched_target=matched,
    )
