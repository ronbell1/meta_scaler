"""
Policy Engine — 30 deterministic policy rules for procurement contract review.

Each rule has:
  - rule_id: unique identifier
  - category: one of LIABILITY, PAYMENT, IP, DATA_PRIVACY, TERMINATION, DISPUTE
  - description: plain-English policy requirement
  - severity: critical | high | medium | low
  - check(contract_text: str) -> bool  (True = violation found)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class PolicyRule:
    rule_id: str
    category: str
    description: str
    severity: str  # critical | high | medium | low
    check: Callable[[str], bool] = field(repr=False)


# ─── helpers ───────────────────────────────────────────────────────────────


def _has_clause(text: str, pattern: str, flags: int = re.IGNORECASE) -> bool:
    return bool(re.search(pattern, text, flags))


def _extract_number(text: str, pattern: str, flags: int = re.IGNORECASE) -> Optional[float]:
    m = re.search(pattern, text, flags)
    if m:
        try:
            return float(m.group(1))
        except (IndexError, ValueError):
            return None
    return None


def _extract_days(text: str, pattern: str) -> Optional[int]:
    """Extract a number of days from text matching pattern."""
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        try:
            return int(float(m.group(1)))
        except (IndexError, ValueError):
            return None
    return None


# ─── checkers ──────────────────────────────────────────────────────────────


def check_liability_cap(text: str) -> bool:
    """RULE_01: Liability cap must be >= 2x annual contract value."""
    if not _has_clause(text, r"liability.*cap|cap.*liability|limited to fees|total liability"):
        return False
    cap_months = _extract_days(text, r"(?:preceding|past|previous)\s+(\d+)\s+month")
    if cap_months is not None and cap_months < 24:
        return True
    m = re.search(r"preceding\s+(?:six|three)\s*\(?(\d+)\)?\s*months?", text, re.IGNORECASE)
    if m:
        return int(m.group(1)) < 24
    if _has_clause(text, r"liability.*unlimited|no.*cap|not.*limited", re.IGNORECASE):
        return False
    return False
    cap_months = _extract_days(text, r"(?:preceding|past|previous)\s+(\d+)\s+month")
    if cap_months is not None and cap_months < 24:
        return True
    m = re.search(r"preceding\s+(?:six|three)\s*\(?(\d+)\)?\s*months?", text, re.IGNORECASE)
    if m:
        return True
    m = re.search(r"preceding\s+six\s+\(6\)\s+months", text, re.IGNORECASE)
    if m:
        return True
    if _has_clause(text, r"liability.*unlimited|no.*cap|not.*limited", re.IGNORECASE):
        return False
    return False
    cap_months = _extract_days(text, r"(?:preceding|past|previous)\s+(\d+)\s+month")
    if cap_months is not None and cap_months < 24:
        return True
    m = re.search(r"preceding\s+(?:six|three)\s*\(?(\d+)\)?\s*months?", text, re.IGNORECASE)
    if m:
        return True
    if _has_clause(text, r"liability.*unlimited|no.*cap|not.*limited", re.IGNORECASE):
        return False
    return False


def check_payment_terms(text: str) -> bool:
    """RULE_02: Payment terms must be net-60 or better (not net-30 or less)."""
    m = re.search(r"net[- ](\d+)", text, re.IGNORECASE)
    if m:
        days = int(m.group(1))
        return days < 60
    m = re.search(r"within\s+(?:thirty|forty|fifty)\s*\(?(\d+)\)?\s*days?", text, re.IGNORECASE)
    if m:
        days = int(m.group(1))
        return days < 60
    m = re.search(r"(?:pay|paid|payment|invoices).*within.*?(\d+)\s*days?", text, re.IGNORECASE)
    if m:
        days = int(m.group(1))
        return days < 60
    return False


def check_auto_renewal(text: str) -> bool:
    """RULE_03: Auto-renewal requires 90-day written opt-out notice."""
    if not _has_clause(text, r"auto[- ]?renew|renewal|automatically renew|renews automatically"):
        return False
    m = re.search(r"at\s+least\s+(\d+)\s*days?\s*(?:prior\s+)?(?:written\s+)?notice", text, re.IGNORECASE)
    if m:
        days = int(m.group(1))
        return days < 90
    m = re.search(r"(\d+)\s*days?\s*(?:prior\s+)?(?:written\s+)?notice", text, re.IGNORECASE)
    if m:
        days = int(m.group(1))
        return days < 90
    m = re.search(r"(?:terminated|notice).*?(\d+)\s*days?", text, re.IGNORECASE)
    if m:
        days = int(m.group(1))
        return days < 90
    return False
    m = re.search(r"(\d+)\s*days?\s*(?:prior\s+)?(?:written\s+)?notice", text, re.IGNORECASE)
    if m:
        days = int(m.group(1))
        return days < 90
    m = re.search(r"(?:terminated|notice).*?(\d+)\s*days?", text, re.IGNORECASE)
    if m:
        days = int(m.group(1))
        return days < 90
    return False


def check_governing_law(text: str) -> bool:
    """RULE_04: Governing law must be India or USA (not Singapore/UK)."""
    if not _has_clause(text, r"governing law|laws of|governed by"):
        return False
    if _has_clause(
        text,
        r"(?:governed by|laws of)\s+(?:the\s+)?(?:singapore|uk|united kingdom|england)",
    ):
        return True
    return False


def check_ip_work_for_hire(text: str) -> bool:
    """RULE_05: IP created by vendor is work-for-hire (company owns it)."""
    if _has_clause(
        text,
        r"(?:work product|inventions|deliverables|ip|intellectual property).*(?:shall be|is).*(?:sole property|property|owned by|belongs to)\s+(?:of\s+)?(?:supplier|vendor|contractor)",
    ):
        return True
    if _has_clause(
        text,
        r"(?:all\s+)?(?:ip|intellectual property).*(?:transfer|assigned|transfers)\s+to\s+(?:vendor|supplier)",
    ):
        return True
    return False


def check_mutual_indemnification(text: str) -> bool:
    """RULE_06: Indemnification must be mutual (not one-sided)."""
    if not _has_clause(text, r"indemnif"):
        return False
    client_indemnifies = _has_clause(text, r"(?:client|company|buyer|licensee)\s+(?:shall\s+)?indemnif")
    vendor_indemnifies = _has_clause(text, r"(?:vendor|supplier|contractor|seller)\s+(?:shall\s+)?indemnif")
    if client_indemnifies and not vendor_indemnifies:
        return True
    if _has_clause(text, r"indemnif.*(?:vendor|supplier|contractor).*negligence"):
        return True
    return False


def check_termination_notice(text: str) -> bool:
    """RULE_07: Termination for convenience: minimum 30-day notice."""
    if not _has_clause(text, r"terminat"):
        return False
    days = _extract_days(
        text,
        r"(?:terminate|termination).*(\d+)\s*(?:-?day|days?)\s*(?:notice|prior|written)",
    )
    if days is not None and days < 30:
        return True
    m = re.search(r"(\d+)\s*days?\s*(?:prior\s+)?(?:written\s+)?notice", text, re.IGNORECASE)
    if m and int(m.group(1)) < 30:
        return True
    return False


def check_dpa_required(text: str) -> bool:
    """RULE_08: Data processing agreement required if PII is shared."""
    has_pii = _has_clause(
        text,
        r"(?:personal data|pii|personally identifiable|gdpr|data protection|data processing)",
    )
    has_dpa = _has_clause(text, r"data processing agreement|dpa\b|data protection addendum")
    if has_pii and not has_dpa:
        return True
    if _has_clause(
        text,
        r"no\s+data processing agreement|no\s+separate\s+data\s+processing\s+agreement|dpa.*not\s+referenced|gdpr.*unaddressed|gdpr\s+obligations\s+are\s+not\s+specifically\s+addressed",
    ):
        return True
    return False


def check_limitation_of_liability(text: str) -> bool:
    """RULE_09: Limitation of liability clause must be present."""
    if _has_clause(
        text,
        r"no\s+limitation\s+of\s+liability\s+clause|liability\s+is\s+capped\s+or\s+limited\s+in\s+any\s+way",
    ):
        return True
    if not _has_clause(
        text,
        r"limitation of liability|limit.*liability|liability.*cap|liability.*limit",
    ):
        return True
    return False


def check_sla_uptime(text: str) -> bool:
    """RULE_10: SLA uptime commitment >= 99.5% for production services."""
    if not _has_clause(
        text,
        r"(?:uptime|availability|sla).*(?:\d+\.?\d*)%|(\d+\.?\d*)%.*(?:uptime|availability)",
    ):
        return False
    m = re.search(r"(\d+\.?\d*)\s*%", text)
    if m:
        uptime = float(m.group(1))
        if uptime < 99.5:
            return True
    return False


def check_warranty_period(text: str) -> bool:
    """RULE_11: Warranty period minimum 12 months post-delivery."""
    if not _has_clause(text, r"warrant"):
        return False
    months = _extract_number(text, r"warrant.*?for\s+(?:a\s+period\s+of\s+)?(\d+)\s*(?:month|year)")
    if months is not None:
        if months < 12:
            return True
    if _has_clause(text, r"warranty.*(?:not\s+provided|no\s+warranty|warranty\s+not\s+defined)"):
        return True
    return False
    months = _extract_number(text, r"warrant.*?(\d+)\s*(?:month|year)")
    if months is not None:
        if months < 12:
            return True
    if _has_clause(text, r"warranty.*(?:not\s+provided|no\s+warranty|warranty\s+not\s+defined)"):
        return True
    return False


def check_dispute_arbitration(text: str) -> bool:
    """RULE_12: Dispute resolution: arbitration preferred over litigation."""
    if not _has_clause(text, r"dispute|arbitration|litigation|jurisdiction"):
        return False
    if _has_clause(
        text,
        r"(?:disputes?.*resolved|jurisdiction).*(?:exclusively|solely|only).*(?:court|litigation|vendor.*home)",
    ):
        return True
    if not _has_clause(text, r"arbitration"):
        return True
    return False


def check_late_payment_penalty(text: str) -> bool:
    """RULE_13: Late payment penalty clause required."""
    if not _has_clause(text, r"(?:payment|pay|invoice)"):
        return False
    if _has_clause(
        text,
        r"late\s+payments?\s+shall\s+accrue\s+interest|late\s+payments?\s+incur\s+interest|overdue\s+amounts?\s+bear\s+interest|late\s+payment\s+penalty",
    ):
        return False
    if _has_clause(
        text, r"no\s+penalty|no\s+late\s+fee|late\s+payments?\s+incur\s+no\s+penalty|no\s+late\s+payment\s+penalty"
    ):
        return True
    if not _has_clause(
        text,
        r"late.*penalty|penalty.*late|interest.*late|late.*fee|late.*charge|overdue.*interest",
    ):
        return True
    return False
    if not _has_clause(
        text,
        r"late.*penalty|penalty.*late|interest.*late|late.*fee|late.*charge|overdue.*interest",
    ):
        return True
    if _has_clause(text, r"no\s+penalty|no\s+late\s+fee|late\s+payments?\s+incur\s+no\s+penalty"):
        return True
    return False


def check_currency_risk(text: str) -> bool:
    """RULE_14: Currency fluctuation risk must be shared."""
    if _has_clause(
        text,
        r"currency.*(?:risk|fluctuation|exchange).*(?:borne|borne entirely|solely|entirely)\s+by\s+(?:client|buyer|licensee)",
    ):
        return True
    if _has_clause(
        text,
        r"(?:client|buyer|licensee).*bears.*currency|currency.*risk.*entirely.*client",
    ):
        return True
    return False


def check_background_ip_license(text: str) -> bool:
    """RULE_15: License-back required on vendor background IP."""
    if _has_clause(
        text,
        r"(?:no\s+license|receives\s+no\s+license|not\s+granted).*(?:background\s+ip|pre[- ]?existing|vendor.*ip)",
    ):
        return True
    if _has_clause(text, r"(?:client|company).*no\s+license.*background"):
        return True
    return False


def check_asymmetric_liability(text: str) -> bool:
    """RULE_16: Symmetric liability caps required."""
    if _has_clause(
        text,
        r"(?:vendor|supplier|contractor).*(?:liability|total liability).*(?:unlimited|not\s+limited|uncapped)",
    ):
        return True
    if _has_clause(
        text,
        r"(?:client|company|buyer).*(?:liability|total liability).*(?:capped|limited).*(?:\$\d+|\d+\s+month)",
    ):
        return True
    return False


def check_consequential_damages(text: str) -> bool:
    """RULE_17: Mutual consequential damages exclusion."""
    if not _has_clause(text, r"consequential\s+damages|indirect\s+damages"):
        return False
    if _has_clause(
        text,
        r"consequential.*excluded.*only\s+(?:for|vendor|supplier)|consequential.*exclusion.*one[- ]sided",
    ):
        return True
    if _has_clause(
        text,
        r"(?:vendor|supplier|contractor).*(?:exclude|exclude|except).*(?:consequential|indirect)",
    ) and not _has_clause(
        text,
        r"(?:client|company|buyer).*(?:exclude|except).*(?:consequential|indirect)",
    ):
        return True
    return False


def check_data_breach_indemnity(text: str) -> bool:
    """RULE_18: Indemnification must cover data breaches."""
    if not _has_clause(text, r"indemnif"):
        return False
    if _has_clause(
        text,
        r"indemnif.*(?:exclude|excludes|except).*(?:data\s+breach|security\s+incident|breach)",
    ):
        return True
    if _has_clause(
        text,
        r"(?:exclude|excludes|except).*(?:data\s+breach|security\s+incident).*indemnif",
    ):
        return True
    return False


def check_sla_penalties(text: str) -> bool:
    """RULE_19: SLA breach penalties/credits required."""
    if not _has_clause(text, r"(?:sla|uptime|availability|service\s+level)"):
        return False
    if _has_clause(
        text,
        r"no\s+(?:credits|penalties|remedies)|no\s+financial\s+penalty|penalties?.*not\s+defined|no\s+service\s+credits|no\s+remedies\s+are\s+defined",
    ):
        return True
    if not _has_clause(text, r"(?:credit|penalty|remedy|remedies|service\s+credit|financial)"):
        return True
    return False
    if not _has_clause(text, r"(?:credit|penalty|remedy|remedies|service\s+credit|financial)"):
        return True
    if _has_clause(
        text,
        r"no\s+(?:credits|penalties|remedies)|no\s+financial\s+penalty|penalties?.*not\s+defined",
    ):
        return True
    return False


def check_suspension_notice(text: str) -> bool:
    """RULE_20: Vendor may not suspend service without notice."""
    if _has_clause(text, r"(?:vendor|supplier|contractor)\s+may\s+suspend.*without\s+notice"):
        return True
    if _has_clause(text, r"suspend.*service.*without\s+(?:prior|written)?\s*notice"):
        return True
    return False


def check_confidentiality_period(text: str) -> bool:
    """RULE_21: Confidentiality period must be >= 3 years."""
    if not _has_clause(text, r"confidential"):
        return False
    years = _extract_number(text, r"confidential.*?for\s+(?:a\s+period\s+of\s+)?(\d+)\s*(?:year|yr)")
    if years is not None and years < 3:
        return True
    months = _extract_number(text, r"confidential.*?for\s+(?:a\s+period\s+of\s+)?(\d+)\s*month")
    if months is not None and months < 36:
        return True
    return False


def check_escalation_clause(text: str) -> bool:
    """RULE_22: Dispute escalation to senior management before litigation."""
    if not _has_clause(text, r"dispute|escalat"):
        return False
    if _has_clause(
        text,
        r"(?:first\s+be\s+submitted|escalat|senior\s+management|executive).*(?:negotiation|good-faith\s+negotiation).*(?:before\s+pursuing|before\s+litigation|before\s+arbitration|before\s+court)",
    ):
        return False
    if _has_clause(
        text,
        r"(?:escalat|senior\s+management|executive|negotiation)\s+before|before\s+(?:litigation|arbitration|court)",
    ):
        return False
    return True
    if not _has_clause(
        text,
        r"(?:escalat|senior\s+management|executive|negotiation)\s+before|before\s+(?:litigation|arbitration|court)",
    ):
        return True
    return False


def check_force_majeure(text: str) -> bool:
    """RULE_23: Force majeure clause must be present."""
    if _has_clause(
        text,
        r"no\s+force\s+majeure\s+clause|force\s+majeure\s+clause\s+is\s+not\s+included|force\s+majeure\s+clause\s+is\s+included",
    ):
        if _has_clause(text, r"no\s+force\s+majeure\s+clause|force\s+majeure\s+clause\s+is\s+not\s+included"):
            return True
        if _has_clause(text, r"force\s+majeure\s+clause\s+is\s+included"):
            return False
    if not _has_clause(
        text,
        r"force\s+majeure|act\s+of\s+god|unforeseeable|impossibility\s+of\s+performance|causes\s+beyond\s+its\s+reasonable\s+control",
    ):
        return True
    return False


def check_assignment_restriction(text: str) -> bool:
    """RULE_24: Contract assignment requires prior written consent."""
    if not _has_clause(text, r"assign"):
        return False
    if _has_clause(text, r"may\s+assign.*without\s+(?:the\s+)?consent|may\s+assign.*without\s+(?:the\s+)?approval"):
        return True
    if not _has_clause(
        text,
        r"(?:assign|assignment).*(?:consent|approval|written\s+consent|prior\s+approval)",
    ):
        return True
    return False


def check_audit_rights(text: str) -> bool:
    """RULE_25: Client must have audit rights over vendor."""
    if not _has_clause(text, r"(?:client|company|buyer)"):
        return False
    if _has_clause(text, r"no\s+audit\s+right|audit\s+not\s+permitted|audit\s+rights.*not\s+granted"):
        return True
    if _has_clause(text, r"(?:audit|inspect|examine).*(?:right|access|upon\s+request)"):
        return False
    return True
    if not _has_clause(text, r"(?:audit|inspect|examine).*(?:right|access|upon\s+request)"):
        return True
    if _has_clause(
        text,
        r"no\s+audit\s+right|audit\s+not\s+permitted|audit\s+rights.*not\s+granted",
    ):
        return True
    return False


def check_insurance_requirements(text: str) -> bool:
    """RULE_26: Vendor must maintain minimum insurance coverage."""
    if not _has_clause(text, r"(?:vendor|supplier|contractor)"):
        return False
    if _has_clause(
        text,
        r"not\s+required\s+to\s+maintain\s+any\s+specific\s+insurance|no\s+insurance\s+coverage|not\s+required.*insurance",
    ):
        return True
    if not _has_clause(
        text,
        r"(?:insurance|coverage|liability\s+insurance|professional\s+indemnity|general\s+liability)",
    ):
        return True
    return False


def check_survival_clause(text: str) -> bool:
    """RULE_27: Key clauses must survive termination."""
    if _has_clause(text, r"no\s+provisions.*surviv|surviv.*not\s+stated|no.*survive\s+termination"):
        return True
    if not _has_clause(text, r"surviv|survive\s+termination|survive\s+expiration"):
        return True
    return False


def check_subcontractor_approval(text: str) -> bool:
    """RULE_28: Subcontracting requires client approval."""
    if not _has_clause(text, r"subcontract"):
        return False
    if _has_clause(
        text,
        r"may\s+engage\s+subcontractors.*without\s+(?:client's\s+)?consent|may\s+assign.*without\s+consent|without\s+client's\s+consent\s+or\s+notification",
    ):
        return True
    if not _has_clause(text, r"subcontract.*(?:consent|approval|written\s+consent|prior\s+approval)"):
        return True
    return False
    if not _has_clause(text, r"subcontract.*(?:consent|approval|written\s+consent|prior\s+approval)"):
        return True
    return False


def check_export_compliance(text: str) -> bool:
    """RULE_29: Export compliance clause required for software/services."""
    if _has_clause(text, r"(?:software|service|technology|data)"):
        if _has_clause(
            text,
            r"no\s+export\s+compliance|no\s+export\s+compliance\s+or\s+trade\s+control\s+provisions|contains\s+no\s+export\s+compliance",
        ):
            return True
        if not _has_clause(text, r"(?:export|export\s+control|ear|itar|sanctions|trade\s+compliance)"):
            return True
    return False


def check_anti_corruption(text: str) -> bool:
    """RULE_30: Anti-corruption / FCPA compliance clause required."""
    if _has_clause(
        text,
        r"no\s+anti[- ]?corruption|no\s+anti[- ]?bribery|anti[- ]?corruption.*not\s+made|no\s+anti[- ]?corruption\s+or\s+anti[- ]?bribery\s+representations",
    ):
        return True
    if not _has_clause(
        text,
        r"(?:anti[- ]?corruption|fcpa|bribery|anti[- ]?bribery|corrupt\s+practices|uk\s+ba)",
    ):
        return True
    return False


# ─── rulebook ──────────────────────────────────────────────────────────────

RULEBOOK: List[PolicyRule] = [
    PolicyRule(
        "RULE_01",
        "LIABILITY",
        "Liability cap must be >= 2x annual contract value",
        "critical",
        check_liability_cap,
    ),
    PolicyRule(
        "RULE_02",
        "PAYMENT",
        "Payment terms must be net-60 or better",
        "high",
        check_payment_terms,
    ),
    PolicyRule(
        "RULE_03",
        "PAYMENT",
        "Auto-renewal requires 90-day written opt-out notice",
        "high",
        check_auto_renewal,
    ),
    PolicyRule(
        "RULE_04",
        "DISPUTE",
        "Governing law must be India or USA (not Singapore/UK)",
        "high",
        check_governing_law,
    ),
    PolicyRule(
        "RULE_05",
        "IP",
        "IP created by vendor is work-for-hire (company owns it)",
        "critical",
        check_ip_work_for_hire,
    ),
    PolicyRule(
        "RULE_06",
        "LIABILITY",
        "Indemnification must be mutual (not one-sided)",
        "critical",
        check_mutual_indemnification,
    ),
    PolicyRule(
        "RULE_07",
        "TERMINATION",
        "Termination for convenience: minimum 30-day notice",
        "medium",
        check_termination_notice,
    ),
    PolicyRule(
        "RULE_08",
        "DATA_PRIVACY",
        "Data processing agreement required if PII is shared",
        "critical",
        check_dpa_required,
    ),
    PolicyRule(
        "RULE_09",
        "LIABILITY",
        "Limitation of liability clause must be present",
        "critical",
        check_limitation_of_liability,
    ),
    PolicyRule(
        "RULE_10",
        "PAYMENT",
        "SLA uptime commitment >= 99.5% for production services",
        "high",
        check_sla_uptime,
    ),
    PolicyRule(
        "RULE_11",
        "TERMINATION",
        "Warranty period minimum 12 months post-delivery",
        "medium",
        check_warranty_period,
    ),
    PolicyRule(
        "RULE_12",
        "DISPUTE",
        "Dispute resolution: arbitration preferred over litigation",
        "low",
        check_dispute_arbitration,
    ),
    PolicyRule(
        "RULE_13",
        "PAYMENT",
        "Late payment penalty clause required",
        "high",
        check_late_payment_penalty,
    ),
    PolicyRule(
        "RULE_14",
        "PAYMENT",
        "Currency fluctuation risk must be shared",
        "medium",
        check_currency_risk,
    ),
    PolicyRule(
        "RULE_15",
        "IP",
        "License-back required on vendor background IP",
        "critical",
        check_background_ip_license,
    ),
    PolicyRule(
        "RULE_16",
        "LIABILITY",
        "Symmetric liability caps required",
        "critical",
        check_asymmetric_liability,
    ),
    PolicyRule(
        "RULE_17",
        "LIABILITY",
        "Mutual consequential damages exclusion",
        "high",
        check_consequential_damages,
    ),
    PolicyRule(
        "RULE_18",
        "DATA_PRIVACY",
        "Indemnification must cover data breaches",
        "critical",
        check_data_breach_indemnity,
    ),
    PolicyRule(
        "RULE_19",
        "PAYMENT",
        "SLA breach penalties/credits required",
        "high",
        check_sla_penalties,
    ),
    PolicyRule(
        "RULE_20",
        "TERMINATION",
        "Vendor may not suspend service without notice",
        "medium",
        check_suspension_notice,
    ),
    PolicyRule(
        "RULE_21",
        "DATA_PRIVACY",
        "Confidentiality period must be >= 3 years",
        "medium",
        check_confidentiality_period,
    ),
    PolicyRule(
        "RULE_22",
        "DISPUTE",
        "Dispute escalation to senior management before litigation",
        "low",
        check_escalation_clause,
    ),
    PolicyRule(
        "RULE_23",
        "LIABILITY",
        "Force majeure clause must be present",
        "medium",
        check_force_majeure,
    ),
    PolicyRule(
        "RULE_24",
        "TERMINATION",
        "Contract assignment requires prior written consent",
        "low",
        check_assignment_restriction,
    ),
    PolicyRule(
        "RULE_25",
        "DATA_PRIVACY",
        "Client must have audit rights over vendor",
        "medium",
        check_audit_rights,
    ),
    PolicyRule(
        "RULE_26",
        "LIABILITY",
        "Vendor must maintain minimum insurance coverage",
        "medium",
        check_insurance_requirements,
    ),
    PolicyRule(
        "RULE_27",
        "TERMINATION",
        "Key clauses must survive termination",
        "low",
        check_survival_clause,
    ),
    PolicyRule(
        "RULE_28",
        "PAYMENT",
        "Subcontracting requires client approval",
        "medium",
        check_subcontractor_approval,
    ),
    PolicyRule(
        "RULE_29",
        "DISPUTE",
        "Export compliance clause required for software/services",
        "low",
        check_export_compliance,
    ),
    PolicyRule(
        "RULE_30",
        "DISPUTE",
        "Anti-corruption / FCPA compliance clause required",
        "low",
        check_anti_corruption,
    ),
]

RULEBOOK_BY_ID: Dict[str, PolicyRule] = {r.rule_id: r for r in RULEBOOK}

CATEGORIES = ["LIABILITY", "PAYMENT", "IP", "DATA_PRIVACY", "TERMINATION", "DISPUTE"]

SEVERITY_WEIGHT = {"critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25}


def run_policy_check(contract_text: str, rule_ids: Optional[List[str]] = None) -> Dict[str, bool]:
    """Run policy checks against contract text. Returns {rule_id: is_violation}."""
    rules = [r for r in RULEBOOK if r.rule_id in (rule_ids or [r.rule_id for r in RULEBOOK])]
    return {r.rule_id: r.check(contract_text) for r in rules}


def get_rule(rule_id: str) -> Optional[PolicyRule]:
    return RULEBOOK_BY_ID.get(rule_id)


def get_rules_by_category(category: str) -> List[PolicyRule]:
    return [r for r in RULEBOOK if r.category == category]
