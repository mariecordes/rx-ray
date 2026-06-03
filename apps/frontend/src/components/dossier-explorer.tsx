"use client";

import { FormEvent, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  Database,
  FileText,
  FlaskConical,
  Loader2,
  Network,
  Search,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  DrugDossier,
  LabelSection,
  OpenFDALabelRecord,
  RxNormConcept,
  RxNormEdge,
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

function joinValues(values?: string[] | null) {
  if (!values || values.length === 0) {
    return "—";
  }
  return values.join(", ");
}

function primaryValue(values?: string[] | null) {
  if (!values || values.length === 0) {
    return null;
  }
  return values[0];
}

function groupEdges(edges: RxNormEdge[]) {
  return edges.reduce<Record<string, RxNormEdge[]>>((groups, edge) => {
    groups[edge.relation] = groups[edge.relation] ?? [];
    groups[edge.relation].push(edge);
    return groups;
  }, {});
}

const ttyStyles: Record<string, { label: string; fill: string; stroke: string }> = {
  IN: { label: "Ingredient", fill: "#ecfeff", stroke: "#0891b2" },
  PIN: { label: "Precise ingredient", fill: "#ecfeff", stroke: "#0891b2" },
  MIN: { label: "Multi-ingredient", fill: "#f0fdf4", stroke: "#16a34a" },
  BN: { label: "Brand", fill: "#fff7ed", stroke: "#ea580c" },
  SCD: { label: "Clinical drug", fill: "#eff6ff", stroke: "#2563eb" },
  SBD: { label: "Branded drug", fill: "#f5f3ff", stroke: "#7c3aed" },
  SCDF: { label: "Clinical form", fill: "#f8fafc", stroke: "#64748b" },
  SBDF: { label: "Branded form", fill: "#fdf2f8", stroke: "#db2777" },
  DF: { label: "Dose form", fill: "#fefce8", stroke: "#ca8a04" },
  DFG: { label: "Dose form group", fill: "#fefce8", stroke: "#ca8a04" },
};

function getTtyStyle(tty?: string | null) {
  return ttyStyles[(tty ?? "").toUpperCase()] ?? {
    label: tty ?? "Other",
    fill: "#f8fafc",
    stroke: "#94a3b8",
  };
}

function shortLabel(value: string, maxLength = 24) {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength - 3)}...`;
}

function buildNodeMap(nodes: RxNormConcept[]) {
  return new Map(nodes.map((node) => [node.rxcui, node]));
}

export function DossierExplorer() {
  const [drug, setDrug] = useState("aspirin");
  const [maxEdges, setMaxEdges] = useState(75);
  const [openfdaLimit, setOpenfdaLimit] = useState(5);
  const [dossier, setDossier] = useState<DrugDossier | null>(null);
  const [selectedSection, setSelectedSection] = useState<string | null>(null);
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sourcesPanelRef = useRef<HTMLDivElement>(null);
  const labelEvidencePanelRef = useRef<HTMLDivElement>(null);

  const labelEvidence = dossier?.label_evidence ?? null;
  const sectionEntries = useMemo(() => {
    return Object.entries(labelEvidence?.sections ?? {});
  }, [labelEvidence]);
  const activeSection = selectedSection ?? sectionEntries[0]?.[0] ?? null;
  const activeTexts: LabelSection[] = activeSection
    ? labelEvidence?.sections[activeSection] ?? []
    : [];
  const sourceById = useMemo(() => {
    return new Map(
      (labelEvidence?.label_records ?? []).map((record) => [
        record.source_id,
        record,
      ])
    );
  }, [labelEvidence]);
  const sourceNumberById = useMemo(() => {
    return new Map(
      (labelEvidence?.label_records ?? []).map((record, index) => [
        record.source_id,
        index + 1,
      ])
    );
  }, [labelEvidence]);
  function selectSourceFromEvidence(sourceId?: string | null) {
    if (!sourceId) {
      return;
    }
    const nextSourceId = selectedSourceId === sourceId ? null : sourceId;
    setSelectedSourceId(nextSourceId);
    if (!nextSourceId) {
      return;
    }
    sourcesPanelRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
  }

  function selectSourceFromSourcePanel(sourceId?: string | null) {
    if (!sourceId) {
      return;
    }
    const nextSourceId = selectedSourceId === sourceId ? null : sourceId;
    setSelectedSourceId(nextSourceId);
    if (!nextSourceId) {
      return;
    }
    labelEvidencePanelRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch("/api/dossier", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          drug,
          depth: 1,
          max_edges: maxEdges,
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
      setSelectedSourceId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to build dossier");
    } finally {
      setIsLoading(false);
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
          className="grid gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm md:grid-cols-[1fr_140px_140px_auto]"
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
          <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
            Max edges
            <Input
              min={1}
              max={500}
              type="number"
              value={maxEdges}
              onChange={(event) => setMaxEdges(Number(event.target.value))}
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
            <RxNormPanel
              key={dossier.resolved_drug?.rxcui ?? dossier.query}
              dossier={dossier}
            />
            <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
              <LabelEvidencePanel
                ref={labelEvidencePanelRef}
                activeSection={activeSection}
                activeTexts={activeTexts}
                sectionEntries={sectionEntries}
                sourceById={sourceById}
                sourceNumberById={sourceNumberById}
                selectedSourceId={selectedSourceId}
                onSelectSection={setSelectedSection}
                onSelectSource={selectSourceFromEvidence}
              />
              <SourcesPanel
                ref={sourcesPanelRef}
                labelEvidence={labelEvidence}
                selectedSourceId={selectedSourceId}
                sourceNumberById={sourceNumberById}
                onSelectSource={selectSourceFromSourcePanel}
              />
            </div>
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

function RxNormPanel({ dossier }: { dossier: DrugDossier }) {
  const [selectedRxcui, setSelectedRxcui] = useState<string | null>(
    dossier.resolved_drug?.rxcui ?? null
  );
  const edges = dossier.rxnorm_neighborhood.edges;
  const nodes = dossier.rxnorm_neighborhood.nodes;
  const centerRxcui = dossier.resolved_drug?.rxcui ?? null;
  const nodeMap = useMemo(() => buildNodeMap(nodes), [nodes]);
  const visualEdges = useMemo(() => edges.slice(0, 40), [edges]);
  const visualRxcuis = useMemo(() => {
    const ids = new Set<string>();
    if (centerRxcui) {
      ids.add(centerRxcui);
    }
    for (const edge of visualEdges) {
      ids.add(edge.source_rxcui);
      ids.add(edge.target_rxcui);
    }
    return Array.from(ids);
  }, [centerRxcui, visualEdges]);
  const positionedNodes = useMemo(() => {
    const width = 900;
    const height = 460;
    const center = { x: width / 2, y: height / 2 };
    const neighborIds = visualRxcuis.filter((rxcui) => rxcui !== centerRxcui);
    const radius = Math.min(180, 92 + neighborIds.length * 7);

    return new Map(
      visualRxcuis.map((rxcui) => {
        if (rxcui === centerRxcui) {
          return [rxcui, center];
        }
        const neighborIndex = neighborIds.indexOf(rxcui);
        const angle = (2 * Math.PI * neighborIndex) / Math.max(neighborIds.length, 1);
        return [
          rxcui,
          {
            x: center.x + radius * Math.cos(angle),
            y: center.y + radius * Math.sin(angle),
          },
        ];
      })
    );
  }, [centerRxcui, visualRxcuis]);
  const selectedNode = selectedRxcui ? nodeMap.get(selectedRxcui) : null;
  const groupedEdges = useMemo(() => groupEdges(edges), [edges]);
  const entries = Object.entries(groupedEdges);
  const truncated =
    dossier.rxnorm_neighborhood.truncated || edges.length > visualEdges.length;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <CardTitle>RxNorm Knowledge Graph</CardTitle>
        {truncated ? <Badge className="bg-amber-50 text-amber-800">Truncated</Badge> : null}
      </CardHeader>
      <CardContent className="space-y-4">
        {edges.length === 0 ? (
          <p className="text-sm text-slate-600">No RxNorm edges returned.</p>
        ) : (
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_280px]">
            <div className="overflow-hidden rounded-md border border-slate-200 bg-white">
              <svg
                viewBox="0 0 900 460"
                className="h-[360px] w-full sm:h-[420px]"
                role="img"
                aria-label="RxNorm local knowledge graph"
              >
                <defs>
                  <marker
                    id="arrow"
                    markerHeight="8"
                    markerWidth="8"
                    orient="auto"
                    refX="8"
                    refY="4"
                  >
                    <path d="M0,0 L8,4 L0,8 Z" fill="#94a3b8" />
                  </marker>
                </defs>
                {visualEdges.map((edge) => {
                  const source = positionedNodes.get(edge.source_rxcui);
                  const target = positionedNodes.get(edge.target_rxcui);
                  if (!source || !target) {
                    return null;
                  }
                  return (
                    <g key={`${edge.source_rxcui}-${edge.relation}-${edge.target_rxcui}`}>
                      <line
                        x1={source.x}
                        x2={target.x}
                        y1={source.y}
                        y2={target.y}
                        stroke="#cbd5e1"
                        strokeWidth="1.5"
                        markerEnd="url(#arrow)"
                      />
                      <text
                        x={(source.x + target.x) / 2}
                        y={(source.y + target.y) / 2}
                        className="fill-slate-500 text-[10px]"
                        textAnchor="middle"
                      >
                        {shortLabel(edge.relation, 18)}
                      </text>
                    </g>
                  );
                })}
                {visualRxcuis.map((rxcui) => {
                  const node = nodeMap.get(rxcui);
                  const point = positionedNodes.get(rxcui);
                  if (!node || !point) {
                    return null;
                  }
                  const isCenter = rxcui === centerRxcui;
                  const isSelected = rxcui === selectedRxcui;
                  const style = getTtyStyle(node.tty);
                  const radius = isCenter ? 34 : 24;
                  return (
                    <g
                      key={rxcui}
                      className="cursor-pointer"
                      onClick={() => setSelectedRxcui(rxcui)}
                    >
                      <circle
                        cx={point.x}
                        cy={point.y}
                        r={radius}
                        fill={style.fill}
                        stroke={isSelected ? "#0f172a" : style.stroke}
                        strokeWidth={isSelected ? 4 : 2}
                      />
                      <text
                        x={point.x}
                        y={point.y + radius + 16}
                        className="fill-slate-700 text-[12px] font-medium"
                        textAnchor="middle"
                      >
                        {shortLabel(node.name, isCenter ? 28 : 20)}
                      </text>
                      <text
                        x={point.x}
                        y={point.y + 4}
                        className="fill-slate-700 text-[11px] font-semibold"
                        textAnchor="middle"
                      >
                        {node.tty ?? "?"}
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>
            <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <div className="text-xs font-medium uppercase text-slate-500">
                Selected node
              </div>
              {selectedNode ? (
                <div className="mt-2 space-y-2">
                  <div className="font-semibold text-slate-950">
                    {selectedNode.name}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge>RXCUI {selectedNode.rxcui}</Badge>
                    <Badge>{selectedNode.tty ?? "TTY unknown"}</Badge>
                    <Badge>{getTtyStyle(selectedNode.tty).label}</Badge>
                  </div>
                </div>
              ) : (
                <p className="mt-2 text-sm text-slate-600">Select a node.</p>
              )}
              <div className="mt-4 text-xs font-medium uppercase text-slate-500">
                Node types
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {Array.from(
                  new Set(
                    visualRxcuis
                      .map((rxcui) => nodeMap.get(rxcui)?.tty)
                      .filter(Boolean)
                  )
                ).map((tty) => {
                  const style = getTtyStyle(tty);
                  return (
                    <span
                      key={tty}
                      className="inline-flex items-center gap-1 text-xs text-slate-600"
                    >
                      <span
                        className="size-2 rounded-full"
                        style={{ backgroundColor: style.stroke }}
                      />
                      {tty} · {style.label}
                    </span>
                  );
                })}
              </div>
              <p className="mt-4 text-xs leading-5 text-slate-500">
                Showing {visualEdges.length} of {edges.length} returned RxNorm
                relationships.
              </p>
            </div>
          </div>
        )}
        {entries.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {entries.map(([relation, relationEdges]) => (
              <Badge key={relation}>
                {relation} · {relationEdges.length}
              </Badge>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function LabelEvidencePanel({
  ref,
  activeSection,
  activeTexts,
  sectionEntries,
  sourceById,
  sourceNumberById,
  selectedSourceId,
  onSelectSection,
  onSelectSource,
}: {
  ref: React.RefObject<HTMLDivElement | null>;
  activeSection: string | null;
  activeTexts: LabelSection[];
  sectionEntries: [string, LabelSection[]][];
  sourceById: Map<string | null | undefined, OpenFDALabelRecord>;
  sourceNumberById: Map<string | null | undefined, number>;
  selectedSourceId: string | null;
  onSelectSection: (section: string) => void;
  onSelectSource: (sourceId?: string | null) => void;
}) {
  return (
    <div ref={ref}>
      <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <CardTitle>Label Evidence</CardTitle>
        <FileText className="size-4 text-slate-400" />
      </CardHeader>
      <CardContent>
        {sectionEntries.length === 0 ? (
          <p className="text-sm text-slate-600">No OpenFDA sections returned.</p>
        ) : (
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap gap-2">
              {sectionEntries.map(([section, texts]) => (
                <Button
                  key={section}
                  type="button"
                  variant={activeSection === section ? "primary" : "secondary"}
                  onClick={() => onSelectSection(section)}
                >
                  {displaySectionName(section)}
                  <span className="text-xs opacity-75">{texts.length}</span>
                </Button>
              ))}
            </div>

            <div className="space-y-3">
              {activeTexts.map((entry, index) => {
                const source = sourceById.get(entry.source_id);
                const sourceNumber = sourceNumberById.get(entry.source_id);
                const brandName = primaryValue(source?.brand_names);
                const manufacturerName = primaryValue(source?.manufacturer_names);
                const isSelected = entry.source_id === selectedSourceId;
                return (
                  <button
                    key={`${entry.source_id}-${index}`}
                    type="button"
                    onClick={() => onSelectSource(entry.source_id)}
                    className={cn(
                      "w-full rounded-md border p-3 text-left transition",
                      isSelected
                        ? "border-cyan-400 bg-cyan-50 shadow-sm"
                        : "border-slate-200 bg-slate-50 hover:border-slate-300 hover:bg-white"
                    )}
                  >
                    <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                      {sourceNumber ? (
                        <span className="inline-flex items-center rounded-md border border-cyan-200 bg-cyan-50 px-2 py-0.5 font-medium text-cyan-800">
                          Source {sourceNumber}
                        </span>
                      ) : (
                        <Badge>Source unknown</Badge>
                      )}
                      {brandName ? <span>{brandName}</span> : null}
                      {manufacturerName ? <span>· {manufacturerName}</span> : null}
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
      </CardContent>
      </Card>
    </div>
  );
}

const SourcesPanel = function SourcesPanel({
  labelEvidence,
  selectedSourceId,
  sourceNumberById,
  onSelectSource,
  ref,
}: {
  labelEvidence: DrugDossier["label_evidence"];
  selectedSourceId: string | null;
  sourceNumberById: Map<string | null | undefined, number>;
  onSelectSource: (sourceId?: string | null) => void;
  ref: React.RefObject<HTMLDivElement | null>;
}) {
  const records = labelEvidence?.label_records ?? [];

  return (
    <aside ref={ref} className="flex flex-col gap-5">
      <Card className="xl:sticky xl:top-5">
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <CardTitle>Sources</CardTitle>
          <Network className="size-4 text-slate-400" />
        </CardHeader>
        <CardContent>
          {labelEvidence ? (
            <div className="mb-4 grid grid-cols-2 gap-2">
              <Metric label="Retrieval" value={labelEvidence.retrieval_mode} />
              <Metric
                label="Records"
                value={`${labelEvidence.labels_found}/${labelEvidence.label_limit ?? "—"}`}
              />
            </div>
          ) : null}
          {records.length === 0 ? (
            <p className="text-sm text-slate-600">No label records returned.</p>
          ) : (
            <div className="space-y-3">
              {records.map((record) => {
                const sourceNumber = sourceNumberById.get(record.source_id);
                const isSelected = record.source_id === selectedSourceId;
                return (
                  <button
                    key={record.source_id ?? record.id ?? record.set_id}
                    type="button"
                    onClick={() => onSelectSource(record.source_id)}
                    className={cn(
                      "w-full rounded-md border p-3 text-left text-sm transition",
                      isSelected
                        ? "border-cyan-400 bg-cyan-50 shadow-sm"
                        : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
                    )}
                  >
                    <div className="mb-3 flex flex-wrap items-center gap-2">
                      <Badge className="bg-cyan-50 text-cyan-800">
                        Source {sourceNumber ?? "?"}
                      </Badge>
                    </div>
                    <dl className="space-y-2 text-slate-700">
                      <SourceRow
                        label="Brand"
                        value={joinValues(record.brand_names)}
                      />
                      <SourceRow
                        label="Generic"
                        value={joinValues(record.generic_names)}
                      />
                      <SourceRow
                        label="Manufacturer"
                        value={joinValues(record.manufacturer_names)}
                      />
                    </dl>
                  </button>
                );
              })}
            </div>
          )}
          {labelEvidence?.errors.length ? (
            <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              {labelEvidence.errors.join(" ")}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </aside>
  );
};

function SourceRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase text-slate-500">{label}</dt>
      <dd className="mt-0.5 break-words">{value}</dd>
    </div>
  );
}
