"""Unit tests for the policy engine — 30 deterministic rule checkers."""

import pytest

from server.policy_engine import (
    RULEBOOK,
    RULEBOOK_BY_ID,
    SEVERITY_WEIGHT,
    CATEGORIES,
    PolicyRule,
    run_policy_check,
    get_rule,
    get_rules_by_category,
    check_liability_cap,
    check_payment_terms,
    check_auto_renewal,
    check_governing_law,
    check_ip_work_for_hire,
    check_mutual_indemnification,
    check_termination_notice,
    check_dpa_required,
    check_limitation_of_liability,
    check_sla_uptime,
    check_warranty_period,
    check_dispute_arbitration,
    check_late_payment_penalty,
    check_currency_risk,
    check_background_ip_license,
    check_asymmetric_liability,
    check_consequential_damages,
    check_data_breach_indemnity,
    check_sla_penalties,
    check_suspension_notice,
    check_confidentiality_period,
    check_escalation_clause,
    check_force_majeure,
    check_assignment_restriction,
    check_audit_rights,
    check_insurance_requirements,
    check_survival_clause,
    check_subcontractor_approval,
    check_export_compliance,
    check_anti_corruption,
)


class TestRulebookStructure:
    def test_rulebook_has_30_rules(self):
        assert len(RULEBOOK) == 30

    def test_all_rule_ids_are_unique(self):
        rule_ids = [r.rule_id for r in RULEBOOK]
        assert len(rule_ids) == len(set(rule_ids))

    def test_rulebook_by_id_matches_rulebook(self):
        assert len(RULEBOOK_BY_ID) == 30
        for rule in RULEBOOK:
            assert RULEBOOK_BY_ID[rule.rule_id] is rule

    def test_severity_weights_cover_all_levels(self):
        assert SEVERITY_WEIGHT["critical"] == 1.0
        assert SEVERITY_WEIGHT["high"] == 0.75
        assert SEVERITY_WEIGHT["medium"] == 0.5
        assert SEVERITY_WEIGHT["low"] == 0.25

    def test_categories_are_correct(self):
        expected = {"LIABILITY", "PAYMENT", "IP", "DATA_PRIVACY", "TERMINATION", "DISPUTE"}
        assert set(CATEGORIES) == expected

    def test_all_rules_have_valid_categories(self):
        for rule in RULEBOOK:
            assert rule.category in CATEGORIES

    def test_all_rules_have_valid_severity(self):
        for rule in RULEBOOK:
            assert rule.severity in SEVERITY_WEIGHT

    def test_rule_ids_are_sequential(self):
        for i, rule in enumerate(RULEBOOK, 1):
            assert rule.rule_id == f"RULE_{i:02d}"


class TestRuleCheckers:
    def test_check_liability_cap_violation(self):
        text = "Vendor's total aggregate liability under this Agreement shall be limited to the fees paid by Client in the preceding six (6) months."
        assert check_liability_cap(text) is True

    def test_check_liability_cap_compliant(self):
        text = "Liability shall not exceed two times (2x) the annual contract value paid in the twelve (12) months preceding the claim."
        assert check_liability_cap(text) is False

    def test_check_liability_cap_no_clause(self):
        text = "This is a simple contract with no liability mentions."
        assert check_liability_cap(text) is False

    def test_check_payment_terms_violation(self):
        text = "Client shall pay all invoices within thirty (30) days of receipt."
        assert check_payment_terms(text) is True

    def test_check_payment_terms_compliant(self):
        text = "Payment is due net-60 days from invoice date."
        assert check_payment_terms(text) is False

    def test_check_auto_renewal_violation(self):
        text = "This Agreement shall automatically renew for successive one-year terms unless either party provides written notice of non-renewal at least thirty (30) days prior to the end of the then-current term."
        assert check_auto_renewal(text) is True

    def test_check_auto_renewal_compliant(self):
        text = "This Agreement shall automatically renew for successive one-year terms unless either party provides written notice of non-renewal at least ninety (90) days prior to the end of the then-current term."
        assert check_auto_renewal(text) is False

    def test_check_governing_law_violation(self):
        text = "This Agreement shall be governed by and construed in accordance with the laws of Singapore."
        assert check_governing_law(text) is True

    def test_check_governing_law_compliant(self):
        text = "This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware, United States of America."
        assert check_governing_law(text) is False

    def test_check_ip_work_for_hire_violation(self):
        text = "All work product, inventions, and intellectual property created by Vendor in the performance of this Agreement shall be deemed work-made-for-hire and shall be the sole property of Vendor."
        assert check_ip_work_for_hire(text) is True

    def test_check_ip_work_for_hire_compliant(self):
        text = "All work product, inventions, and intellectual property created by Vendor in the performance of this Agreement shall be deemed work-made-for-hire and shall be the sole property of Client."
        assert check_ip_work_for_hire(text) is False

    def test_check_mutual_indemnification_violation(self):
        text = "Client shall indemnify, defend, and hold harmless Vendor from and against any third-party claims arising from Client's use of the services. Vendor provides no indemnification to Client."
        assert check_mutual_indemnification(text) is True

    def test_check_mutual_indemnification_compliant(self):
        text = "Each party shall indemnify, defend, and hold harmless the other party from and against any third-party claims arising from its breach of this Agreement or its negligent or willful misconduct."
        assert check_mutual_indemnification(text) is False

    def test_check_termination_notice_violation(self):
        text = "Either party may terminate this Agreement for convenience upon seven (7) days' prior written notice to the other party."
        assert check_termination_notice(text) is True

    def test_check_termination_notice_compliant(self):
        text = "Either party may terminate this Agreement for convenience upon sixty (60) days' prior written notice to the other party."
        assert check_termination_notice(text) is False

    def test_check_dpa_required_violation(self):
        text = "Vendor may process personal data on behalf of Client. No separate Data Processing Agreement is executed. GDPR obligations are not specifically addressed."
        assert check_dpa_required(text) is True

    def test_check_dpa_required_compliant(self):
        text = "Where Vendor processes personal data on behalf of Client, the parties shall execute a Data Processing Agreement incorporating standard contractual clauses."
        assert check_dpa_required(text) is False

    def test_check_limitation_of_liability_violation(self):
        text = "There is no limitation of liability clause in this Agreement. Neither party's liability is capped or limited in any way."
        assert check_limitation_of_liability(text) is True

    def test_check_limitation_of_liability_compliant(self):
        text = "Limitation of liability: each party's total aggregate liability under this agreement shall not exceed two times the annual contract value."
        assert check_limitation_of_liability(text) is False

    def test_check_sla_uptime_violation(self):
        text = "Vendor shall maintain a minimum uptime availability of 95.0% for production services, measured monthly."
        assert check_sla_uptime(text) is True

    def test_check_sla_uptime_compliant(self):
        text = "Vendor shall maintain a minimum uptime availability of 99.9% for production services, measured monthly."
        assert check_sla_uptime(text) is False

    def test_check_warranty_period_violation(self):
        text = "Vendor warrants deliverables for a period of six (6) months from delivery."
        assert check_warranty_period(text) is True

    def test_check_warranty_period_compliant(self):
        text = "Vendor warrants that all deliverables shall be free from material defects for a period of eighteen (18) months from delivery."
        assert check_warranty_period(text) is False

    def test_check_dispute_arbitration_violation(self):
        text = "All disputes arising under this Agreement shall be resolved exclusively in the courts of Vendor's home jurisdiction. No arbitration mechanism is provided."
        assert check_dispute_arbitration(text) is True

    def test_check_dispute_arbitration_compliant(self):
        text = "Any dispute arising under this Agreement shall first be submitted to good-faith negotiation between senior executives. If unresolved within 30 days, the dispute shall be resolved by binding arbitration."
        assert check_dispute_arbitration(text) is False

    def test_check_late_payment_penalty_violation(self):
        text = "Client shall pay invoices within the specified period. Late payments incur no penalty or interest."
        assert check_late_payment_penalty(text) is True

    def test_check_late_payment_penalty_compliant(self):
        text = "Client shall pay all undisputed invoices within sixty (60) days of receipt. Late payments shall accrue interest at 1.5% per month."
        assert check_late_payment_penalty(text) is False

    def test_check_currency_risk_violation(self):
        text = "All amounts are in USD. Currency fluctuation risk shall be borne entirely by Client."
        assert check_currency_risk(text) is True

    def test_check_currency_risk_compliant(self):
        text = "All amounts are in USD. Currency fluctuation risk shall be shared equally between the parties."
        assert check_currency_risk(text) is False

    def test_check_background_ip_license_violation(self):
        text = "Vendor retains all rights to its background intellectual property. Client receives no license to use Vendor's pre-existing IP incorporated in deliverables."
        assert check_background_ip_license(text) is True

    def test_check_background_ip_license_compliant(self):
        text = "Each party retains ownership of its pre-existing intellectual property. Vendor grants Client a perpetual, non-exclusive, royalty-free license to use Vendor's background IP incorporated in the deliverables."
        assert check_background_ip_license(text) is False

    def test_check_asymmetric_liability_violation(self):
        text = "Vendor's total liability is unlimited. Client's total liability is capped at $1,000."
        assert check_asymmetric_liability(text) is True

    def test_check_asymmetric_liability_compliant(self):
        text = "Each party's total aggregate liability under this agreement shall not exceed two times the annual contract value."
        assert check_asymmetric_liability(text) is False

    def test_check_consequential_damages_violation(self):
        text = "Vendor excludes all consequential and indirect damages. Client's exclusion of consequential damages is not addressed."
        assert check_consequential_damages(text) is True

    def test_check_consequential_damages_compliant(self):
        text = "Neither party shall be liable to the other for any indirect, incidental, special, consequential, or punitive damages, including lost profits, regardless of the form of action."
        assert check_consequential_damages(text) is False

    def test_check_data_breach_indemnity_violation(self):
        text = "Vendor's indemnification obligations exclude any claims arising from data breaches or security incidents involving personal data."
        assert check_data_breach_indemnity(text) is True

    def test_check_data_breach_indemnity_compliant(self):
        text = "Each party shall indemnify, defend, and hold harmless the other party from and against any third-party claims arising from data breaches."
        assert check_data_breach_indemnity(text) is False

    def test_check_sla_penalties_violation(self):
        text = "Vendor shall maintain 99.9% uptime. No financial penalties, service credits, or remedies are defined for failure to meet this target."
        assert check_sla_penalties(text) is True

    def test_check_sla_penalties_compliant(self):
        text = "Service credits for SLA failures are calculated as a percentage of monthly fees, ranging from 5% for minor shortfalls to 25% for severe outages."
        assert check_sla_penalties(text) is False

    def test_check_suspension_notice_violation(self):
        text = "Vendor may suspend services immediately and without prior notice for any suspected breach of this Agreement."
        assert check_suspension_notice(text) is True

    def test_check_suspension_notice_compliant(self):
        text = "Vendor may suspend services only upon thirty (30) days' prior written notice to Client and only for material breach of payment obligations."
        assert check_suspension_notice(text) is False

    def test_check_confidentiality_period_violation(self):
        text = "Each party shall maintain the confidentiality of the other party's Confidential Information for a period of one (1) year from the date of disclosure."
        assert check_confidentiality_period(text) is True

    def test_check_confidentiality_period_compliant(self):
        text = "Each party shall maintain the confidentiality of all Confidential Information for a period of five (5) years from the date of disclosure."
        assert check_confidentiality_period(text) is False

    def test_check_escalation_clause_violation(self):
        text = (
            "Any dispute may be pursued directly in court without any requirement for prior escalation or negotiation."
        )
        assert check_escalation_clause(text) is True

    def test_check_escalation_clause_compliant(self):
        text = "Any dispute arising under this Agreement shall first be submitted to good-faith negotiation between senior executives before pursuing arbitration."
        assert check_escalation_clause(text) is False

    def test_check_force_majeure_violation(self):
        text = "No force majeure clause is included in this Agreement."
        assert check_force_majeure(text) is True

    def test_check_force_majeure_compliant(self):
        text = "Neither party shall be liable for any failure or delay in performance due to causes beyond its reasonable control, including acts of God, war, terrorism, labor disputes, or government actions."
        assert check_force_majeure(text) is False

    def test_check_assignment_restriction_violation(self):
        text = "Either party may assign this Agreement to any third party without the consent of the other party."
        assert check_assignment_restriction(text) is True

    def test_check_assignment_restriction_compliant(self):
        text = "Neither party may assign this Agreement without the prior written consent of the other party, which shall not be unreasonably withheld."
        assert check_assignment_restriction(text) is False

    def test_check_audit_rights_violation(self):
        text = "Client shall have no right to audit Vendor's records, facilities, or systems related to performance of this Agreement."
        assert check_audit_rights(text) is True

    def test_check_audit_rights_compliant(self):
        text = "Client shall have the right, upon reasonable notice and during normal business hours, to audit Vendor's records and facilities relevant to the performance of this Agreement."
        assert check_audit_rights(text) is False

    def test_check_insurance_requirements_violation(self):
        text = "Vendor is not required to maintain any specific insurance coverage as a condition of this Agreement."
        assert check_insurance_requirements(text) is True

    def test_check_insurance_requirements_compliant(self):
        text = "Vendor shall maintain commercial general liability insurance of not less than $2,000,000 per occurrence, professional liability insurance of not less than $1,000,000."
        assert check_insurance_requirements(text) is False

    def test_check_survival_clause_violation(self):
        text = "No provisions of this Agreement are stated to survive termination or expiration."
        assert check_survival_clause(text) is True

    def test_check_survival_clause_compliant(self):
        text = "The provisions regarding confidentiality, indemnification, limitation of liability, intellectual property, and payment obligations shall survive termination or expiration of this Agreement."
        assert check_survival_clause(text) is False

    def test_check_subcontractor_approval_violation(self):
        text = "Vendor may engage subcontractors to perform any portion of the services without Client's consent or notification."
        assert check_subcontractor_approval(text) is True

    def test_check_subcontractor_approval_compliant(self):
        text = "Vendor shall not subcontract any portion of the services without Client's prior written consent. Approved subcontractors shall be bound by terms no less restrictive than this Agreement."
        assert check_subcontractor_approval(text) is False

    def test_check_export_compliance_violation(self):
        text = "This software service agreement contains no export compliance or trade control provisions whatsoever."
        assert check_export_compliance(text) is True

    def test_check_export_compliance_compliant(self):
        text = "Vendor shall comply with all applicable export control laws and regulations, including the U.S. Export Administration Regulations (EAR) and the International Traffic in Arms Regulations (ITAR)."
        assert check_export_compliance(text) is False

    def test_check_anti_corruption_violation(self):
        text = "No anti-corruption or anti-bribery representations are made by either party in this Agreement."
        assert check_anti_corruption(text) is True

    def test_check_anti_corruption_compliant(self):
        text = "Each party represents and warrants that it has not and will not offer, pay, or promise to pay anything of value to any government official in violation of the U.S. Foreign Corrupt Practices Act (FCPA) or the UK Bribery Act."
        assert check_anti_corruption(text) is False


class TestHelperFunctions:
    def test_run_policy_check_all_rules(self, sample_contract_text):
        results = run_policy_check(sample_contract_text)
        assert len(results) == 30
        assert all(isinstance(v, bool) for v in results.values())

    def test_run_policy_check_specific_rules(self, sample_contract_text):
        results = run_policy_check(sample_contract_text, rule_ids=["RULE_02", "RULE_03"])
        assert len(results) == 2
        assert "RULE_02" in results
        assert "RULE_03" in results

    def test_get_rule_returns_correct_rule(self):
        rule = get_rule("RULE_01")
        assert rule is not None
        assert rule.rule_id == "RULE_01"
        assert rule.severity == "critical"

    def test_get_rule_returns_none_for_invalid(self):
        assert get_rule("RULE_99") is None

    def test_get_rules_by_category(self):
        liability_rules = get_rules_by_category("LIABILITY")
        assert len(liability_rules) > 0
        assert all(r.category == "LIABILITY" for r in liability_rules)

    def test_get_rules_by_category_empty(self):
        assert get_rules_by_category("NONEXISTENT") == []
