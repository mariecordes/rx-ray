"use client";

import { FormEvent, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  Database,
  FileText,
  FlaskConical,
  Loader2,
  Search,
} from "lucide-react";

import { RxNormKnowledgeGraph } from "@/components/rxnorm-knowledge-graph";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  DrugDossier,
  LabelSection,
  OpenFDALabelEvidence,
  OpenFDALabelRecord,
  RxNormConcept,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const sectionLabels: Record<string, string> = {
  boxed_warning: "Boxed warning",
  contraindications: "Contraindications",
  warnings: "Warnings",
  drug_interactions: "Drug interactions",
  pregnancy: "Pregnancy",
  lactation: "Lactation",
  adverse_reactions: "Adverse reactions",
  indications_and_usage: "Indications",
  use_in_specific_populations: "Specific populations",
};

function displaySectionName(section: string) {
  return sectionLabels[section] ?? section.replaceAll("_", " ");
}

function primaryValue(values?: string[] | null) {
  if (!values || values.length === 0) {
    return null;
  }
  return values[0];
}

const sourceSelectionClasses =
  "border-[#C7B4EF] bg-[#E8DDF9] shadow-sm hover:border-[#C7B4EF]";
const nodeSpecificClasses =
  "border-[#EACB96] bg-[#FAE8CD] hover:border-[#DDBB7E]";
const searchSourceClasses =
  "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50";
const selectedSourceBadgeClasses =
  "border-[#C7B4EF] bg-[#DDCAF7] text-[#4C2C77]";
const nodeSpecificBadgeClasses =
  "border-[#EACB96] bg-[#FAE8CD] text-[#704A12]";
const searchSpecificBadgeClasses =
  "border-slate-200 bg-white text-slate-700";

type DisplayLabelSection = LabelSection & {
  displaySourceKey?: string;
  isSelectedNodeEvidence: boolean;
};

type DisplaySourceRecord = {
  key: string;
  record: OpenFDALabelRecord;
  sourceNumber: number;
  isSelectedNodeMatch: boolean;
  isSelectedNodeOnly: boolean;
};

type DisplayEvidenceModel = {
  records: DisplaySourceRecord[];
  sections: Record<string, DisplayLabelSection[]>;
  sourceByKey: Map<string, DisplaySourceRecord>;
  selectedNodeSourceKeys: Set<string>;
  selectedNodeOnlyCount: number;
  selectedNodeMatchCount: number;
};

function recordKey(
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

function hasSharedValue(left: string[], right: string[]) {
  if (left.length === 0 || right.length === 0) {
    return false;
  }
  const rightValues = new Set(right);
  return left.some((value) => rightValues.has(value));
}

function recordsMatch(
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

function buildDisplayEvidenceModel(
  baselineEvidence: OpenFDALabelEvidence | null,
  selectedEvidence: OpenFDALabelEvidence | null
): DisplayEvidenceModel {
  const baselineRecords = baselineEvidence?.label_records ?? [];
  const selectedRecords = selectedEvidence?.label_records ?? [];
  const baselineItems = baselineRecords.map((record, index) => ({
    key: recordKey(record, index, "baseline"),
    record,
    sourceNumber: index + 1,
    isSelectedNodeMatch: false,
    isSelectedNodeOnly: false,
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
    };
    selectedOnlyItems.push(selectedOnlyItem);
    if (selectedRecord.source_id) {
      selectedSectionKeyBySourceId.set(selectedRecord.source_id, selectedOnlyItem.key);
    }
  });

  const records = [
    ...selectedOnlyItems,
    ...baselineItems.map((item) => ({
      ...item,
      isSelectedNodeMatch: matchedBaselineKeys.has(item.key),
    })),
  ].map((item, index) => ({
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

export function DossierExplorer() {
  const [drug, setDrug] = useState("aspirin");
  const [openfdaLimit, setOpenfdaLimit] = useState(5);
  const [dossier, setDossier] = useState<DrugDossier | null>(null);
  const [selectedSection, setSelectedSection] = useState<string | null>(null);
  const [selectedSourceKey, setSelectedSourceKey] = useState<string | null>(null);
  const [selectedGraphNode, setSelectedGraphNode] =
    useState<RxNormConcept | null>(null);
  const [nodeLabelEvidence, setNodeLabelEvidence] =
    useState<OpenFDALabelEvidence | null>(null);
  const [isNodeEvidenceLoading, setIsNodeEvidenceLoading] = useState(false);
  const [nodeEvidenceError, setNodeEvidenceError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const labelEvidencePanelRef = useRef<HTMLDivElement>(null);
  const nodeEvidenceRequestRef = useRef(0);

  const labelEvidence = dossier?.label_evidence ?? null;
  const displayEvidence = useMemo(
    () => buildDisplayEvidenceModel(labelEvidence, nodeLabelEvidence),
    [labelEvidence, nodeLabelEvidence]
  );
  const sectionEntries = useMemo(() => {
    return Object.entries(displayEvidence.sections);
  }, [displayEvidence]);
  const activeSection =
    selectedSection && displayEvidence.sections[selectedSection]
      ? selectedSection
      : sectionEntries[0]?.[0] ?? null;
  const activeTexts: DisplayLabelSection[] = activeSection
    ? displayEvidence.sections[activeSection] ?? []
    : [];

  function toggleSourceSelection(sourceKey?: string | null) {
    if (!sourceKey) {
      return;
    }
    setSelectedSourceKey((current) =>
      current === sourceKey ? null : sourceKey
    );
  }

  function selectSourceFromStrip(sourceKey?: string | null) {
    if (!sourceKey) {
      return;
    }
    const nextSourceKey = selectedSourceKey === sourceKey ? null : sourceKey;
    setSelectedSourceKey(nextSourceKey);
    if (!nextSourceKey) {
      return;
    }
    const sectionWithSource = sectionEntries.find(([, entries]) =>
      entries.some((entry) => entry.displaySourceKey === sourceKey)
    );
    if (sectionWithSource) {
      setSelectedSection(sectionWithSource[0]);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoading(true);
    setError(null);
    setSelectedGraphNode(null);
    setNodeLabelEvidence(null);
    setNodeEvidenceError(null);
    setIsNodeEvidenceLoading(false);
    nodeEvidenceRequestRef.current += 1;

    try {
      const response = await fetch("/api/dossier", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          drug,
          depth: 2,
          max_edges: 400,
          openfda_limit: openfdaLimit,
          include_openfda: true,
        }),
      });
      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload.detail ?? "Failed to build dossier");
      }

      setDossier(payload);
      const firstSection = Object.keys(payload.label_evidence?.sections ?? {})[0];
      setSelectedSection(firstSection ?? null);
      setSelectedSourceKey(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to build dossier");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSelectedGraphNodeChange(node: RxNormConcept | null) {
    const requestId = nodeEvidenceRequestRef.current + 1;
    nodeEvidenceRequestRef.current = requestId;
    setSelectedGraphNode(node);
    setNodeLabelEvidence(null);
    setNodeEvidenceError(null);
    setSelectedSourceKey(null);

    if (!node) {
      setIsNodeEvidenceLoading(false);
      return;
    }

    setIsNodeEvidenceLoading(true);
    try {
      const response = await fetch("/api/label-evidence", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          rxcui: node.rxcui,
          name: node.name,
          limit: 3,
        }),
      });
      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload.detail ?? "Failed to fetch label evidence");
      }

      if (nodeEvidenceRequestRef.current === requestId) {
        setNodeLabelEvidence(payload);
      }
    } catch (err) {
      if (nodeEvidenceRequestRef.current === requestId) {
        setNodeEvidenceError(
          err instanceof Error
            ? err.message
            : "Failed to fetch selected-node label evidence"
        );
      }
    } finally {
      if (nodeEvidenceRequestRef.current === requestId) {
        setIsNodeEvidenceLoading(false);
      }
    }
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-3 border-b border-slate-200 pb-4 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm font-medium text-cyan-700">
              <FlaskConical className="size-4" />
              rx-ray
            </div>
            <h1 className="mt-1 text-2xl font-semibold text-slate-950">
              Drug Dossier Explorer
            </h1>
          </div>
          <div className="max-w-xl rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            Educational prototype. Summarizes public RxNorm and OpenFDA data;
            not medical advice.
          </div>
        </header>

        <form
          onSubmit={handleSubmit}
          className="grid gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm md:grid-cols-[1fr_140px_auto]"
        >
          <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
            Drug
            <Input
              value={drug}
              onChange={(event) => setDrug(event.target.value)}
              placeholder="aspirin"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
            Label limit
            <Input
              min={1}
              max={25}
              type="number"
              value={openfdaLimit}
              onChange={(event) => setOpenfdaLimit(Number(event.target.value))}
            />
          </label>
          <div className="flex items-end">
            <Button className="w-full" disabled={isLoading || !drug.trim()}>
              {isLoading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Search className="size-4" />
              )}
              Search
            </Button>
          </div>
        </form>

        {error ? (
          <div className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            <AlertTriangle className="size-4" />
            {error}
          </div>
        ) : null}

        {!dossier ? (
          <EmptyState />
        ) : (
          <div className="flex flex-col gap-5">
            <Overview dossier={dossier} />
            <RxNormKnowledgeGraph
              key={dossier.resolved_drug?.rxcui ?? dossier.query}
              dossier={dossier}
              onSelectedNodeChange={handleSelectedGraphNodeChange}
            />
            <LabelEvidencePanel
              ref={labelEvidencePanelRef}
              activeSection={activeSection}
              activeTexts={activeTexts}
              displayEvidence={displayEvidence}
              labelEvidence={labelEvidence}
              nodeEvidenceError={nodeEvidenceError}
              nodeLabelEvidence={nodeLabelEvidence}
              isNodeEvidenceLoading={isNodeEvidenceLoading}
              sectionEntries={sectionEntries}
              selectedGraphNode={selectedGraphNode}
              selectedSourceKey={selectedSourceKey}
              onSelectSection={setSelectedSection}
              onSelectSource={toggleSourceSelection}
              onSelectSourceFromStrip={selectSourceFromStrip}
            />
          </div>
        )}
      </div>
    </main>
  );
}

function EmptyState() {
  return (
    <div className="grid min-h-[320px] place-items-center rounded-lg border border-dashed border-slate-300 bg-white">
      <div className="max-w-md px-6 text-center">
        <Database className="mx-auto mb-3 size-8 text-slate-400" />
        <p className="text-sm text-slate-600">No dossier loaded.</p>
      </div>
    </div>
  );
}

function Overview({ dossier }: { dossier: DrugDossier }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Overview</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4 md:grid-cols-[1fr_1.4fr]">
        <div>
          <div className="text-sm text-slate-500">Resolved drug</div>
          {dossier.resolved_drug ? (
            <div className="mt-2 space-y-2">
              <div className="text-xl font-semibold text-slate-950">
                {dossier.resolved_drug.name}
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge>RXCUI {dossier.resolved_drug.rxcui}</Badge>
                <Badge>{dossier.resolved_drug.tty ?? "TTY unknown"}</Badge>
                <Badge>{dossier.resolved_drug.sab ?? "Source unknown"}</Badge>
              </div>
            </div>
          ) : (
            <div className="mt-2 text-sm text-slate-600">No RxNorm match.</div>
          )}
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <Metric
            label="Candidates"
            value={dossier.resolution_candidates.length.toString()}
          />
          <Metric
            label="RxNorm edges"
            value={dossier.rxnorm_neighborhood.edges.length.toString()}
          />
          <Metric
            label="Labels found"
            value={(dossier.label_evidence?.labels_found ?? 0).toString()}
          />
          <Metric
            label="Label limit"
            value={(dossier.label_evidence?.label_limit ?? "—").toString()}
          />
        </div>
        {dossier.notes.length > 0 ? (
          <div className="md:col-span-2">
            <div className="mb-2 text-sm font-medium text-slate-700">Notes</div>
            <div className="flex flex-wrap gap-2">
              {dossier.notes.map((note) => (
                <Badge key={note} className="bg-cyan-50 text-cyan-800">
                  {note}
                </Badge>
              ))}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <div className="text-xs font-medium uppercase text-slate-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-slate-950">{value}</div>
    </div>
  );
}

function LabelEvidencePanel({
  ref,
  activeSection,
  activeTexts,
  displayEvidence,
  labelEvidence,
  nodeEvidenceError,
  nodeLabelEvidence,
  isNodeEvidenceLoading,
  sectionEntries,
  selectedGraphNode,
  selectedSourceKey,
  onSelectSection,
  onSelectSource,
  onSelectSourceFromStrip,
}: {
  ref: React.RefObject<HTMLDivElement | null>;
  activeSection: string | null;
  activeTexts: DisplayLabelSection[];
  displayEvidence: DisplayEvidenceModel;
  labelEvidence: OpenFDALabelEvidence | null;
  nodeEvidenceError: string | null;
  nodeLabelEvidence: OpenFDALabelEvidence | null;
  isNodeEvidenceLoading: boolean;
  sectionEntries: [string, DisplayLabelSection[]][];
  selectedGraphNode: RxNormConcept | null;
  selectedSourceKey: string | null;
  onSelectSection: (section: string) => void;
  onSelectSource: (sourceKey?: string | null) => void;
  onSelectSourceFromStrip: (sourceKey?: string | null) => void;
}) {
  const records = displayEvidence.records;
  const evidenceCardsRef = useRef<HTMLDivElement>(null);

  function handleSourceStripClick(sourceKey: string) {
    onSelectSourceFromStrip(sourceKey);
    window.requestAnimationFrame(() => {
      evidenceCardsRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    });
  }

  return (
    <div ref={ref}>
      <Card>
        <CardHeader className="border-b border-slate-200">
          <div className="flex flex-row items-start justify-between gap-3">
            <div>
              <CardTitle>Label Evidence</CardTitle>
              <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-500">
                OpenFDA drug-label evidence retrieved for the searched drug,
                with graph selections used to highlight or add more specific
                label records.
              </p>
            </div>
            <FileText className="mt-1 size-4 text-slate-400" />
          </div>
        </CardHeader>
        <CardContent className="space-y-5 pt-5">
          <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
            <div className="mb-2 text-xs font-medium uppercase text-slate-500">
              Graph selection context
            </div>
            <LabelEvidenceContextNote
              displayEvidence={displayEvidence}
              error={nodeEvidenceError}
              isLoading={isNodeEvidenceLoading}
              node={selectedGraphNode}
              nodeLabelEvidence={nodeLabelEvidence}
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-[minmax(240px,0.32fr)_minmax(0,1fr)]">
            <aside className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs font-medium uppercase text-slate-500">
                    Sources
                  </div>
                  <div className="text-xs text-slate-500">
                    Brand, generic, manufacturer
                  </div>
                </div>
                <Badge className="bg-white text-slate-700">
                  {records.length}
                </Badge>
              </div>
              {records.length === 0 ? (
                <p className="text-sm text-slate-600">
                  No label records returned.
                </p>
              ) : (
                <div className="space-y-2">
                  {records.map((source) => {
                    const brandName = primaryValue(source.record.brand_names);
                    const genericName = primaryValue(source.record.generic_names);
                    const manufacturerName = primaryValue(
                      source.record.manufacturer_names
                    );
                    const isSelected = source.key === selectedSourceKey;
                    const sourceClasses = isSelected
                      ? sourceSelectionClasses
                      : source.isSelectedNodeOnly
                        ? nodeSpecificClasses
                        : searchSourceClasses;
                    return (
                      <button
                        key={source.key}
                        type="button"
                        onClick={() => handleSourceStripClick(source.key)}
                        className={cn(
                          "w-full rounded-md border p-2 text-left text-xs transition",
                          sourceClasses
                        )}
                      >
                        <div className="mb-1 flex flex-wrap items-center gap-1.5">
                          <Badge className="bg-white text-slate-800">
                            Source {source.sourceNumber}
                          </Badge>
                          {!source.isSelectedNodeOnly ? (
                            <Badge className={searchSpecificBadgeClasses}>
                              Search-specific
                            </Badge>
                          ) : null}
                          {source.isSelectedNodeOnly ||
                          source.isSelectedNodeMatch ? (
                            <Badge className={nodeSpecificBadgeClasses}>
                              Node-specific
                            </Badge>
                          ) : null}
                          {isSelected ? (
                            <Badge className={selectedSourceBadgeClasses}>
                              Selected
                            </Badge>
                          ) : null}
                        </div>
                        <div className="truncate font-medium text-slate-900">
                          {brandName ?? genericName ?? "Unnamed label"}
                        </div>
                        <div className="truncate text-slate-600">
                          {genericName ?? "Generic unavailable"}
                        </div>
                        <div className="truncate text-slate-500">
                          {manufacturerName ?? "Manufacturer unavailable"}
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </aside>

            <section className="min-w-0">
              {sectionEntries.length === 0 ? (
                <p className="text-sm text-slate-600">
                  No OpenFDA sections returned.
                </p>
              ) : (
                <div className="flex flex-col gap-4">
                  <div className="flex flex-wrap gap-2">
                    {sectionEntries.map(([section, texts]) => (
                      <Button
                        key={section}
                        type="button"
                        variant={
                          activeSection === section ? "primary" : "secondary"
                        }
                        onClick={() => onSelectSection(section)}
                      >
                        {displaySectionName(section)}
                        <span className="text-xs opacity-75">
                          {texts.length}
                        </span>
                      </Button>
                    ))}
                  </div>

                  <div ref={evidenceCardsRef} className="space-y-3">
                    {activeTexts.map((entry, index) => {
                      const sourceKey = entry.displaySourceKey;
                      const source = sourceKey
                        ? displayEvidence.sourceByKey.get(sourceKey)
                        : null;
                      const brandName = primaryValue(
                        source?.record.brand_names
                      );
                      const manufacturerName = primaryValue(
                        source?.record.manufacturer_names
                      );
                      const isSelected =
                        Boolean(sourceKey) && sourceKey === selectedSourceKey;
                      const isNodeSpecific = sourceKey
                        ? displayEvidence.selectedNodeSourceKeys.has(sourceKey)
                        : false;
                      const evidenceClasses = isSelected
                        ? sourceSelectionClasses
                        : source?.isSelectedNodeOnly
                          ? nodeSpecificClasses
                          : "border-slate-200 bg-slate-50 hover:border-slate-300 hover:bg-white";
                      return (
                        <button
                          key={`${sourceKey ?? entry.source_id}-${index}`}
                          type="button"
                          onClick={() => onSelectSource(sourceKey)}
                          className={cn(
                            "w-full rounded-md border p-3 text-left transition",
                            evidenceClasses
                          )}
                        >
                          <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                            {source ? (
                              <span className="inline-flex items-center rounded-md border border-slate-200 bg-white px-2 py-0.5 font-medium text-slate-800">
                                Source {source.sourceNumber}
                              </span>
                            ) : (
                              <Badge>Source unknown</Badge>
                            )}
                            {!source?.isSelectedNodeOnly ? (
                              <Badge className={searchSpecificBadgeClasses}>
                                Search-specific
                              </Badge>
                            ) : null}
                            {isNodeSpecific ? (
                              <Badge className={nodeSpecificBadgeClasses}>
                                Node-specific
                              </Badge>
                            ) : null}
                            {brandName ? <span>{brandName}</span> : null}
                            {manufacturerName ? (
                              <span>· {manufacturerName}</span>
                            ) : null}
                          </div>
                          <p className="whitespace-pre-wrap text-sm leading-6 text-slate-800">
                            {entry.text}
                          </p>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </section>
          </div>
          {labelEvidence?.errors.length ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              {labelEvidence.errors.join(" ")}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

function LabelEvidenceContextNote({
  displayEvidence,
  error,
  isLoading,
  node,
  nodeLabelEvidence,
}: {
  displayEvidence: DisplayEvidenceModel;
  error: string | null;
  isLoading: boolean;
  node: RxNormConcept | null;
  nodeLabelEvidence: OpenFDALabelEvidence | null;
}) {
  if (!node) {
    return (
      <div className="text-sm leading-6 text-slate-600">
        Select a node in the RxNorm graph above to check whether OpenFDA has
        labels for that specific concept.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm leading-6 text-slate-700">
        <Loader2 className="size-4 animate-spin text-slate-500" />
        Looking up labels for{" "}
        <span className="font-medium text-slate-900">{node.name}</span>.
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
        {error}
      </div>
    );
  }

  if (nodeLabelEvidence && nodeLabelEvidence.labels_found === 0) {
    return (
      <div className="text-sm leading-6 text-slate-700">
        Selected graph node:{" "}
        <span className="font-medium text-slate-950">{node.name}</span>. No
        specific OpenFDA labels were found, so the evidence below remains tied
        to the original search.
      </div>
    );
  }

  if (displayEvidence.selectedNodeOnlyCount > 0) {
    return (
      <div className="text-sm leading-6 text-slate-700">
        Selected graph node:{" "}
        <span className="font-medium text-slate-950">{node.name}</span>. Found{" "}
        {displayEvidence.selectedNodeOnlyCount} node-specific source
        {displayEvidence.selectedNodeOnlyCount === 1 ? "" : "s"} and pinned{" "}
        {displayEvidence.selectedNodeOnlyCount === 1 ? "it" : "them"} first.
      </div>
    );
  }

  if (displayEvidence.selectedNodeMatchCount > 0) {
    return (
      <div className="text-sm leading-6 text-slate-700">
        Selected graph node:{" "}
        <span className="font-medium text-slate-950">{node.name}</span>. Its
        labels match source
        {displayEvidence.selectedNodeMatchCount === 1 ? "" : "s"} already
        returned for the original search.
      </div>
    );
  }

  return (
    <div className="text-sm leading-6 text-slate-700">
      Selected graph node:{" "}
      <span className="font-medium text-slate-950">{node.name}</span>.
    </div>
  );
}
