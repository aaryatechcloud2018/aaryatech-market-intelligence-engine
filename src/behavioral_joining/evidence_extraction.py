"""
evidence_extraction.py

Behavioral evidence extraction engine.

Architecture (Part H):
  1. A deterministic rule-based baseline extractor (EvidenceExtractor / RuleBasedExtractor)
     that runs with zero external dependencies -- always available.
  2. A pluggable ExtractorBackend interface so an LLM-backed extractor can be dropped
     in later without changing anything that calls extract_evidence().
  3. Human review remains mandatory downstream (evidence_review.py) -- nothing here
     auto-approves anything.

Evidence categories are DESCRIPTIVE observations about communication content/behavior,
never behavioral-science mechanism interpretations. See EVIDENCE_CATEGORIES below.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional, Protocol
import re
import uuid
import pandas as pd

EVIDENCE_CATEGORIES = [
    "commitment_language", "certainty_uncertainty", "responsiveness", "response_latency",
    "compensation_concern", "alternative_opportunity", "current_employer_activity",
    "job_security_concern", "work_arrangement", "location_commute", "schedule_shift",
    "joining_date", "onboarding_process", "documentation", "recruiter_follow_up",
    "expectation_setting", "candidate_questions", "candidate_excitement",
    "candidate_hesitation", "withdrawal_language", "contradictory_information",
    "process_delay", "other",
]

REVIEW_STATUSES = {"pending", "approved", "rejected", "edited"}
EVIDENCE_STRENGTHS = {"weak", "moderate", "strong"}


@dataclass
class EvidenceCandidate:
    evidence_id: str
    application_id: str
    log_id: str
    timestamp: str
    source_type: str
    direction: str
    evidence_span: str          # EXACT source text -- never paraphrased
    evidence_category: str
    evidence_description: str   # descriptive observation, NOT a mechanism claim
    evidence_strength: str      # weak / moderate / strong
    context_before: str
    context_after: str
    response_latency_hours: float
    extractor_confidence: float
    review_status: str = "pending"
    reviewer_notes: str = ""

    def as_dict(self):
        return asdict(self)


class ExtractorBackend(Protocol):
    """Pluggable interface. Any backend (rule-based, local model, hosted LLM) that
    implements this method can be swapped in without touching extract_evidence()."""
    def propose(self, text: str) -> list[dict]:
        """Return a list of dicts: {category, description, strength, confidence}."""
        ...


# ---------------------------------------------------------------------------
# Rule-based baseline backend -- always available, no external API required.
# Patterns are intentionally observational, not theory-laden. Each rule maps
# surface language patterns to a DESCRIPTIVE category + plain-English description.
# ---------------------------------------------------------------------------
class RuleBasedExtractorBackend:
    RULES = [
        # (category, [regex patterns], description template, base_strength)
        ("commitment_language",
         [r"\blooking forward\b", r"\bcan'?t wait\b", r"\bexcited\b", r"\bcommitted\b",
          r"\bsee you (then|there)\b"],
         "Candidate uses language expressing forward commitment to the role.", "moderate"),

        ("certainty_uncertainty",
         [r"\b(still (sorting|thinking|deciding))\b", r"\bnot (totally|100%|fully) sure\b",
          r"\bkind of\b", r"\bsort of\b", r"\bmight\b.*\b(push|move|change)\b"],
         "Candidate expresses uncertainty or hedging about their situation.", "moderate"),

        ("responsiveness",
         [r"^(ok|okay|sure|yep|got it)\.?$", r"\bsounds good\b"],
         "Candidate gives a brief, low-elaboration response.", "weak"),

        ("compensation_concern",
         [r"\b(pay rate|compensation|salary|comp)\b.*\b(concern|lower|expect|revisit)\b",
          r"\brate is a little\b", r"\bdouble check.{0,15}rate\b"],
         "Candidate raises a question or concern about compensation.", "moderate"),

        ("alternative_opportunity",
         [r"\banother (company|opportunity|offer|process)\b", r"\bparallel process\b",
          r"\bcompeting (offer|process)\b", r"\bother role\b"],
         "Candidate references a parallel or competing opportunity.", "strong"),

        ("current_employer_activity",
         [r"\bcurrent (employer|manager|job)\b", r"\bmanager (asked|wants) to (talk|speak)\b",
          r"\bcounteroffer\b", r"\bstay(ing)? (at|with) my current\b"],
         "Candidate references activity or conversations at their current employer.", "strong"),

        ("job_security_concern",
         [r"\b(long term|long-term) stability\b", r"\bconvert to permanent\b",
          r"\bhow stable\b", r"\bcontract length\b", r"\bshort.?term\b.*\brole\b"],
         "Candidate asks about role stability or long-term security.", "moderate"),

        ("work_arrangement",
         [r"\b(fully remote|hybrid|onsite)\b", r"\bcome in sometimes\b",
          r"\bdays onsite\b", r"\bwork arrangement\b"],
         "Candidate raises a question about remote/hybrid/onsite work arrangement.", "moderate"),

        ("location_commute",
         [r"\bcommute\b", r"\btraffic\b", r"\btransportation\b", r"\bdrive to\b"],
         "Candidate raises a comment or concern about commute/location.", "moderate"),

        ("schedule_shift",
         [r"\bshift\b", r"\bschedule\b.*\b(flexib|conflict|childcare)\b", r"\bday shift\b"],
         "Candidate raises a comment about shift or schedule.", "moderate"),

        ("joining_date",
         [r"\bstart date\b", r"\bfinal(ly)? date\b", r"\bconfirmed\b.*\bstart\b",
          r"\bmove again\b", r"\bpush(ed)? (the )?(start )?date\b"],
         "Candidate references the start/joining date, its confirmation, or a change to it.", "moderate"),

        ("onboarding_process",
         [r"\bbring on day one\b", r"\bonboarding\b", r"\bparking\b", r"\bbadge\b"],
         "Candidate asks about onboarding logistics.", "weak"),

        ("documentation",
         [r"\boffer letter\b", r"\bpaperwork\b", r"\bbackground check\b"],
         "Reference to offer letter, paperwork, or background check status.", "moderate"),

        ("recruiter_follow_up",
         [r"\bhaven'?t heard\b", r"\bfollowing up again\b", r"\bany (news|update)\b",
          r"\bchecking in\b"],
         "Candidate follows up due to a lack of recent contact from the recruiter.", "moderate"),

        ("expectation_setting",
         [r"\bscope\b.*\b(sound|different|change)\b", r"\bthought this (role|was)\b",
          r"\bclarif(y|ied)\b"],
         "Communication reflects clarification or mismatch of role expectations.", "moderate"),

        ("candidate_questions",
         [r"\?\s*$", r"\bcan you confirm\b", r"\bwanted to (ask|check)\b"],
         "Candidate asks a direct question.", "weak"),

        ("candidate_excitement",
         [r"\bso excited\b", r"\bgreat fit\b", r"\breally appreciate\b", r"\bthank you so much\b"],
         "Candidate expresses positive sentiment about the role or process.", "moderate"),

        ("candidate_hesitation",
         [r"\bstill (sorting|figuring|thinking)\b", r"\bneed (a bit )?more time\b",
          r"\bgoing back and forth\b"],
         "Candidate's language reflects hesitation or delay in decision-making.", "moderate"),

        ("withdrawal_language",
         [r"\bwithdraw\b", r"\bnot going to (be able to )?move forward\b",
          r"\bhave to pass\b", r"\bdecided to\b.*\b(withdraw|pass|step back)\b",
          r"\bwon'?t be (moving forward|able to)\b"],
         "Communication contains explicit withdrawal or declination language.", "strong"),

        ("contradictory_information",
         [r"\bpersonal reasons\b"],
         "Stated reason is brief/generic; may warrant comparison against surrounding evidence.", "weak"),

        ("process_delay",
         [r"\bdelay(ed)?\b", r"\btakes? longer\b", r"\brunning behind\b", r"\bstill (waiting|processing)\b"],
         "Communication references a delay in the recruitment process.", "moderate"),
    ]

    def propose(self, text: str) -> list[dict]:
        if not isinstance(text, str) or not text.strip():
            return []
        proposals = []
        low = text.lower()
        for category, patterns, description, strength in self.RULES:
            for pat in patterns:
                if re.search(pat, low, flags=re.IGNORECASE):
                    proposals.append({
                        "category": category,
                        "description": description,
                        "strength": strength,
                        "confidence": {"weak": 0.45, "moderate": 0.6, "strong": 0.75}[strength],
                    })
                    break  # one proposal per category per message is enough
        return proposals


class EvidenceExtractor:
    """Orchestrates extraction over a discovery working set using a pluggable backend."""

    def __init__(self, backend: Optional[ExtractorBackend] = None):
        self.backend = backend or RuleBasedExtractorBackend()

    def extract_evidence(self, context) -> pd.DataFrame:
        """
        context: DiscoveryWorkingSet (outcome-blind). Returns a DataFrame of
        EvidenceCandidate rows, review_status = 'pending' for every row.
        """
        from .discovery_context import assert_outcome_blind
        assert_outcome_blind(context.applications)

        comms = context.communications.sort_values(["application_id", "timestamp"]).copy()
        comms = comms.reset_index(drop=True)

        rows = []
        for app_id, sub in comms.groupby("application_id"):
            sub = sub.reset_index(drop=True)
            texts = sub["text"].fillna("").tolist()
            for i, row in sub.iterrows():
                proposals = self.backend.propose(row["text"])
                if not proposals:
                    continue
                context_before = texts[i - 1] if i > 0 else ""
                context_after = texts[i + 1] if i < len(texts) - 1 else ""
                for p in proposals:
                    ev = EvidenceCandidate(
                        evidence_id=f"EV-{uuid.uuid4().hex[:12]}",
                        application_id=app_id,
                        log_id=row["log_id"],
                        timestamp=str(row["timestamp"]),
                        source_type=row["source_type"],
                        direction=row["direction"],
                        evidence_span=row["text"],  # exact source text
                        evidence_category=p["category"],
                        evidence_description=p["description"],
                        evidence_strength=p["strength"],
                        context_before=context_before,
                        context_after=context_after,
                        response_latency_hours=row["response_latency_hours"],
                        extractor_confidence=p["confidence"],
                        review_status="pending",
                        reviewer_notes="",
                    )
                    rows.append(ev.as_dict())

        return pd.DataFrame(rows, columns=list(EvidenceCandidate.__annotations__.keys()))


def extract_evidence(context, backend: Optional[ExtractorBackend] = None) -> pd.DataFrame:
    """Module-level convenience function matching the requested extract_evidence(context) interface."""
    return EvidenceExtractor(backend=backend).extract_evidence(context)
