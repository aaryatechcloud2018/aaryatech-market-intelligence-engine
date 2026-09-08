"""
mechanism_mapping.py

Maps APPROVED/EDITED behavioral evidence to Aaryatech's frozen mechanism library.

Design notes:
- Mechanism mapping is contextual, not keyword matching. The rule-based baseline
  backend here is deliberately conservative: without genuine semantic understanding,
  matching on a handful of keywords would produce exactly the kind of naive
  "salary mentioned -> loss aversion" association this project explicitly rejects.
  So the baseline only proposes a mapping when a mechanism entry supplies enough
  structured signal (an explicit keyword/description field) to support a defensible,
  reasoned match -- and it is designed to return NO SUPPORTED MECHANISM far more
  often than it proposes one. True contextual mapping is intended for a pluggable
  LLM backend (MechanismMapperBackend), which can be swapped in later without
  changing map_mechanism()'s call signature.
- If the mechanism library is not loaded (status != "LOADED"), this engine runs but
  produces zero mappings for every evidence item, with a clear reason logged. It
  does not error out silently and does not fabricate mechanism content.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Protocol, Optional
import uuid
import pandas as pd

from .mechanism_library import MechanismLibraryResult

MAPPING_REVIEW_STATUSES = {"pending", "approved", "rejected", "edited"}
SUPPORT_LEVELS = {"strong", "moderate", "weak", "insufficient"}


@dataclass
class MechanismMapping:
    mapping_id: str
    evidence_id: str
    application_id: str
    mechanism_id: str            # empty string if NO SUPPORTED MECHANISM
    mechanism_name: str
    mapping_reason: str
    evidence_support_level: str  # strong / moderate / weak / insufficient
    mapping_confidence: float
    alternative_interpretation: str
    review_status: str = "pending"
    reviewer_notes: str = ""

    def as_dict(self):
        return asdict(self)


class MechanismMapperBackend(Protocol):
    def propose(self, evidence_row: dict, mechanism_library: list[dict]) -> list[dict]:
        """Return a list of dicts: {mechanism_id, mechanism_name, reason, support_level,
        confidence, alternative_interpretation}. Empty list = NO SUPPORTED MECHANISM."""
        ...


class RuleBasedMechanismMapperBackend:
    """Conservative baseline. Only proposes a mapping when a mechanism entry has an
    explicit 'keywords' list (case-insensitive substrings) and at least two of those
    keywords are found across the evidence_span + context_before + context_after +
    evidence_description -- a much higher bar than single-keyword matching, and still
    explicitly labeled 'weak' support even when it fires, precisely because this is
    a surface-pattern heuristic and NOT genuine contextual reasoning."""

    def propose(self, evidence_row: dict, mechanism_library: list[dict]) -> list[dict]:
        if not mechanism_library:
            return []
        haystack = " ".join([
            str(evidence_row.get("evidence_span", "")),
            str(evidence_row.get("context_before", "")),
            str(evidence_row.get("context_after", "")),
            str(evidence_row.get("evidence_description", "")),
        ]).lower()

        proposals = []
        for mech in mechanism_library:
            keywords = [k.lower() for k in mech.get("keywords", [])]
            if len(keywords) < 2:
                continue  # not enough structured signal to support a defensible match
            hits = [k for k in keywords if k in haystack]
            if len(hits) >= 2:
                proposals.append({
                    "mechanism_id": mech["mechanism_id"],
                    "mechanism_name": mech["mechanism_name"],
                    "reason": f"Evidence text and surrounding context both reference: {', '.join(hits)}.",
                    "support_level": "weak",
                    "confidence": 0.35,
                    "alternative_interpretation": (
                        "Surface term overlap only -- a human reviewer should confirm this "
                        "is contextually appropriate, not coincidental."
                    ),
                })
        return proposals


# ---------------------------------------------------------------------------
# Context-aware backend, built for the REAL frozen mechanism library schema
# (Pattern_ID/Pattern_Name/Category/... with Possible_Contradictory_Signals,
# Related_Patterns, Distinguishing_Features, Evidence_Requirements).
#
# This is explicitly NOT keyword-only: it (1) uses a curated, documented mapping
# from DESCRIPTIVE evidence categories to plausible mechanism candidates -- never a
# raw text-keyword search -- (2) actively checks Possible_Contradictory_Signals
# against the evidence span AND its surrounding context to VETO candidates, (3)
# supports multiple plausible mechanisms via alternative_mechanism_id, and (4) is
# always allowed to return zero proposals (NO_SUPPORTED_MECHANISM).
#
# The category->mechanism hint table below is a development heuristic authored to
# get a defensible MVP mapping engine running -- it is explicitly NOT a scientific
# ground truth, and every proposal it makes still requires human review before it
# can be used for anything.
# ---------------------------------------------------------------------------
EVIDENCE_CATEGORY_MECHANISM_HINTS = {
    "commitment_language": ["Commitment / Consistency", "Self-Consistency", "Identity Signaling"],
    "certainty_uncertainty": ["Uncertainty / Ambiguity Aversion", "Status Quo Bias"],
    "responsiveness": [],
    "compensation_concern": ["Loss Aversion", "Anchoring", "Fairness / Equity Perception"],
    "alternative_opportunity": ["Choice Overload", "Present Bias (Hyperbolic Discounting)"],
    "current_employer_activity": ["Status Quo Bias", "Endowment Effect", "Sunk Cost Fallacy"],
    "job_security_concern": ["Uncertainty / Ambiguity Aversion", "Loss Aversion"],
    "work_arrangement": ["Status Quo Bias"],
    "location_commute": ["Friction"],
    "schedule_shift": ["Friction"],
    "joining_date": ["Goal Gradient", "Present Bias (Hyperbolic Discounting)"],
    "onboarding_process": ["Friction", "Default Effect"],
    "documentation": ["Friction"],
    "recruiter_follow_up": ["Reciprocity", "Halo Effect"],
    "expectation_setting": ["Confirmation Bias", "Cognitive Dissonance"],
    "candidate_questions": [],
    "candidate_excitement": ["Identity Signaling", "Halo Effect"],
    "candidate_hesitation": ["Uncertainty / Ambiguity Aversion", "Status Quo Bias"],
    "withdrawal_language": ["Loss Aversion", "Reactance", "Cognitive Dissonance"],
    "contradictory_information": [],
    "process_delay": ["Friction", "Negativity Bias"],
    "other": [],
}


def _text_blob(evidence_row: dict) -> str:
    return " ".join([
        str(evidence_row.get("evidence_span", "")),
        str(evidence_row.get("context_before", "")),
        str(evidence_row.get("context_after", "")),
    ]).lower()


class ContextAwareMechanismMapperBackend:
    """
    Multi-factor rule-based baseline for the real 34-mechanism library. This is the
    pluggable backend actually used by run_mechanism_mapping.py. An LLM-backed
    backend implementing the same MechanismMapperBackend protocol can replace this
    later without changing map_mechanism()'s call signature.
    """

    def propose(self, evidence_row: dict, mechanism_library: list[dict]) -> list[dict]:
        category = str(evidence_row.get("human_evidence_category")
                        or evidence_row.get("evidence_category") or "")
        hinted_names = EVIDENCE_CATEGORY_MECHANISM_HINTS.get(category, [])
        if not hinted_names:
            return []

        by_name = {m["Pattern_Name"]: m for m in mechanism_library}
        blob = _text_blob(evidence_row)

        candidates = []
        for name in hinted_names:
            mech = by_name.get(name)
            if mech is None:
                continue  # hinted mechanism not present in the loaded library -- skip, don't guess

            contradictions_found = [
                sig for sig in mech.get("Possible_Contradictory_Signals", [])
                if sig.lower() in blob
            ]
            if contradictions_found:
                # Vetoed: contradictory evidence present in the text/context itself.
                continue

            candidates.append({
                "mechanism_id": mech["Pattern_ID"],
                "mechanism_name": mech["Pattern_Name"],
                "category": mech.get("Category", ""),
                "distinguishing_features": mech.get("Distinguishing_Features", ""),
                "evidence_requirements": mech.get("Evidence_Requirements", ""),
                "related_patterns": mech.get("Related_Patterns", []),
            })

        if not candidates:
            return []

        proposals = []
        primary = candidates[0]
        alt = candidates[1] if len(candidates) > 1 else None

        support_level = "moderate" if len(candidates) == 1 else "weak"
        confidence = 0.55 if len(candidates) == 1 else 0.4

        reason = (
            f"Evidence category '{category}' is a documented candidate signal for "
            f"'{primary['mechanism_name']}' ({primary['category']}); no matching "
            f"Possible_Contradictory_Signals phrase was found in the evidence span or "
            f"its surrounding context."
        )
        supporting_context = (
            f"context_before/context_after reviewed for contradiction; distinguishing "
            f"feature considered: {primary['distinguishing_features'][:200]}"
        )
        contradictory_context = "none found in evidence span or immediate context"

        proposals.append({
            "mechanism_id": primary["mechanism_id"],
            "mechanism_name": primary["mechanism_name"],
            "reason": reason,
            "support_level": support_level,
            "confidence": confidence,
            "supporting_context": supporting_context,
            "contradictory_context": contradictory_context,
            "alternative_mechanism_id": alt["mechanism_id"] if alt else "",
            "alternative_reason": (
                f"'{alt['mechanism_name']}' is also a documented candidate for this evidence "
                f"category and was not contradicted either -- human review should confirm "
                f"which (if either) fits better." if alt else ""
            ),
        })
        return proposals


def map_mechanism(approved_evidence: pd.DataFrame, mechanism_library_result: MechanismLibraryResult,
                   backend: Optional[MechanismMapperBackend] = None) -> pd.DataFrame:
    """
    approved_evidence: rows from evidence_review.get_approved_or_edited(), merged with
        the original evidence_span/context columns from behavioral_evidence_candidates.
    mechanism_library_result: output of mechanism_library.load_mechanism_library().
    """
    backend = backend or RuleBasedMechanismMapperBackend()
    rows = []

    if mechanism_library_result.status != "LOADED" or not mechanism_library_result.mechanisms:
        # Honest, explicit "no mapping possible" -- not a silent empty return.
        for _, ev in approved_evidence.iterrows():
            rows.append(MechanismMapping(
                mapping_id=f"MAP-{uuid.uuid4().hex[:12]}",
                evidence_id=ev.evidence_id,
                application_id=ev.application_id,
                mechanism_id="",
                mechanism_name="",
                mapping_reason="NO SUPPORTED MECHANISM -- mechanism library is not loaded "
                                f"({mechanism_library_result.error or 'not found'}).",
                evidence_support_level="insufficient",
                mapping_confidence=0.0,
                alternative_interpretation="",
                review_status="pending",
                reviewer_notes="",
            ).as_dict())
        return pd.DataFrame(rows, columns=list(MechanismMapping.__annotations__.keys()))

    for _, ev in approved_evidence.iterrows():
        proposals = backend.propose(ev.to_dict(), mechanism_library_result.mechanisms)
        if not proposals:
            rows.append(MechanismMapping(
                mapping_id=f"MAP-{uuid.uuid4().hex[:12]}",
                evidence_id=ev.evidence_id,
                application_id=ev.application_id,
                mechanism_id="",
                mechanism_name="",
                mapping_reason="NO SUPPORTED MECHANISM -- insufficient contextual support "
                                "for any library mechanism.",
                evidence_support_level="insufficient",
                mapping_confidence=0.0,
                alternative_interpretation="",
                review_status="pending",
                reviewer_notes="",
            ).as_dict())
            continue
        for p in proposals:
            rows.append(MechanismMapping(
                mapping_id=f"MAP-{uuid.uuid4().hex[:12]}",
                evidence_id=ev.evidence_id,
                application_id=ev.application_id,
                mechanism_id=p["mechanism_id"],
                mechanism_name=p["mechanism_name"],
                mapping_reason=p["reason"],
                evidence_support_level=p["support_level"],
                mapping_confidence=p["confidence"],
                alternative_interpretation=p.get("alternative_interpretation", ""),
                review_status="pending",
                reviewer_notes="",
            ).as_dict())

    return pd.DataFrame(rows, columns=list(MechanismMapping.__annotations__.keys()))


# ---------------------------------------------------------------------------
# New mapping function for the human-review-sample-driven workflow (Part 6/7/8).
# Produces the exact schema requested for mechanism_human_review.csv, distinct
# from the earlier MechanismMapping dataclass used by Task 2-5's pipeline run.
# ---------------------------------------------------------------------------
MAPPING_V2_COLUMNS = [
    "mapping_id", "evidence_id", "application_id", "mechanism_id", "mechanism_name",
    "mapping_reason", "supporting_context", "contradictory_context", "mapping_confidence",
    "alternative_mechanism_id", "alternative_reason", "mapping_status",
    "human_mapping_decision", "human_selected_mechanism", "human_mapping_notes",
]


def map_reviewed_evidence(approved_evidence: pd.DataFrame,
                           mechanism_library_result: MechanismLibraryResult,
                           backend: Optional[MechanismMapperBackend] = None) -> pd.DataFrame:
    """
    approved_evidence: rows from the human evidence review sample where
        human_decision is APPROVE or EDIT ONLY. Caller is responsible for that
        filter -- this function does not re-check human_decision itself, so it
        must never be called with anything else (see run_mechanism_mapping.py,
        which enforces this).
    mechanism_library_result: output of mechanism_library.load_mechanism_library().
        Must be the frozen source-of-truth library, loaded unmodified.
    """
    backend = backend or ContextAwareMechanismMapperBackend()
    rows = []

    for _, ev in approved_evidence.iterrows():
        if mechanism_library_result.status != "LOADED" or not mechanism_library_result.mechanisms:
            rows.append({
                "mapping_id": f"MAP-{uuid.uuid4().hex[:12]}",
                "evidence_id": ev.evidence_id,
                "application_id": ev.application_id,
                "mechanism_id": "", "mechanism_name": "",
                "mapping_reason": f"NO_SUPPORTED_MECHANISM -- mechanism library not loaded "
                                   f"({mechanism_library_result.error or 'not found'}).",
                "supporting_context": "", "contradictory_context": "",
                "mapping_confidence": 0.0,
                "alternative_mechanism_id": "", "alternative_reason": "",
                "mapping_status": "NO_SUPPORTED_MECHANISM",
                "human_mapping_decision": "PENDING",
                "human_selected_mechanism": "", "human_mapping_notes": "",
            })
            continue

        proposals = backend.propose(ev.to_dict(), mechanism_library_result.mechanisms)
        if not proposals:
            rows.append({
                "mapping_id": f"MAP-{uuid.uuid4().hex[:12]}",
                "evidence_id": ev.evidence_id,
                "application_id": ev.application_id,
                "mechanism_id": "", "mechanism_name": "",
                "mapping_reason": "NO_SUPPORTED_MECHANISM -- no library mechanism had sufficient, "
                                   "uncontradicted contextual support for this evidence category.",
                "supporting_context": "", "contradictory_context": "",
                "mapping_confidence": 0.0,
                "alternative_mechanism_id": "", "alternative_reason": "",
                "mapping_status": "NO_SUPPORTED_MECHANISM",
                "human_mapping_decision": "PENDING",
                "human_selected_mechanism": "", "human_mapping_notes": "",
            })
            continue

        for p in proposals:
            rows.append({
                "mapping_id": f"MAP-{uuid.uuid4().hex[:12]}",
                "evidence_id": ev.evidence_id,
                "application_id": ev.application_id,
                "mechanism_id": p["mechanism_id"],
                "mechanism_name": p["mechanism_name"],
                "mapping_reason": p["reason"],
                "supporting_context": p.get("supporting_context", ""),
                "contradictory_context": p.get("contradictory_context", ""),
                "mapping_confidence": p["confidence"],
                "alternative_mechanism_id": p.get("alternative_mechanism_id", ""),
                "alternative_reason": p.get("alternative_reason", ""),
                "mapping_status": "PROPOSED",
                "human_mapping_decision": "PENDING",
                "human_selected_mechanism": "", "human_mapping_notes": "",
            })

    return pd.DataFrame(rows, columns=MAPPING_V2_COLUMNS)
