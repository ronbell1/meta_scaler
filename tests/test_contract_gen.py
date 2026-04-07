"""Unit tests for the synthetic contract generator."""

import pytest

from server.contract_gen import (
    ContractGenerator,
    ContractPackage,
    COMPLIANT_CLAUSE_TEMPLATES,
    VIOLATION_CLAUSE_TEMPLATES,
    CONTRACT_STRUCTURES,
)


class TestContractGenerator:
    def test_generator_initialization(self):
        gen = ContractGenerator(seed=42)
        assert gen.seed == 42

    def test_generator_deterministic(self):
        gen1 = ContractGenerator(seed=42)
        gen2 = ContractGenerator(seed=42)
        contract1 = gen1.generate(contract_type="MSA")
        contract2 = gen2.generate(contract_type="MSA")
        assert contract1 == contract2

    def test_generate_msa_contract(self):
        gen = ContractGenerator(seed=42)
        contract = gen.generate(contract_type="MSA")
        assert isinstance(contract, str)
        assert len(contract) > 100
        assert "PREAMBLE" in contract

    def test_generate_nda_contract(self):
        gen = ContractGenerator(seed=42)
        contract = gen.generate(contract_type="NDA")
        assert isinstance(contract, str)
        assert "CONFIDENTIAL INFORMATION" in contract

    def test_generate_sla_contract(self):
        gen = ContractGenerator(seed=42)
        contract = gen.generate(contract_type="SLA")
        assert isinstance(contract, str)
        assert "SERVICE AVAILABILITY" in contract

    def test_generate_sow_contract(self):
        gen = ContractGenerator(seed=42)
        contract = gen.generate(contract_type="SOW")
        assert isinstance(contract, str)
        assert "SCOPE OF WORK" in contract

    def test_generate_dpa_contract(self):
        gen = ContractGenerator(seed=42)
        contract = gen.generate(contract_type="DPA")
        assert isinstance(contract, str)
        assert "DEFINITIONS" in contract

    def test_generate_vendor_po_contract(self):
        gen = ContractGenerator(seed=42)
        contract = gen.generate(contract_type="VENDOR_PO")
        assert isinstance(contract, str)
        assert "PURCHASE ORDER" in contract or "PO" in contract

    def test_generate_with_violations(self):
        gen = ContractGenerator(seed=42)
        violations = ["RULE_02", "RULE_03"]
        contract = gen.generate(contract_type="MSA", violations=violations)
        assert isinstance(contract, str)
        assert "thirty (30) days" in contract or "30 days" in contract

    def test_generate_with_red_herrings(self):
        gen = ContractGenerator(seed=42)
        contract = gen.generate(contract_type="MSA", red_herrings=1)
        assert "RED HERRING CLAUSE" in contract

    def test_generate_default_contract_type(self):
        gen = ContractGenerator(seed=42)
        contract = gen.generate()
        assert isinstance(contract, str)

    def test_generate_unknown_contract_type_uses_msa(self):
        gen = ContractGenerator(seed=42)
        contract = gen.generate(contract_type="UNKNOWN_TYPE")
        assert isinstance(contract, str)
        assert "PREAMBLE" in contract


class TestContractPackage:
    def test_generate_package_single_document(self):
        gen = ContractGenerator(seed=42)
        package = gen.generate_package(documents=["MSA"])
        assert isinstance(package, ContractPackage)
        assert "MSA" in package.documents
        assert len(package.documents) == 1

    def test_generate_package_multiple_documents(self):
        gen = ContractGenerator(seed=42)
        package = gen.generate_package(documents=["MSA", "SOW", "DPA"])
        assert len(package.documents) == 3
        assert "MSA" in package.documents
        assert "SOW" in package.documents
        assert "DPA" in package.documents

    def test_generate_package_with_violations(self):
        gen = ContractGenerator(seed=42)
        violations = {"MSA": ["RULE_02", "RULE_03"]}
        package = gen.generate_package(
            documents=["MSA"],
            violations=violations,
        )
        assert package.injected_violations == violations

    def test_generate_package_with_cross_doc_violations(self):
        gen = ContractGenerator(seed=42)
        cross_violations = [("MSA", "DPA", "RULE_18")]
        package = gen.generate_package(
            documents=["MSA", "DPA"],
            cross_doc_violations=cross_violations,
        )
        assert package.cross_doc_violations == cross_violations

    def test_generate_package_with_red_herrings(self):
        gen = ContractGenerator(seed=42)
        package = gen.generate_package(
            documents=["MSA"],
            red_herrings=1,
        )
        assert package.red_herrings == 1
        assert "EXHIBIT A" in package.documents["MSA"]

    def test_generate_package_preserves_seed(self):
        gen = ContractGenerator(seed=42)
        package = gen.generate_package(documents=["MSA"])
        assert package.seed == 42


class TestClauseTemplates:
    def test_compliant_templates_exist_for_all_keys(self):
        expected_keys = {
            "payment_terms",
            "liability_cap",
            "confidentiality",
            "governing_law",
            "ip_ownership",
            "indemnification",
            "termination",
            "sla_uptime",
            "data_privacy",
            "force_majeure",
            "dispute_resolution",
            "auto_renewal",
            "warranty",
            "consequential_damages",
            "assignment",
            "audit_rights",
            "insurance",
            "survival",
            "subcontracting",
            "export_compliance",
            "anti_corruption",
            "suspension",
            "background_ip",
            "currency",
        }
        assert set(COMPLIANT_CLAUSE_TEMPLATES.keys()) == expected_keys

    def test_each_compliant_template_has_multiple_variants(self):
        for key, templates in COMPLIANT_CLAUSE_TEMPLATES.items():
            assert len(templates) >= 1, f"{key} has no templates"

    def test_violation_templates_exist_for_all_rules(self):
        for i in range(1, 31):
            rule_id = f"RULE_{i:02d}"
            assert rule_id in VIOLATION_CLAUSE_TEMPLATES, f"Missing violation template for {rule_id}"


class TestContractStructures:
    def test_all_contract_types_defined(self):
        expected = {"MSA", "NDA", "SLA", "SOW", "DPA", "VENDOR_PO"}
        assert set(CONTRACT_STRUCTURES.keys()) == expected

    def test_each_structure_has_sections(self):
        for contract_type, structure in CONTRACT_STRUCTURES.items():
            assert "sections" in structure
            assert len(structure["sections"]) > 0

    def test_msa_has_most_sections(self):
        msa_sections = CONTRACT_STRUCTURES["MSA"]["sections"]
        assert len(msa_sections) > 15
