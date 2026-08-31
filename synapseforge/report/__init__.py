"""
Report Specification and Publication Engine Module for SynapseForge.
Implements the highest standard of publication-grade writing: zero AI flavor,
continuous narrative analytical prose, academic booktabs, scientific plotting,
and publication PDF typography.
"""

from synapseforge.report.spec import ReportSpecification, ReportStandard
from synapseforge.report.generator import ReportGenerator
from synapseforge.report.prompts import REPORT_SPEC_PROMPTS

__all__ = [
    "ReportSpecification",
    "ReportStandard",
    "ReportGenerator",
    "REPORT_SPEC_PROMPTS",
]
