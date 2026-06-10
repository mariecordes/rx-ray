from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests

from src.dossier.models import (
    LabelSection,
    OpenFDALabelEvidence,
    OpenFDALabelRecord,
)


DEFAULT_BASE_URL = "https://api.fda.gov/drug/label.json"

SECTION_ALIASES = {
    "boxed_warning": ("boxed_warning",),
    "contraindications": ("contraindications",),
    "warnings": ("warnings", "warnings_and_precautions", "warnings_and_cautions"),
    "drug_interactions": ("drug_interactions",),
    "pregnancy": ("pregnancy", "pregnancy_or_breast_feeding"),
    "lactation": ("lactation", "nursing_mothers"),
    "adverse_reactions": ("adverse_reactions",),
    "indications_and_usage": ("indications_and_usage",),
    "use_in_specific_populations": ("use_in_specific_populations",),
}


class OpenFDALabelStore:
    """Retrieve and normalize OpenFDA drug-label evidence."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        cache_dir: str | Path = "data/cache/openfda_labels",
        timeout: int = 12,
        use_cache: bool = True,
        allow_live: bool = True,
    ) -> None:
        self.base_url = base_url
        self.cache_dir = Path(cache_dir)
        self.timeout = timeout
        self.use_cache = use_cache
        self.allow_live = allow_live
        self.session = requests.Session()

    def get_label_evidence(
        self,
        rxcui: str,
        fallback_name: str | None = None,
        limit: int = 5,
    ) -> OpenFDALabelEvidence:
        """Fetch OpenFDA labels by RXCUI, falling back to generic name when needed."""

        errors: list[str] = []
        labels: list[dict[str, Any]] = []
        cached_labels: list[dict[str, Any]] | None = None
        retrieval_mode = "none"

        if self.use_cache:
            cached_labels = self._read_cache(rxcui)
            if cached_labels is not None and (
                len(cached_labels) >= limit or not self.allow_live
            ):
                labels = cached_labels[:limit]
                retrieval_mode = "cache"

        if not labels and self.allow_live:
            try:
                labels = self._query(f"openfda.rxcui:{rxcui}", limit=limit)
                retrieval_mode = "live_rxcui" if labels else "none"
                if not labels and fallback_name:
                    labels = self._query(
                        f'openfda.generic_name:"{fallback_name}"',
                        limit=limit,
                    )
                    retrieval_mode = "live_generic_name" if labels else "none"
                if labels and self.use_cache:
                    self._write_cache(rxcui, labels)
            except requests.RequestException as exc:
                errors.append(f"OpenFDA request failed: {exc}")
            except ValueError as exc:
                errors.append(f"OpenFDA response could not be parsed: {exc}")
            if not labels and cached_labels is not None:
                labels = cached_labels[:limit]
                retrieval_mode = "cache"

        evidence = self._normalize_labels(
            rxcui,
            labels,
            retrieval_mode,
            label_limit=limit,
        )
        evidence.errors.extend(errors)
        if not labels and not errors and not self.allow_live:
            evidence.errors.append(
                "Live OpenFDA lookup disabled and no cache was found."
            )
        return evidence

    def get_interaction_label_evidence(
        self,
        rxcui: str,
        interaction_name: str,
        fallback_name: str | None = None,
        limit: int = 3,
    ) -> OpenFDALabelEvidence:
        """Fetch labels whose drug-interactions section mentions another drug."""

        errors: list[str] = []
        labels: list[dict[str, Any]] = []
        retrieval_mode = "none"
        interaction_query = self._quote_query_value(interaction_name)

        if self.allow_live and limit > 0 and interaction_query:
            try:
                labels = self._query(
                    f"openfda.rxcui:{rxcui}+AND+drug_interactions:{interaction_query}",
                    limit=limit,
                )
                retrieval_mode = "interaction_targeted_lookup" if labels else "none"
                if not labels and fallback_name:
                    labels = self._query(
                        "openfda.generic_name:"
                        f"{self._quote_query_value(fallback_name)}"
                        f"+AND+drug_interactions:{interaction_query}",
                        limit=limit,
                    )
                    retrieval_mode = (
                        "interaction_targeted_lookup" if labels else "none"
                    )
            except requests.RequestException as exc:
                errors.append(f"OpenFDA interaction request failed: {exc}")
            except ValueError as exc:
                errors.append(
                    f"OpenFDA interaction response could not be parsed: {exc}"
                )

        evidence = self._normalize_labels(
            rxcui,
            labels,
            retrieval_mode,
            label_limit=limit,
        )
        evidence.errors.extend(errors)
        if not labels and not errors and not self.allow_live:
            evidence.errors.append(
                "Live OpenFDA interaction lookup disabled."
            )
        return evidence

    def _query(self, search: str, limit: int) -> list[dict[str, Any]]:
        response = self.session.get(
            self.base_url,
            params={"search": search, "limit": limit},
            timeout=self.timeout,
        )
        if response.status_code == 404:
            return []
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])

    def _read_cache(self, rxcui: str) -> list[dict[str, Any]] | None:
        path = self.cache_dir / f"{rxcui}.json"
        if not path.exists():
            return None
        with path.open() as f:
            return json.load(f)

    def _write_cache(self, rxcui: str, labels: list[dict[str, Any]]) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.cache_dir / f"{rxcui}.json"
        with path.open("w") as f:
            json.dump(labels, f, indent=2)

    def _normalize_labels(
        self,
        rxcui: str,
        labels: list[dict[str, Any]],
        retrieval_mode: str,
        label_limit: int | None = None,
    ) -> OpenFDALabelEvidence:
        sections: dict[str, list[LabelSection]] = {
            section: [] for section in SECTION_ALIASES
        }
        label_records: list[OpenFDALabelRecord] = []
        manufacturers: set[str] = set()
        brand_names: set[str] = set()
        generic_names: set[str] = set()
        label_ids: set[str] = set()
        label_set_ids: set[str] = set()
        spl_ids: set[str] = set()
        spl_set_ids: set[str] = set()

        for label in labels:
            source_id = label.get("id") or label.get("set_id")
            effective_time = label.get("effective_time")
            openfda = label.get("openfda", {})
            manufacturer_names = self._as_text_list(
                openfda.get("manufacturer_name", [])
            )
            label_brand_names = self._as_text_list(openfda.get("brand_name", []))
            label_generic_names = self._as_text_list(openfda.get("generic_name", []))
            label_spl_ids = self._as_text_list(openfda.get("spl_id", []))
            label_spl_set_ids = self._as_text_list(openfda.get("spl_set_id", []))
            manufacturers.update(manufacturer_names)
            brand_names.update(label_brand_names)
            generic_names.update(label_generic_names)
            if label.get("id"):
                label_ids.add(label["id"])
            if label.get("set_id"):
                label_set_ids.add(label["set_id"])
            spl_ids.update(label_spl_ids)
            spl_set_ids.update(label_spl_set_ids)

            label_records.append(
                OpenFDALabelRecord(
                    source_id=source_id,
                    id=label.get("id"),
                    set_id=label.get("set_id"),
                    spl_ids=label_spl_ids,
                    spl_set_ids=label_spl_set_ids,
                    effective_time=effective_time,
                    version=label.get("version"),
                    brand_names=label_brand_names,
                    generic_names=label_generic_names,
                    manufacturer_names=manufacturer_names,
                    product_ndcs=self._as_text_list(openfda.get("product_ndc", [])),
                    product_types=self._as_text_list(openfda.get("product_type", [])),
                    routes=self._as_text_list(openfda.get("route", [])),
                    substance_names=self._as_text_list(
                        openfda.get("substance_name", [])
                    ),
                    rxcuis=self._as_text_list(openfda.get("rxcui", [])),
                )
            )

            for normalized_name, raw_names in SECTION_ALIASES.items():
                for raw_name in raw_names:
                    for text in self._as_text_list(label.get(raw_name, [])):
                        sections[normalized_name].append(
                            LabelSection(
                                section=normalized_name,
                                text=text,
                                source_id=source_id,
                                effective_time=effective_time,
                            )
                        )

        sections = {name: values for name, values in sections.items() if values}
        flags = {f"has_{name}": bool(values) for name, values in sections.items()}

        return OpenFDALabelEvidence(
            rxcui=str(rxcui),
            labels_found=len(labels),
            label_limit=label_limit,
            retrieval_mode=retrieval_mode,
            label_records=label_records,
            summary_metadata={
                "manufacturers": sorted(manufacturers),
                "brand_names": sorted(brand_names),
                "generic_names": sorted(generic_names),
                "label_ids": sorted(label_ids),
                "label_set_ids": sorted(label_set_ids),
                "spl_ids": sorted(spl_ids),
                "spl_set_ids": sorted(spl_set_ids),
            },
            sections=sections,
            section_flags=flags,
        )

    @staticmethod
    def _as_text_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()] if str(value).strip() else []

    @staticmethod
    def _quote_query_value(value: str) -> str:
        escaped = value.strip().replace('"', '\\"')
        return f'"{escaped}"' if escaped else ""
