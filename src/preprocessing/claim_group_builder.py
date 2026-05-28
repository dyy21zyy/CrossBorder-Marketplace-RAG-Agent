"""Build claim-level groups by attaching dependent claims to independent claims."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

DEPENDENCY_RE = re.compile(r"claims?\s+(\d+)(?:\s*[-to]+\s*(\d+))?", re.IGNORECASE)


@dataclass
class ClaimGroup:
    patent_id: str
    independent_claim_number: str
    dependent_claim_numbers: list[str]
    claim_group_text: str
    claim_count: int
    source: str
    context_path: str


class ClaimGroupBuilder:
    source_name = "Patent Claims Research Dataset"

    @staticmethod
    def _is_truthy(value: Any) -> bool:
        return str(value).strip().lower() in {"1", "true", "y", "yes", "t"}

    @staticmethod
    def _parse_dep_numbers(dependencies: str, claim_text: str) -> list[str]:
        text = f"{dependencies} {claim_text}".strip()
        refs: set[str] = set()
        for m in DEPENDENCY_RE.finditer(text):
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else start
            if end < start:
                start, end = end, start
            for i in range(start, end + 1):
                refs.add(str(i))
        return sorted(refs, key=lambda x: int(x))

    def build(self, claims: list[dict[str, Any]], context_path: str = "") -> list[ClaimGroup]:
        by_patent: dict[str, list[dict[str, Any]]] = {}
        for row in claims:
            by_patent.setdefault(str(row.get("patent_id", "")).strip(), []).append(row)

        all_groups: list[ClaimGroup] = []
        for patent_id, patent_claims in by_patent.items():
            patent_claims = sorted(patent_claims, key=lambda r: int(str(r.get("claim_number", "0") or "0")))
            groups: dict[str, dict[str, Any]] = {}
            last_ind: str | None = None

            for row in patent_claims:
                cno = str(row.get("claim_number", "")).strip()
                ctext = str(row.get("claim_text", "")).strip()
                deps = str(row.get("dependencies", "")).strip()
                is_ind = self._is_truthy(row.get("independent_flag")) or deps == ""

                if is_ind:
                    groups.setdefault(cno, {"ind": row, "deps": []})
                    last_ind = cno
                    continue

                refs = self._parse_dep_numbers(deps, ctext)
                anchor = next((r for r in refs if r in groups), None)
                if not anchor:
                    anchor = last_ind
                if not anchor:
                    groups[cno] = {"ind": row, "deps": []}
                    last_ind = cno
                else:
                    groups.setdefault(anchor, {"ind": {"claim_number": anchor, "claim_text": ""}, "deps": []})
                    groups[anchor]["deps"].append(row)

            for ind_no, payload in groups.items():
                ind = payload["ind"]
                dep_rows = payload["deps"]
                dep_numbers = [str(d.get("claim_number", "")).strip() for d in dep_rows if str(d.get("claim_number", "")).strip()]
                lines = [
                    "[Patent Claim Group]",
                    f"Patent: {patent_id}",
                    f"Independent Claim: {ind_no}",
                    f"Dependent Claims: {', '.join(dep_numbers) if dep_numbers else 'None'}",
                    "Source: USPTO Patent Claims Research Dataset",
                    "",
                    f"Claim {ind_no}: {str(ind.get('claim_text', '')).strip()}",
                ]
                for dep in dep_rows:
                    dno = str(dep.get("claim_number", "")).strip()
                    lines.append(f"Claim {dno}: {str(dep.get('claim_text', '')).strip()}")

                all_groups.append(
                    ClaimGroup(
                        patent_id=patent_id,
                        independent_claim_number=ind_no,
                        dependent_claim_numbers=dep_numbers,
                        claim_group_text="\n".join(lines).strip(),
                        claim_count=1 + len(dep_rows),
                        source=self.source_name,
                        context_path=context_path,
                    )
                )
        return all_groups
