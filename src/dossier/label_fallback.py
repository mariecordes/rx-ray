from __future__ import annotations

from src.dossier.models import (
    LabelSection,
    OpenFDALabelEvidence,
    OpenFDALabelRecord,
)


def tag_label_evidence(
    evidence: OpenFDALabelEvidence,
    tag: str,
) -> OpenFDALabelEvidence:
    """Stamp a provenance tag onto every record and section of an evidence bundle."""

    if not evidence.labels_found:
        return evidence
    return evidence.model_copy(
        update={
            "label_records": [
                record.model_copy(
                    update={
                        "provenance_tags": _merge_tags(record.provenance_tags, [tag])
                    }
                )
                for record in evidence.label_records
            ],
            "sections": {
                name: [
                    entry.model_copy(
                        update={
                            "provenance_tags": _merge_tags(
                                entry.provenance_tags, [tag]
                            )
                        }
                    )
                    for entry in entries
                ]
                for name, entries in evidence.sections.items()
            },
        }
    )


def merge_ingredient_label_evidence(
    rxcui: str,
    evidences: list[OpenFDALabelEvidence],
    *,
    label_limit: int,
) -> OpenFDALabelEvidence:
    """Combine the per-ingredient label bundles into one evidence view.

    Records keep their per-ingredient provenance tags, so the merge is labelled,
    not silent. ``rxcui`` is the broadened (specific) concept, while each record
    carries its own ingredient RXCUIs.
    """

    records: list[OpenFDALabelRecord] = []
    sections: dict[str, list[LabelSection]] = {}
    errors: list[str] = []
    seen_records: set[str] = set()
    seen_sections: set[tuple[str, str | None, str]] = set()

    for evidence in evidences:
        errors.extend(evidence.errors)
        for record in evidence.label_records:
            key = _stable_record_key(record)
            if key in seen_records:
                continue
            seen_records.add(key)
            records.append(record)
        for name, entries in evidence.sections.items():
            for entry in entries:
                section_key = (name, entry.source_id, entry.text)
                if section_key in seen_sections:
                    continue
                seen_sections.add(section_key)
                sections.setdefault(name, []).append(entry)

    return OpenFDALabelEvidence(
        rxcui=str(rxcui),
        labels_found=len(records),
        label_limit=label_limit,
        retrieval_mode="ingredient_fallback" if records else "none",
        label_records=records,
        summary_metadata=_build_summary_metadata(records),
        sections=sections,
        section_flags={
            f"has_{name}": bool(values) for name, values in sections.items()
        },
        errors=errors,
    )


def _merge_tags(existing: list[str], new: list[str]) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    for tag in [*existing, *new]:
        if not tag or tag in seen:
            continue
        seen.add(tag)
        tags.append(tag)
    return tags


def _stable_record_key(record: OpenFDALabelRecord) -> str:
    for value in [record.source_id, record.id, record.set_id]:
        if value:
            return value
    for values in [record.spl_ids, record.spl_set_ids]:
        if values:
            return "|".join(sorted(values))
    return "|".join(
        [
            ",".join(record.brand_names),
            ",".join(record.generic_names),
            ",".join(record.manufacturer_names),
        ]
    )


def _build_summary_metadata(
    records: list[OpenFDALabelRecord],
) -> dict[str, list[str]]:
    return {
        "manufacturers": sorted(
            {value for record in records for value in record.manufacturer_names}
        ),
        "brand_names": sorted(
            {value for record in records for value in record.brand_names}
        ),
        "generic_names": sorted(
            {value for record in records for value in record.generic_names}
        ),
        "label_ids": sorted({record.id for record in records if record.id}),
        "label_set_ids": sorted(
            {record.set_id for record in records if record.set_id}
        ),
        "spl_ids": sorted({value for record in records for value in record.spl_ids}),
        "spl_set_ids": sorted(
            {value for record in records for value in record.spl_set_ids}
        ),
    }
