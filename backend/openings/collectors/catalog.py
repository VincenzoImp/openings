"""Company adapter capabilities shared by validation, discovery and the dashboard."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class CompanyAdapter:
    description_mode: Literal["inline", "separate", "metadata"]
    candidates: bool = True
    region: bool = False

    @property
    def fields(self):
        fields = ["board", "max_results"]
        if self.candidates:
            fields.append("max_candidates")
        if self.region:
            fields.append("region")
        return fields


COMPANY_ADAPTERS = {
    "greenhouse": CompanyAdapter("separate"),
    "lever": CompanyAdapter("inline", candidates=False, region=True),
    "ashby": CompanyAdapter("inline", candidates=False),
    "recruitee": CompanyAdapter("inline"),
    "personio": CompanyAdapter("inline"),
    "workable": CompanyAdapter("inline"),
    "breezy": CompanyAdapter("metadata"),
    "smartrecruiters": CompanyAdapter("separate"),
    "bamboohr": CompanyAdapter("separate"),
    "rippling": CompanyAdapter("separate"),
    "workday": CompanyAdapter("separate"),
    "oracle": CompanyAdapter("separate"),
    "joincom": CompanyAdapter("separate"),
}
COMPANY_KINDS = tuple(COMPANY_ADAPTERS)
