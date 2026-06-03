"use client";

import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DrugDossier, RxNormConcept, RxNormEdge } from "@/lib/types";

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

function groupEdges(edges: RxNormEdge[]) {
  return edges.reduce<Record<string, RxNormEdge[]>>((groups, edge) => {
    groups[edge.relation] = groups[edge.relation] ?? [];
    groups[edge.relation].push(edge);
    return groups;
  }, {});
}

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

export function RxNormKnowledgeGraph({ dossier }: { dossier: DrugDossier }) {
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
        const angle =
          (2 * Math.PI * neighborIndex) / Math.max(neighborIds.length, 1);
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
        {truncated ? (
          <Badge className="bg-amber-50 text-amber-800">Truncated</Badge>
        ) : null}
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
                      {tty} - {style.label}
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
                {relation} - {relationEdges.length}
              </Badge>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
