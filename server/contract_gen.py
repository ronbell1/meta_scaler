"""
Synthetic Contract Generator — procedural generation of procurement contracts.

Generates contracts by combining clause templates and injecting violations
deterministically. Supports 6 contract types: MSA, NDA, SLA, SOW, DPA, Vendor PO.
"""

from __future__ import annotations

import random
import textwrap
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ─── clause templates (compliant versions) ────────────────────────────────

COMPLIANT_CLAUSE_TEMPLATES = {
    "payment_terms": [
        "Client shall pay all undisputed invoices within sixty (60) days of receipt. Late payments shall accrue interest at 1.5% per month.",
        "Payment is due net-60 days from invoice date. Overdue amounts bear interest at the lesser of 1.5% per month or the maximum rate permitted by law.",
        "All fees are payable within 60 days of invoice. Late payment penalty of 1.5% per month applies to overdue balances.",
    ],
    "liability_cap": [
        "Each party's total aggregate liability under this agreement shall not exceed two times (2x) the annual contract value paid or payable in the twelve (12) months preceding the claim.",
        "Neither party's liability shall exceed twice the fees paid by Client in the twelve-month period immediately before the event giving rise to liability.",
        "Total liability of either party is capped at an amount equal to 2x the annual fees under this Agreement.",
    ],
    "confidentiality": [
        "Each party shall maintain the confidentiality of all Confidential Information for a period of five (5) years from the date of disclosure.",
        "Confidential Information shall be protected for three (3) years following termination or expiration of this Agreement.",
        "The obligations of confidentiality shall survive for a period of five (5) years after the termination of this Agreement.",
    ],
    "governing_law": [
        "This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware, United States of America.",
        "This Agreement is governed by the laws of India, without regard to conflict of law principles.",
        "The laws of the State of New York, United States, shall govern this Agreement.",
    ],
    "ip_ownership": [
        "All work product, inventions, and intellectual property created by Vendor in the performance of this Agreement shall be deemed work-made-for-hire and shall be the sole property of Client.",
        "Vendor hereby assigns to Client all right, title, and interest in and to any work product, deliverables, or inventions created under this Agreement.",
        "All intellectual property rights in deliverables created under this SOW shall vest exclusively in Client upon creation.",
    ],
    "indemnification": [
        "Each party shall indemnify, defend, and hold harmless the other party from and against any third-party claims arising from its breach of this Agreement or its negligent or willful misconduct.",
        "Both parties mutually agree to indemnify each other against claims arising from their respective breach, negligence, or willful misconduct.",
        "Mutual indemnification: each party shall defend and indemnify the other against third-party claims resulting from its own actions or omissions.",
    ],
    "termination": [
        "Either party may terminate this Agreement for convenience upon sixty (60) days' prior written notice to the other party.",
        "This Agreement may be terminated by either party with sixty (60) days' written notice.",
        "Termination for convenience is permitted upon ninety (90) days' prior written notice.",
    ],
    "sla_uptime": [
        "Vendor shall maintain a minimum uptime availability of 99.9% for all production services, measured monthly. Service credits apply for any shortfall below this threshold.",
        "System availability shall be no less than 99.95% during any calendar month. Failure to meet this target results in service credits as defined in Schedule A.",
        "Vendor guarantees 99.9% uptime for production environments. Service credits of 5% of monthly fees apply for each 0.1% below the target.",
    ],
    "data_privacy": [
        "Where Vendor processes personal data on behalf of Client, the parties shall execute a Data Processing Agreement (DPA) incorporating standard contractual clauses. Vendor shall comply with all applicable data protection laws including GDPR.",
        "Vendor shall process personal data only in accordance with Client's documented instructions and shall implement appropriate technical and organizational measures. A Data Processing Agreement is attached as Exhibit B.",
        "The parties acknowledge that a Data Processing Agreement governs all processing of personal data under this Agreement. Vendor certifies compliance with GDPR and applicable privacy laws.",
    ],
    "force_majeure": [
        "Neither party shall be liable for any failure or delay in performance due to causes beyond its reasonable control, including acts of God, war, terrorism, labor disputes, or government actions.",
        "Performance excused by force majeure events including natural disasters, war, civil unrest, or government orders. Affected party must notify the other within 5 business days.",
        "Neither party is responsible for delays caused by force majeure events. The affected party shall use commercially reasonable efforts to mitigate the impact.",
    ],
    "dispute_resolution": [
        "Any dispute arising under this Agreement shall first be submitted to good-faith negotiation between senior executives. If unresolved within 30 days, the dispute shall be resolved by binding arbitration under the rules of the American Arbitration Association.",
        "Disputes shall be escalated to senior management for resolution. If not resolved within 30 days, disputes shall be submitted to binding arbitration in accordance with ICC rules.",
        "The parties agree to attempt resolution through executive negotiation before pursuing arbitration. Arbitration shall be conducted under AAA Commercial Rules.",
    ],
    "auto_renewal": [
        "This Agreement shall automatically renew for successive one-year terms unless either party provides written notice of non-renewal at least ninety (90) days prior to the end of the then-current term.",
        "The Agreement renews automatically for additional one-year periods unless either party gives at least 90 days' prior written notice of intent not to renew.",
        "Automatic renewal for successive 12-month periods applies unless terminated with 90 days' written opt-out notice before the renewal date.",
    ],
    "warranty": [
        "Vendor warrants that all deliverables shall be free from material defects for a period of eighteen (18) months from delivery. Vendor shall remedy any non-conforming deliverables at no additional cost.",
        "Vendor provides a warranty of 12 months from delivery against material defects. Defective deliverables will be repaired or replaced at Vendor's expense.",
        "All services and deliverables are warranted to be free from defects for 24 months from the date of acceptance.",
    ],
    "consequential_damages": [
        "Neither party shall be liable to the other for any indirect, incidental, special, consequential, or punitive damages, including lost profits, regardless of the form of action.",
        "Both parties mutually waive any claim for consequential, indirect, incidental, or punitive damages arising out of or related to this Agreement.",
        "Each party's exclusion of consequential damages applies mutually. Neither party may claim lost profits or indirect damages from the other.",
    ],
    "assignment": [
        "Neither party may assign this Agreement without the prior written consent of the other party, which shall not be unreasonably withheld.",
        "Assignment of this Agreement or any rights hereunder requires the express prior written consent of both parties.",
        "No party shall transfer or assign its rights or obligations under this Agreement without the other party's prior written approval.",
    ],
    "audit_rights": [
        "Client shall have the right, upon reasonable notice and during normal business hours, to audit Vendor's records and facilities relevant to the performance of this Agreement, no more than once per calendar year.",
        "Vendor shall permit Client or its designated auditor to inspect relevant records and systems annually, with 30 days' prior written notice.",
        "Client may conduct an annual audit of Vendor's compliance with this Agreement upon 30 days' written notice and during normal business hours.",
    ],
    "insurance": [
        "Vendor shall maintain commercial general liability insurance of not less than $2,000,000 per occurrence, professional liability insurance of not less than $1,000,000, and workers' compensation as required by law.",
        "Vendor shall carry general liability insurance of at least $2M per occurrence and professional indemnity insurance of at least $1M throughout the term of this Agreement.",
        "Throughout the Agreement term, Vendor shall maintain: (a) general liability insurance of $2M; (b) professional liability of $1M; (c) cyber liability of $1M.",
    ],
    "survival": [
        "The provisions regarding confidentiality, indemnification, limitation of liability, intellectual property, and payment obligations shall survive termination or expiration of this Agreement.",
        "Sections relating to confidentiality, IP ownership, indemnification, liability, and payment shall survive the termination of this Agreement for their respective specified periods.",
        "Upon termination, the following provisions shall survive: confidentiality, indemnification, limitation of liability, IP rights, and any accrued payment obligations.",
    ],
    "subcontracting": [
        "Vendor shall not subcontract any portion of the services without Client's prior written consent. Approved subcontractors shall be bound by terms no less restrictive than this Agreement.",
        "Subcontracting requires Client's prior written approval. Vendor remains fully responsible for the acts and omissions of its subcontractors.",
        "Vendor may not engage subcontractors without Client's express written consent. All subcontractors must execute confidentiality and IP assignment agreements.",
    ],
    "export_compliance": [
        "Vendor shall comply with all applicable export control laws and regulations, including the U.S. Export Administration Regulations (EAR) and the International Traffic in Arms Regulations (ITAR).",
        "Both parties agree to comply with all applicable export and import laws, including U.S. sanctions and export control regulations.",
        "Vendor certifies that its performance under this Agreement complies with all applicable export control laws, including EAR, ITAR, and OFAC sanctions programs.",
    ],
    "anti_corruption": [
        "Each party represents and warrants that it has not and will not offer, pay, or promise to pay anything of value to any government official in violation of the U.S. Foreign Corrupt Practices Act (FCPA) or the UK Bribery Act.",
        "Both parties shall comply with all applicable anti-corruption laws, including the FCPA and the UK Bribery Act 2010. No bribes, kickbacks, or improper payments shall be made.",
        "Each party certifies compliance with anti-bribery and anti-corruption laws including the FCPA, UK Bribery Act, and all applicable local anti-corruption statutes.",
    ],
    "suspension": [
        "Vendor may suspend services only upon thirty (30) days' prior written notice to Client and only for material breach of payment obligations that remains uncured.",
        "Service suspension by Vendor requires 30 days' written notice and may only occur for uncured material payment default.",
        "Vendor shall not suspend services without providing at least 30 days' prior written notice and a reasonable opportunity to cure.",
    ],
    "background_ip": [
        "Each party retains ownership of its pre-existing intellectual property. Vendor grants Client a perpetual, non-exclusive, royalty-free license to use Vendor's background IP incorporated in the deliverables.",
        "Background intellectual property remains the property of its owner. Client receives a perpetual license to use any Vendor background IP embedded in deliverables.",
        "Vendor's pre-existing IP remains Vendor's property. A perpetual, worldwide, non-exclusive license to use such background IP is granted to Client for the deliverables.",
    ],
    "currency": [
        "All amounts are in USD. Currency fluctuation risk shall be shared equally between the parties. If exchange rate variation exceeds 5% from the baseline rate, the parties shall negotiate in good faith to adjust pricing.",
        "Fees are denominated in USD. Both parties share currency exchange risk. Price adjustments apply if the exchange rate moves more than 5% from the rate at execution.",
        "Payment currency is USD. Exchange rate risk above a 5% threshold from the baseline shall be shared equally by both parties.",
    ],
}


# ─── violation clause templates ───────────────────────────────────────────

VIOLATION_CLAUSE_TEMPLATES = {
    "RULE_01": [
        "Vendor's total aggregate liability under this Agreement shall be limited to the fees paid by Client in the preceding six (6) months.",
        "Vendor's liability is capped at the amount of fees paid in the three (3) months immediately preceding the claim.",
    ],
    "RULE_02": [
        "Client shall pay all invoices within thirty (30) days of receipt.",
        "Payment is due net-30 days from the invoice date.",
    ],
    "RULE_03": [
        "This Agreement shall automatically renew for successive one-year terms unless either party provides written notice of non-renewal at least thirty (30) days prior to the end of the then-current term.",
        "The Agreement renews automatically unless terminated with 60 days' prior written notice.",
    ],
    "RULE_04": [
        "This Agreement shall be governed by and construed in accordance with the laws of Singapore.",
        "This Agreement is governed by the laws of England and Wales.",
    ],
    "RULE_05": [
        "All work product created by Vendor in the performance of this Agreement shall remain the property of Vendor. Client receives a limited, non-exclusive license to use deliverables for internal purposes only.",
        "All inventions and intellectual property created during the engagement shall be owned exclusively by Supplier.",
    ],
    "RULE_06": [
        "Client shall indemnify, defend, and hold harmless Vendor from and against any third-party claims arising from Client's use of the services. Vendor provides no indemnification to Client.",
        "Client agrees to indemnify Vendor for all claims. No reciprocal indemnification is provided.",
    ],
    "RULE_07": [
        "Either party may terminate this Agreement for convenience upon seven (7) days' prior written notice.",
        "This Agreement may be terminated by either party with fifteen (15) days' written notice.",
    ],
    "RULE_08": [
        "Vendor may process personal data as necessary to perform the services. No separate Data Processing Agreement is executed. GDPR obligations are not specifically addressed.",
        "No data processing agreement is referenced. Vendor processes personal data under the terms of this Agreement only.",
    ],
    "RULE_09": [
        "There is no limitation of liability clause in this Agreement. Neither party's liability is capped or limited in any way.",
    ],
    "RULE_10": [
        "Vendor shall maintain a minimum uptime availability of 95.0% for production services, measured monthly.",
        "System availability target is 99.0%. No service credits are defined for shortfall.",
    ],
    "RULE_11": [
        "Vendor warrants deliverables for a period of six (6) months from delivery.",
        "The warranty period for all deliverables is three (3) months from the date of acceptance.",
    ],
    "RULE_12": [
        "All disputes arising under this Agreement shall be resolved exclusively in the courts of Vendor's home jurisdiction. No arbitration mechanism is provided.",
        "Any dispute shall be litigated exclusively in the courts of Singapore. Neither party may seek arbitration.",
    ],
    "RULE_13": [
        "Client shall pay invoices within the specified period. Late payments incur no penalty or interest.",
        "No late payment penalty or interest applies to overdue invoices.",
    ],
    "RULE_14": [
        "All amounts are in USD. Currency fluctuation risk shall be borne entirely by Client.",
        "Exchange rate variations are the sole responsibility of Client. No price adjustment mechanism exists.",
    ],
    "RULE_15": [
        "Vendor retains all rights to its background intellectual property. Client receives no license to use Vendor's pre-existing IP incorporated in deliverables.",
        "No license is granted to Client on Vendor's background or pre-existing intellectual property.",
    ],
    "RULE_16": [
        "Vendor's total liability is unlimited. Client's total liability is capped at $1,000.",
        "Vendor's liability is uncapped and unlimited. Client's aggregate liability shall not exceed $5,000.",
    ],
    "RULE_17": [
        "Vendor excludes all consequential and indirect damages. Client's exclusion of consequential damages is not addressed.",
        "Consequential damages are excluded only for Vendor. Client remains liable for all categories of damages.",
    ],
    "RULE_18": [
        "Vendor's indemnification obligations exclude any claims arising from data breaches or security incidents involving personal data.",
        "Indemnification does not cover data breach events or unauthorized access to personal information.",
    ],
    "RULE_19": [
        "Vendor shall maintain 99.9% uptime. No financial penalties, service credits, or remedies are defined for failure to meet this target.",
        "SLA uptime target is defined but no penalties or credits apply for breach of the SLA.",
    ],
    "RULE_20": [
        "Vendor may suspend services immediately and without prior notice for any suspected breach of this Agreement.",
        "Vendor reserves the right to suspend service at any time without notice.",
    ],
    "RULE_21": [
        "Each party shall maintain the confidentiality of the other party's Confidential Information for a period of one (1) year from the date of disclosure.",
        "Confidentiality obligations shall survive for twelve (12) months following termination.",
    ],
    "RULE_22": [
        "Any dispute may be pursued directly in court without any requirement for prior escalation or negotiation.",
    ],
    "RULE_23": [
        "No force majeure clause is included in this Agreement.",
    ],
    "RULE_24": [
        "Either party may assign this Agreement to any third party without the consent of the other party.",
    ],
    "RULE_25": [
        "Client shall have no right to audit Vendor's records, facilities, or systems related to performance of this Agreement.",
        "No audit rights are granted to Client under this Agreement.",
    ],
    "RULE_26": [
        "Vendor is not required to maintain any specific insurance coverage as a condition of this Agreement.",
    ],
    "RULE_27": [
        "No provisions of this Agreement are stated to survive termination or expiration.",
    ],
    "RULE_28": [
        "Vendor may engage subcontractors to perform any portion of the services without Client's consent or notification.",
    ],
    "RULE_29": [
        "No export compliance or trade control provisions are included in this Agreement.",
    ],
    "RULE_30": [
        "No anti-corruption or anti-bribery representations are made by either party.",
    ],
}


# ─── contract structure templates ─────────────────────────────────────────

CONTRACT_STRUCTURES = {
    "MSA": {
        "sections": [
            (
                "PREAMBLE",
                'This Master Service Agreement ("Agreement") is entered into as of the Effective Date by and between the parties identified in the applicable Statement of Work.',
            ),
            (
                "SERVICES",
                'Vendor agrees to provide the services described in each Statement of Work ("SOW") executed under this Agreement. Each SOW shall reference this Agreement and is subject to its terms.',
            ),
            ("PAYMENT TERMS", "{payment_terms}"),
            ("TERM AND RENEWAL", "{auto_renewal}"),
            ("INTELLECTUAL PROPERTY", "{ip_ownership}"),
            ("CONFIDENTIALITY", "{confidentiality}"),
            ("LIMITATION OF LIABILITY", "{liability_cap}"),
            ("INDEMNIFICATION", "{indemnification}"),
            ("DATA PROTECTION", "{data_privacy}"),
            ("SERVICE LEVELS", "{sla_uptime}"),
            ("WARRANTY", "{warranty}"),
            ("TERMINATION", "{termination}"),
            ("DISPUTE RESOLUTION", "{dispute_resolution}"),
            ("FORCE MAJEURE", "{force_majeure}"),
            ("ASSIGNMENT", "{assignment}"),
            ("AUDIT RIGHTS", "{audit_rights}"),
            ("INSURANCE", "{insurance}"),
            ("SURVIVAL", "{survival}"),
            ("SUBCONTRACTING", "{subcontracting}"),
            ("EXPORT COMPLIANCE", "{export_compliance}"),
            ("ANTI-CORRUPTION", "{anti_corruption}"),
            (
                "GENERAL",
                "This Agreement constitutes the entire agreement between the parties and supersedes all prior agreements. Amendments must be in writing and signed by both parties.",
            ),
        ]
    },
    "NDA": {
        "sections": [
            (
                "PREAMBLE",
                'This Non-Disclosure Agreement ("Agreement") is entered into by and between the parties for the purpose of protecting Confidential Information exchanged in connection with a potential business relationship.',
            ),
            (
                "DEFINITION OF CONFIDENTIAL INFORMATION",
                '"Confidential Information" means all non-public information disclosed by either party, including technical data, trade secrets, business plans, and customer information.',
            ),
            ("CONFIDENTIALITY OBLIGATIONS", "{confidentiality}"),
            (
                "PERMITTED DISCLOSURES",
                "Receiving party may disclose Confidential Information to employees and contractors who have a need to know and are bound by confidentiality obligations no less restrictive than this Agreement.",
            ),
            (
                "TERM",
                "This Agreement shall remain in effect for three (3) years from the Effective Date. Confidentiality obligations survive for five (5) years after termination.",
            ),
            (
                "RETURN OF MATERIALS",
                "Upon termination, each party shall return or destroy all Confidential Information of the other party upon written request.",
            ),
            (
                "REMEDIES",
                "Each party acknowledges that unauthorized disclosure of Confidential Information may cause irreparable harm, and the disclosing party shall be entitled to seek injunctive relief.",
            ),
            ("GOVERNING LAW", "{governing_law}"),
            ("DISPUTE RESOLUTION", "{dispute_resolution}"),
            (
                "GENERAL",
                "This Agreement constitutes the entire understanding between the parties regarding the subject matter hereof.",
            ),
        ]
    },
    "SLA": {
        "sections": [
            (
                "PREAMBLE",
                'This Service Level Agreement ("SLA") sets forth the service levels, performance metrics, and remedies applicable to the services provided under the Master Service Agreement.',
            ),
            ("SERVICE AVAILABILITY", "{sla_uptime}"),
            (
                "MAINTENANCE WINDOWS",
                "Scheduled maintenance shall not exceed 8 hours per month and shall be performed during off-peak hours with at least 48 hours' prior notice.",
            ),
            (
                "INCIDENT RESPONSE",
                "Vendor shall respond to Priority 1 incidents within 1 hour and Priority 2 incidents within 4 hours. Resolution targets are defined in Schedule A.",
            ),
            (
                "SERVICE CREDITS",
                "Service credits for SLA failures are calculated as a percentage of monthly fees, ranging from 5% for minor shortfalls to 25% for severe or prolonged outages.",
            ),
            (
                "REPORTING",
                "Vendor shall provide monthly service level reports within 10 business days of each calendar month end.",
            ),
            ("ESCALATION", "{escalation_clause}"),
            ("SUSPENSION", "{suspension}"),
            ("FORCE MAJEURE", "{force_majeure}"),
            (
                "GENERAL",
                "This SLA is incorporated by reference into the Master Service Agreement. In case of conflict, the MSA terms prevail.",
            ),
        ]
    },
    "SOW": {
        "sections": [
            (
                "PREAMBLE",
                'This Statement of Work ("SOW") is issued under the Master Service Agreement dated [Effective Date] between the parties.',
            ),
            (
                "SCOPE OF WORK",
                "Vendor shall perform the services and deliver the deliverables described in this SOW in accordance with the specifications and timelines set forth herein.",
            ),
            (
                "DELIVERABLES",
                "Vendor shall deliver the items specified in Schedule A. Each deliverable shall meet the acceptance criteria defined therein.",
            ),
            (
                "TIMELINE",
                "Services shall commence on the Start Date and shall be completed by the End Date, subject to the milestones defined in Schedule B.",
            ),
            ("FEES AND PAYMENT", "{payment_terms}"),
            ("INTELLECTUAL PROPERTY", "{ip_ownership}"),
            (
                "ACCEPTANCE CRITERIA",
                "Client shall have 15 business days to test and accept each deliverable. Non-conforming deliverables shall be remedied by Vendor at no additional cost within 10 business days.",
            ),
            ("WARRANTY", "{warranty}"),
            ("TERMINATION", "{termination}"),
            ("SUBCONTRACTING", "{subcontracting}"),
            (
                "GENERAL",
                "This SOW is governed by the terms of the Master Service Agreement. Capitalized terms not defined herein have the meanings given in the MSA.",
            ),
        ]
    },
    "DPA": {
        "sections": [
            (
                "PREAMBLE",
                'This Data Processing Agreement ("DPA") governs the processing of personal data by Vendor on behalf of Client under the Master Service Agreement.',
            ),
            (
                "DEFINITIONS",
                '"Personal Data," "Processing," "Data Subject," and "Supervisory Authority" have the meanings given in the GDPR.',
            ),
            (
                "PROCESSING INSTRUCTIONS",
                "Vendor shall process Personal Data only on documented instructions from Client, including with regard to transfers of Personal Data to a third country.",
            ),
            (
                "CONFIDENTIALITY",
                "Vendor shall ensure that persons authorized to process Personal Data are committed to confidentiality or under an appropriate statutory obligation of confidentiality.",
            ),
            (
                "DATA SUBJECT RIGHTS",
                "Vendor shall assist Client in responding to requests for exercising Data Subject rights under the GDPR, including access, rectification, erasure, and portability requests.",
            ),
            (
                "SECURITY MEASURES",
                "Vendor shall implement appropriate technical and organizational measures to ensure a level of security appropriate to the risk, including encryption, pseudonymization, and regular testing.",
            ),
            (
                "DATA BREACH NOTIFICATION",
                "Vendor shall notify Client without undue delay, and in any event within 24 hours, upon becoming aware of a personal data breach.",
            ),
            (
                "SUB-PROCESSORS",
                "Vendor shall not engage another processor (sub-processor) without prior specific or general written authorization from Client.",
            ),
            (
                "INTERNATIONAL TRANSFERS",
                "Transfers of Personal Data outside the EEA shall be subject to appropriate safeguards, including Standard Contractual Clauses approved by the European Commission.",
            ),
            ("AUDIT AND INSPECTION", "{audit_rights}"),
            (
                "TERM AND TERMINATION",
                "This DPA remains in effect for the duration of the services. Upon termination, Vendor shall return or delete all Personal Data.",
            ),
            ("GOVERNING LAW", "{governing_law}"),
            (
                "GENERAL",
                "This DPA is incorporated into and forms part of the Master Service Agreement. In case of conflict, this DPA prevails with respect to Personal Data processing.",
            ),
        ]
    },
    "VENDOR_PO": {
        "sections": [
            (
                "PREAMBLE",
                'This Purchase Order ("PO") is issued by Client to Vendor for the goods and/or services described herein, subject to the terms of the Master Service Agreement.',
            ),
            (
                "GOODS/SERVICES DESCRIPTION",
                "Vendor shall supply the goods and/or services as specified in the attached Schedule of Requirements.",
            ),
            ("PRICING AND PAYMENT", "{payment_terms}"),
            (
                "DELIVERY",
                "Goods shall be delivered DDP Client's designated facility. Services shall be performed at the locations and times specified in the Schedule.",
            ),
            (
                "INSPECTION AND ACCEPTANCE",
                "Client shall inspect all delivered goods within 10 business days of receipt. Non-conforming goods shall be replaced at Vendor's expense.",
            ),
            ("WARRANTY", "{warranty}"),
            (
                "TITLE AND RISK",
                "Title and risk of loss pass to Client upon delivery and acceptance at Client's facility.",
            ),
            ("INSURANCE", "{insurance}"),
            ("TERMINATION", "{termination}"),
            ("FORCE MAJEURE", "{force_majeure}"),
            ("EXPORT COMPLIANCE", "{export_compliance}"),
            ("ANTI-CORRUPTION", "{anti_corruption}"),
            ("GOVERNING LAW", "{governing_law}"),
            ("DISPUTE RESOLUTION", "{dispute_resolution}"),
            (
                "GENERAL",
                "This PO is subject to the terms and conditions of the Master Service Agreement. In case of conflict, the MSA prevails.",
            ),
        ]
    },
}


# ─── generator ────────────────────────────────────────────────────────────


@dataclass
class ContractPackage:
    """A single contract or multi-document package."""

    documents: Dict[str, str]
    injected_violations: Dict[str, List[str]]
    cross_doc_violations: List[Tuple[str, str, str]]
    ambiguity_level: int
    red_herrings: int
    seed: int


class ContractGenerator:
    """Procedural synthetic contract generator."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)

    def _pick_template(self, key: str, templates: Dict[str, List[str]]) -> str:
        if key in templates:
            return self.rng.choice(templates[key])
        return ""

    def _build_contract(
        self,
        contract_type: str,
        violations: Optional[List[str]] = None,
        ambiguity_level: int = 0,
        red_herrings: int = 0,
    ) -> Tuple[str, List[str]]:
        """Build a single contract text with injected violations."""
        violations = violations or []
        structure = CONTRACT_STRUCTURES.get(contract_type, CONTRACT_STRUCTURES["MSA"])

        clause_map = {}
        for key in COMPLIANT_CLAUSE_TEMPLATES:
            clause_map[key] = self._pick_template(key, COMPLIANT_CLAUSE_TEMPLATES)

        for rule_id in violations:
            if rule_id in VIOLATION_CLAUSE_TEMPLATES:
                violation_clause = self.rng.choice(VIOLATION_CLAUSE_TEMPLATES[rule_id])
                for key, compliant in list(clause_map.items()):
                    if self._rule_maps_to_clause(rule_id, key):
                        clause_map[key] = violation_clause
                        break

        sections = []
        for section_name, section_template in structure["sections"]:
            content = section_template
            for key, value in clause_map.items():
                content = content.replace("{" + key + "}", value)
            sections.append(f"{section_name}\n{content}")

        if red_herrings > 0:
            sections.append(
                "RED HERRING CLAUSE\n"
                "The parties acknowledge that certain provisions may appear unfavorable but are "
                "balanced by corresponding protections elsewhere in this Agreement or its exhibits. "
                "No party shall claim a violation based solely on the apparent one-sidedness of any "
                "single clause without considering the Agreement as a whole, including all exhibits "
                "and schedules incorporated by reference."
            )

        contract_text = "\n\n".join(sections)
        return contract_text, violations

    def _rule_maps_to_clause(self, rule_id: str, clause_key: str) -> bool:
        mapping = {
            "RULE_01": "liability_cap",
            "RULE_02": "payment_terms",
            "RULE_03": "auto_renewal",
            "RULE_04": "governing_law",
            "RULE_05": "ip_ownership",
            "RULE_06": "indemnification",
            "RULE_07": "termination",
            "RULE_08": "data_privacy",
            "RULE_09": "liability_cap",
            "RULE_10": "sla_uptime",
            "RULE_11": "warranty",
            "RULE_12": "dispute_resolution",
            "RULE_13": "payment_terms",
            "RULE_14": "currency",
            "RULE_15": "background_ip",
            "RULE_16": "liability_cap",
            "RULE_17": "consequential_damages",
            "RULE_18": "indemnification",
            "RULE_19": "sla_uptime",
            "RULE_20": "suspension",
            "RULE_21": "confidentiality",
            "RULE_22": "dispute_resolution",
            "RULE_23": "force_majeure",
            "RULE_24": "assignment",
            "RULE_25": "audit_rights",
            "RULE_26": "insurance",
            "RULE_27": "survival",
            "RULE_28": "subcontracting",
            "RULE_29": "export_compliance",
            "RULE_30": "anti_corruption",
        }
        return mapping.get(rule_id) == clause_key

    def generate(
        self,
        contract_type: str = "MSA",
        violations: Optional[List[str]] = None,
        ambiguity_level: int = 0,
        red_herrings: int = 0,
    ) -> str:
        """Generate a single contract with specified violations."""
        text, _ = self._build_contract(
            contract_type=contract_type,
            violations=violations or [],
            ambiguity_level=ambiguity_level,
            red_herrings=red_herrings,
        )
        return text

    def generate_package(
        self,
        documents: List[str],
        violations: Optional[Dict[str, List[str]]] = None,
        cross_doc_violations: Optional[List[Tuple[str, str, str]]] = None,
        ambiguity_level: int = 0,
        red_herrings: int = 0,
    ) -> ContractPackage:
        """Generate a multi-document contract package."""
        violations = violations or {}
        cross_doc = cross_doc_violations or []
        doc_texts = {}

        for doc_type in documents:
            doc_violations = violations.get(doc_type, [])
            text, _ = self._build_contract(
                contract_type=doc_type,
                violations=doc_violations,
                ambiguity_level=ambiguity_level,
                red_herrings=0,
            )
            doc_texts[doc_type] = text

        if red_herrings > 0:
            first_doc = list(doc_texts.keys())[0]
            doc_texts[first_doc] += (
                "\n\nEXHIBIT A — SUPPLEMENTARY TERMS\n"
                "Notwithstanding any provision to the contrary in this Agreement, the parties "
                "agree that intellectual property rights in work product created by Vendor shall "
                "be assigned to Client as work-made-for-hire. This Exhibit A controls over any "
                "conflicting provision in the main body of this Agreement."
            )

        return ContractPackage(
            documents=doc_texts,
            injected_violations=violations,
            cross_doc_violations=cross_doc,
            ambiguity_level=ambiguity_level,
            red_herrings=red_herrings,
            seed=self.seed,
        )
