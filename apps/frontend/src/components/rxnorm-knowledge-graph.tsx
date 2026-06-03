"use client";

import type { MouseEvent } from "react";
import { useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DrugDossier, RxNormConcept, RxNormEdge } from "@/lib/types";

const ttyStyles: Record<string, { label: string; fill: string; stroke: string }> = {
  IN: { label: "Ingredient", fill: "#ecfeff", stroke: "#0891b2" },
  PIN: { label: "Precise Ingredient", fill: "#ccfbf1", stroke: "#0f766e" },
  MIN: { label: "Multiple Ingredients", fill: "#f0fdf4", stroke: "#16a34a" },
  SCDC: {
    label: "Semantic Clinical Drug Component",
    fill: "#eff6ff",
    stroke: "#2563eb",
  },
  SCDF: {
    label: "Semantic Clinical Drug Form",
    fill: "#dbeafe",
    stroke: "#1d4ed8",
  },
  SCDFP: {
    label: "Semantic Clinical Drug Form Precise",
    fill: "#e0f2fe",
    stroke: "#0369a1",
  },
  SCDG: {
    label: "Semantic Clinical Drug Group",
    fill: "#eef2ff",
    stroke: "#4f46e5",
  },
  SCDGP: {
    label: "Semantic Clinical Drug Form Group Precise",
    fill: "#e0e7ff",
    stroke: "#4338ca",
  },
  BN: { label: "Brand", fill: "#fff7ed", stroke: "#ea580c" },
  SBDC: {
    label: "Semantic Branded Drug Component",
    fill: "#fdf2f8",
    stroke: "#db2777",
  },
  SBDF: {
    label: "Semantic Branded Drug Form",
    fill: "#fae8ff",
    stroke: "#c026d3",
  },
  SBDFP: {
    label: "Semantic Branded Drug Form Precise",
    fill: "#f5d0fe",
    stroke: "#a21caf",
  },
  SBDG: {
    label: "Semantic Branded Drug Group",
    fill: "#fce7f3",
    stroke: "#be185d",
  },
  SBD: { label: "Semantic Branded Drug", fill: "#f5f3ff", stroke: "#7c3aed" },
  SCD: { label: "Semantic Clinical Drug", fill: "#eff6ff", stroke: "#2563eb" },
  GPCK: { label: "Generic Pack", fill: "#f1f5f9", stroke: "#475569" },
  BPCK: { label: "Brand Name Pack", fill: "#faf5ff", stroke: "#9333ea" },
  DF: { label: "Dose Form", fill: "#fefce8", stroke: "#ca8a04" },
  DFG: { label: "Dose Form Group", fill: "#fef9c3", stroke: "#a16207" },
  PSN: { label: "Prescribable Name", fill: "#f8fafc", stroke: "#64748b" },
  SY: { label: "Synonym", fill: "#f8fafc", stroke: "#94a3b8" },
  TMSY: {
    label: "Tall Man Lettering Synonym",
    fill: "#f8fafc",
    stroke: "#334155",
  },
};

function getTtyStyle(tty?: string | null) {
  return ttyStyles[(tty ?? "").toUpperCase()] ?? {
    label: tty ? humanizeToken(tty) : "Other",
    fill: "#f8fafc",
    stroke: "#94a3b8",
  };
}

function humanizeToken(value: string) {
  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function humanizeRelation(value: string) {
  return humanizeToken(value).toLowerCase();
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

function displayNodeName(value: string) {
  return value.toUpperCase();
}

function nodeTooltip(node: RxNormConcept) {
  const style = getTtyStyle(node.tty);
  return `${displayNodeName(node.name)}\nType: ${style.label}\nRXCUI: ${node.rxcui}`;
}

function edgeTooltip(edge: RxNormEdge) {
  return `${displayNodeName(edge.target_name)} ${humanizeRelation(
    edge.relation
  )} ${displayNodeName(edge.source_name)}`;
}

export function RxNormKnowledgeGraph({ dossier }: { dossier: DrugDossier }) {
  const [selectedRxcui, setSelectedRxcui] = useState<string | null>(
    dossier.resolved_drug?.rxcui ?? null
  );
  const [tooltip, setTooltip] = useState<{
    text: string;
    x: number;
    y: number;
  } | null>(null);
  const graphFrameRef = useRef<HTMLDivElement>(null);
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
  const visibleNodeTypes = useMemo(() => {
    return Array.from(
      new Set(
        visualRxcuis.map((rxcui) => nodeMap.get(rxcui)?.tty).filter(Boolean)
      )
    ).sort((left, right) =>
      getTtyStyle(left).label.localeCompare(getTtyStyle(right).label)
    );
  }, [nodeMap, visualRxcuis]);
  const truncated =
    dossier.rxnorm_neighborhood.truncated || edges.length > visualEdges.length;

  function updateTooltip(event: MouseEvent<SVGElement>, text: string) {
    const frame = graphFrameRef.current;
    if (!frame) {
      return;
    }
    const bounds = frame.getBoundingClientRect();
    const rawX = event.clientX - bounds.left + 14;
    const rawY = event.clientY - bounds.top + 14;
    setTooltip({
      text,
      x: Math.min(rawX, Math.max(12, bounds.width - 300)),
      y: Math.min(rawY, Math.max(12, bounds.height - 120)),
    });
  }

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
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
            <div
              ref={graphFrameRef}
              className="relative overflow-hidden rounded-md border border-slate-200 bg-white"
            >
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
                  const source = positionedNodes.get(edge.target_rxcui);
                  const target = positionedNodes.get(edge.source_rxcui);
                  if (!source || !target) {
                    return null;
                  }
                  const tooltipText = edgeTooltip(edge);
                  return (
                    <g key={`${edge.source_rxcui}-${edge.relation}-${edge.target_rxcui}`}>
                      <line
                        x1={source.x}
                        x2={target.x}
                        y1={source.y}
                        y2={target.y}
                        stroke="transparent"
                        strokeWidth="14"
                        className="cursor-default"
                        onMouseEnter={(event) =>
                          updateTooltip(event, tooltipText)
                        }
                        onMouseMove={(event) =>
                          updateTooltip(event, tooltipText)
                        }
                        onMouseLeave={() => setTooltip(null)}
                      />
                      <line
                        x1={source.x}
                        x2={target.x}
                        y1={source.y}
                        y2={target.y}
                        stroke="#cbd5e1"
                        strokeWidth="1.5"
                        markerEnd="url(#arrow)"
                        pointerEvents="none"
                      />
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
                      onMouseEnter={(event) =>
                        updateTooltip(event, nodeTooltip(node))
                      }
                      onMouseMove={(event) =>
                        updateTooltip(event, nodeTooltip(node))
                      }
                      onMouseLeave={() => setTooltip(null)}
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
                        {shortLabel(displayNodeName(node.name), isCenter ? 28 : 20)}
                      </text>
                    </g>
                  );
                })}
              </svg>
              {tooltip ? (
                <div
                  className="pointer-events-none absolute z-10 max-w-72 whitespace-pre-line rounded-md border border-slate-200 bg-white px-3 py-2 text-xs leading-5 text-slate-700 shadow-lg"
                  style={{
                    left: tooltip.x,
                    top: tooltip.y,
                  }}
                >
                  {tooltip.text}
                </div>
              ) : null}
            </div>
            <div className="space-y-3">
              <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
                <div className="text-xs font-medium uppercase text-slate-500">
                  Selected node
                </div>
                {selectedNode ? (
                  <div className="mt-2 space-y-2">
                    <div className="font-semibold text-slate-950">
                      {displayNodeName(selectedNode.name)}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Badge>RXCUI {selectedNode.rxcui}</Badge>
                      <Badge>{getTtyStyle(selectedNode.tty).label}</Badge>
                    </div>
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-slate-600">Select a node.</p>
                )}
              </div>

              <div className="rounded-md border border-slate-200 bg-white p-3">
                <div className="text-xs font-medium uppercase text-slate-500">
                  Node types
                </div>
                <div className="mt-3 space-y-2">
                  {visibleNodeTypes.map((tty) => {
                    const style = getTtyStyle(tty);
                    return (
                      <span
                        key={tty}
                        className="flex items-center gap-2 text-xs text-slate-700"
                      >
                        <span
                          className="size-3 rounded-full border"
                          style={{
                            backgroundColor: style.fill,
                            borderColor: style.stroke,
                          }}
                        />
                        {style.label}
                      </span>
                    );
                  })}
                </div>
              </div>
              <p className="text-xs leading-5 text-slate-500">
                Showing {visualEdges.length} of {edges.length} returned RxNorm
                relationships. Hover over a line to see the relationship.
              </p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
