import {
  LabelSection,
  OpenFDALabelEvidence,
  OpenFDALabelRecord,
} from "@/lib/types";

export type DisplayLabelSection = LabelSection & {
  displaySourceKey?: string;
  isSelectedNodeEvidence: boolean;
  isInteractionTargeted: boolean;
  isContextTargeted: boolean;
};

export type DisplaySourceRecord = {
  key: string;
  record: OpenFDALabelRecord;
  sourceNumber: number;
  isSelectedNodeMatch: boolean;
  isSelectedNodeOnly: boolean;
  isInteractionTargeted: boolean;
  isContextTargeted: boolean;
};

export type DisplayEvidenceModel = {
  records: DisplaySourceRecord[];
  sections: Record<string, DisplayLabelSection[]>;
  sourceByKey: Map<string, DisplaySourceRecord>;
  selectedNodeSourceKeys: Set<string>;
  selectedNodeOnlyCount: number;
  selectedNodeMatchCount: number;
};

export type EvidenceCoverageTarget = {
  rxcui: string;
};

export type GroupedLabelSection = {
  key: string;
  sourceKey?: string;
  source?: DisplaySourceRecord;
  text: string;
  chunkCount: number;
  isSelectedNodeEvidence: boolean;
  isInteractionTargeted: boolean;
  isContextTargeted: boolean;
};

export function hasInteractionTargetedTag(
  item: { provenance_tags?: string[] | null }
) {
  return Boolean(
    item.provenance_tags?.includes("interaction_targeted_lookup")
  );
}

export function hasContextTargetedTag(
  item: { provenance_tags?: string[] | null }
) {
  return Boolean(item.provenance_tags?.includes("context_targeted_lookup"));
}

export function sectionTagSources(
  sections: Record<string, LabelSection[]> | undefined,
  hasTag: (item: { provenance_tags?: string[] | null }) => boolean
) {
  const sourceIds = new Set<string>();
  for (const entries of Object.values(sections ?? {})) {
    for (const entry of entries) {
      if (entry.source_id && hasTag(entry)) {
        sourceIds.add(entry.source_id);
      }
    }
  }
  return sourceIds;
}

export function sortEvidenceSources(records: DisplaySourceRecord[]) {
  return [...records].sort((left, right) => {
    if (left.isSelectedNodeOnly !== right.isSelectedNodeOnly) {
      return left.isSelectedNodeOnly ? -1 : 1;
    }
    return left.sourceNumber - right.sourceNumber;
  });
}

export function recordKey(
  record: OpenFDALabelRecord,
  index: number,
  prefix: "baseline" | "selected"
) {
  return [
    prefix,
    record.source_id,
    record.id,
    record.set_id,
    record.spl_ids[0],
    record.spl_set_ids[0],
    index,
  ]
    .filter(Boolean)
    .join(":");
}

export function hasSharedValue(left: string[], right: string[]) {
  if (left.length === 0 || right.length === 0) {
    return false;
  }
  const rightValues = new Set(right);
  return left.some((value) => rightValues.has(value));
}

export function recordsMatch(
  baseline: OpenFDALabelRecord,
  selected: OpenFDALabelRecord
) {
  if (baseline.source_id && baseline.source_id === selected.source_id) {
    return true;
  }
  if (baseline.id && baseline.id === selected.id) {
    return true;
  }
  if (baseline.set_id && baseline.set_id === selected.set_id) {
    return true;
  }
  if (hasSharedValue(baseline.spl_ids, selected.spl_ids)) {
    return true;
  }
  return hasSharedValue(baseline.spl_set_ids, selected.spl_set_ids);
}

export function buildDisplayEvidenceModel(
  baselineEvidence: OpenFDALabelEvidence | null,
  selectedEvidence: OpenFDALabelEvidence | null
): DisplayEvidenceModel {
  const baselineRecords = baselineEvidence?.label_records ?? [];
  const selectedRecords = selectedEvidence?.label_records ?? [];
  const baselineInteractionSourceIds = sectionTagSources(
    baselineEvidence?.sections,
    hasInteractionTargetedTag
  );
  const baselineContextSourceIds = sectionTagSources(
    baselineEvidence?.sections,
    hasContextTargetedTag
  );
  const selectedInteractionSourceIds = sectionTagSources(
    selectedEvidence?.sections,
    hasInteractionTargetedTag
  );
  const selectedContextSourceIds = sectionTagSources(
    selectedEvidence?.sections,
    hasContextTargetedTag
  );
  const baselineItems = baselineRecords.map((record, index) => ({
    key: recordKey(record, index, "baseline"),
    record,
    sourceNumber: index + 1,
    isSelectedNodeMatch: false,
    isSelectedNodeOnly: false,
    isInteractionTargeted:
      hasInteractionTargetedTag(record) ||
      Boolean(record.source_id && baselineInteractionSourceIds.has(record.source_id)),
    isContextTargeted:
      hasContextTargetedTag(record) ||
      Boolean(record.source_id && baselineContextSourceIds.has(record.source_id)),
  }));
  const baselineSectionKeyBySourceId = new Map<string, string>();
  for (const item of baselineItems) {
    if (item.record.source_id) {
      baselineSectionKeyBySourceId.set(item.record.source_id, item.key);
    }
  }

  const matchedBaselineKeys = new Set<string>();
  const selectedOnlyItems: DisplaySourceRecord[] = [];
  const selectedSectionKeyBySourceId = new Map<string, string>();

  selectedRecords.forEach((selectedRecord, selectedIndex) => {
    const match = baselineItems.find((item) =>
      recordsMatch(item.record, selectedRecord)
    );
    if (match) {
      matchedBaselineKeys.add(match.key);
      if (selectedRecord.source_id) {
        selectedSectionKeyBySourceId.set(selectedRecord.source_id, match.key);
      }
      return;
    }

    const selectedOnlyItem: DisplaySourceRecord = {
      key: recordKey(selectedRecord, selectedIndex, "selected"),
      record: selectedRecord,
      sourceNumber: 0,
      isSelectedNodeMatch: false,
      isSelectedNodeOnly: true,
      isInteractionTargeted:
        hasInteractionTargetedTag(selectedRecord) ||
        Boolean(
          selectedRecord.source_id &&
            selectedInteractionSourceIds.has(selectedRecord.source_id)
        ),
      isContextTargeted:
        hasContextTargetedTag(selectedRecord) ||
        Boolean(
          selectedRecord.source_id &&
            selectedContextSourceIds.has(selectedRecord.source_id)
        ),
    };
    selectedOnlyItems.push(selectedOnlyItem);
    if (selectedRecord.source_id) {
      selectedSectionKeyBySourceId.set(selectedRecord.source_id, selectedOnlyItem.key);
    }
  });

  const records = sortEvidenceSources([
    ...selectedOnlyItems,
    ...baselineItems.map((item) => ({
      ...item,
      isSelectedNodeMatch: matchedBaselineKeys.has(item.key),
    })),
  ]).map((item, index) => ({
    ...item,
    sourceNumber: index + 1,
  }));

  const selectedNodeSourceKeys = new Set<string>([
    ...matchedBaselineKeys,
    ...selectedOnlyItems.map((item) => item.key),
  ]);
  const sections: Record<string, DisplayLabelSection[]> = {};

  for (const [section, entries] of Object.entries(
    baselineEvidence?.sections ?? {}
  )) {
    sections[section] = entries.map((entry) => ({
      ...entry,
      displaySourceKey: entry.source_id
        ? baselineSectionKeyBySourceId.get(entry.source_id)
        : undefined,
      isSelectedNodeEvidence: false,
      isInteractionTargeted: hasInteractionTargetedTag(entry),
      isContextTargeted: hasContextTargetedTag(entry),
    }));
  }

  for (const [section, entries] of Object.entries(
    selectedEvidence?.sections ?? {}
  )) {
    const selectedOnlyEntries = entries
      .map((entry) => ({
        ...entry,
        displaySourceKey: entry.source_id
          ? selectedSectionKeyBySourceId.get(entry.source_id)
          : undefined,
        isSelectedNodeEvidence: true,
        isInteractionTargeted: hasInteractionTargetedTag(entry),
        isContextTargeted: hasContextTargetedTag(entry),
      }))
      .filter(
        (entry) =>
          entry.displaySourceKey &&
          selectedOnlyItems.some((item) => item.key === entry.displaySourceKey)
      );

    if (selectedOnlyEntries.length > 0) {
      sections[section] = [...selectedOnlyEntries, ...(sections[section] ?? [])];
    }
  }

  return {
    records,
    sections,
    sourceByKey: new Map(records.map((item) => [item.key, item])),
    selectedNodeSourceKeys,
    selectedNodeOnlyCount: selectedOnlyItems.length,
    selectedNodeMatchCount: matchedBaselineKeys.size,
  };
}

export function groupLabelSectionsBySource(
  section: string | null,
  entries: DisplayLabelSection[],
  displayEvidence: DisplayEvidenceModel
) {
  const groups = new Map<string, GroupedLabelSection>();

  entries.forEach((entry, index) => {
    const sourceKey =
      entry.displaySourceKey ?? `${entry.source_id ?? "unknown"}-${index}`;
    const groupKey = `${section ?? "section"}-${sourceKey}`;
    const existing = groups.get(groupKey);

    if (existing) {
      existing.text = `${existing.text}\n\n${entry.text}`;
      existing.chunkCount += 1;
      existing.isSelectedNodeEvidence =
        existing.isSelectedNodeEvidence || entry.isSelectedNodeEvidence;
      existing.isInteractionTargeted =
        existing.isInteractionTargeted || entry.isInteractionTargeted;
      existing.isContextTargeted =
        existing.isContextTargeted || entry.isContextTargeted;
      return;
    }

    groups.set(groupKey, {
      key: groupKey,
      sourceKey: entry.displaySourceKey,
      source: entry.displaySourceKey
        ? displayEvidence.sourceByKey.get(entry.displaySourceKey)
        : undefined,
      text: entry.text,
      chunkCount: 1,
      isSelectedNodeEvidence: entry.isSelectedNodeEvidence,
      isInteractionTargeted: entry.isInteractionTargeted,
      isContextTargeted: entry.isContextTargeted,
    });
  });

  return Array.from(groups.values()).sort((left, right) => {
    const leftSourceNumber = left.source?.sourceNumber ?? Number.MAX_SAFE_INTEGER;
    const rightSourceNumber = right.source?.sourceNumber ?? Number.MAX_SAFE_INTEGER;
    if (leftSourceNumber !== rightSourceNumber) {
      return leftSourceNumber - rightSourceNumber;
    }
    return left.key.localeCompare(right.key);
  });
}
