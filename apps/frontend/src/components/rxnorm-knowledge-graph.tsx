"use client";

import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
} from "d3-force";
import type { MouseEvent, PointerEvent, WheelEvent } from "react";
import { useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DrugDossier, RxNormConcept, RxNormEdge } from "@/lib/types";

const GRAPH_WIDTH = 900;
const GRAPH_HEIGHT = 520;
const MAX_VISUAL_NODES = 80;
const MAX_VISUAL_EDGES = 120;
const MAX_CENTER_EDGES = 42;

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

type VisualNode = RxNormConcept & {
  depthLevel: 0 | 1 | 2;
};

type ForceNode = VisualNode & {
  fx?: number;
  fy?: number;
  x?: number;
  y?: number;
};

type ForceLink = {
  source: string | ForceNode;
  target: string | ForceNode;
};

function buildVisualGraph(
  centerRxcui: string | null,
  nodes: RxNormConcept[],
  edges: RxNormEdge[]
) {
  const nodeMap = buildNodeMap(nodes);
  const centerEdges = centerRxcui
    ? edges.filter(
        (edge) =>
          edge.source_rxcui === centerRxcui || edge.target_rxcui === centerRxcui
      )
    : [];
  const firstHopIds = new Set<string>();
  for (const edge of centerEdges) {
    if (edge.source_rxcui !== centerRxcui) {
      firstHopIds.add(edge.source_rxcui);
    }
    if (edge.target_rxcui !== centerRxcui) {
      firstHopIds.add(edge.target_rxcui);
    }
  }

  const selectedIds = new Set<string>();
  if (centerRxcui) {
    selectedIds.add(centerRxcui);
  }

  const visualEdges: RxNormEdge[] = [];
  for (const edge of centerEdges) {
    if (visualEdges.length >= MAX_CENTER_EDGES) {
      break;
    }
    const newNodeCount =
      Number(!selectedIds.has(edge.source_rxcui)) +
      Number(!selectedIds.has(edge.target_rxcui));
    if (selectedIds.size + newNodeCount > MAX_VISUAL_NODES) {
      continue;
    }
    visualEdges.push(edge);
    selectedIds.add(edge.source_rxcui);
    selectedIds.add(edge.target_rxcui);
  }

  const contextEdges = edges.filter((edge) => !centerEdges.includes(edge));
  for (const edge of contextEdges) {
    if (visualEdges.length >= MAX_VISUAL_EDGES) {
      break;
    }
    const knownEndpoints =
      selectedIds.has(edge.source_rxcui) || selectedIds.has(edge.target_rxcui);
    const newNodeCount =
      Number(!selectedIds.has(edge.source_rxcui)) +
      Number(!selectedIds.has(edge.target_rxcui));

    if (!knownEndpoints || selectedIds.size + newNodeCount > MAX_VISUAL_NODES) {
      continue;
    }

    visualEdges.push(edge);
    selectedIds.add(edge.source_rxcui);
    selectedIds.add(edge.target_rxcui);
  }

  const visualNodes: VisualNode[] = Array.from(selectedIds)
    .map((rxcui) => nodeMap.get(rxcui))
    .filter((node): node is RxNormConcept => Boolean(node))
    .map((node) => ({
      ...node,
      depthLevel:
        node.rxcui === centerRxcui ? 0 : firstHopIds.has(node.rxcui) ? 1 : 2,
    }));

  return { firstHopIds, visualEdges, visualNodes };
}

function computeLayout(
  centerRxcui: string | null,
  visualNodes: VisualNode[],
  visualEdges: RxNormEdge[]
) {
  const simulationNodes = visualNodes.map((node, index) => {
    const angle = (2 * Math.PI * index) / Math.max(visualNodes.length, 1);
    const radius = node.depthLevel === 0 ? 72 : node.depthLevel === 1 ? 170 : 250;
    return {
      ...node,
      x: GRAPH_WIDTH / 2 + radius * Math.cos(angle),
      y: GRAPH_HEIGHT / 2 + radius * Math.sin(angle),
    };
  });

  const links: ForceLink[] = visualEdges.map((edge) => ({
    source: edge.target_rxcui,
    target: edge.source_rxcui,
  }));

  const simulation = forceSimulation<ForceNode>(simulationNodes)
    .force(
      "link",
      forceLink<ForceNode, ForceLink>(links)
        .id((node) => node.rxcui)
        .distance((link) => {
          const source =
            typeof link.source === "string" ? null : link.source;
          const target =
            typeof link.target === "string" ? null : link.target;
          if (!source || !target) {
            return 100;
          }
          return source.depthLevel === 0 || target.depthLevel === 0 ? 138 : 96;
        })
        .strength(0.34)
    )
    .force("charge", forceManyBody().strength(-310))
    .force(
      "collide",
      forceCollide((node) => {
        return nodeRadius(node as ForceNode) + 10;
      })
    )
    .force("center", forceCenter(GRAPH_WIDTH / 2, GRAPH_HEIGHT / 2))
    .stop();

  for (let tick = 0; tick < 260; tick += 1) {
    simulation.tick();
  }

  return new Map(
    simulationNodes.map((node) => [
      node.rxcui,
      {
        ...node,
        x: Math.max(40, Math.min(GRAPH_WIDTH - 40, node.x ?? GRAPH_WIDTH / 2)),
        y: Math.max(40, Math.min(GRAPH_HEIGHT - 40, node.y ?? GRAPH_HEIGHT / 2)),
      },
    ])
  );
}

function nodeRadius(node: Pick<VisualNode, "depthLevel">) {
  if (node.depthLevel === 0) {
    return 34;
  }
  if (node.depthLevel === 1) {
    return 22;
  }
  return 14;
}

export function RxNormKnowledgeGraph({ dossier }: { dossier: DrugDossier }) {
  const [selectedRxcui, setSelectedRxcui] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<{
    text: string;
    x: number;
    y: number;
  } | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [panDrag, setPanDrag] = useState<{
    x: number;
    y: number;
    startPanX: number;
    startPanY: number;
  } | null>(null);
  const [nodeDrag, setNodeDrag] = useState<string | null>(null);
  const [nodeOverrides, setNodeOverrides] = useState<
    Map<string, { x: number; y: number }>
  >(new Map());
  const graphFrameRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const edges = dossier.rxnorm_neighborhood.edges;
  const nodes = dossier.rxnorm_neighborhood.nodes;
  const centerRxcui = dossier.resolved_drug?.rxcui ?? null;
  const { visualEdges, visualNodes } = useMemo(
    () => buildVisualGraph(centerRxcui, nodes, edges),
    [centerRxcui, edges, nodes]
  );
  const layoutNodes = useMemo(
    () => computeLayout(centerRxcui, visualNodes, visualEdges),
    [centerRxcui, visualEdges, visualNodes]
  );
  const positionedNodes = useMemo(() => {
    return new Map(
      Array.from(layoutNodes.entries()).map(([rxcui, node]) => {
        const override = nodeOverrides.get(rxcui);
        return [rxcui, override ? { ...node, ...override } : node];
      })
    );
  }, [layoutNodes, nodeOverrides]);
  const visualRxcuis = useMemo(
    () => visualNodes.map((node) => node.rxcui),
    [visualNodes]
  );
  const selectedNode = selectedRxcui
    ? positionedNodes.get(selectedRxcui) ?? null
    : null;
  const searchedNode = centerRxcui
    ? positionedNodes.get(centerRxcui) ?? null
    : null;
  const selectedNeighborIds = useMemo(() => {
    if (!selectedRxcui) {
      return new Set<string>();
    }
    const ids = new Set<string>([selectedRxcui]);
    for (const edge of visualEdges) {
      if (edge.source_rxcui === selectedRxcui) {
        ids.add(edge.target_rxcui);
      }
      if (edge.target_rxcui === selectedRxcui) {
        ids.add(edge.source_rxcui);
      }
    }
    return ids;
  }, [selectedRxcui, visualEdges]);
  const visibleNodeTypes = useMemo(() => {
    return Array.from(
      new Set(
        visualRxcuis
          .map((rxcui) => positionedNodes.get(rxcui)?.tty)
          .filter((tty): tty is string => Boolean(tty))
      )
    ).sort((left, right) =>
      getTtyStyle(left).label.localeCompare(getTtyStyle(right).label)
    );
  }, [positionedNodes, visualRxcuis]);
  const truncated =
    dossier.rxnorm_neighborhood.truncated || edges.length > visualEdges.length;

  function screenToGraph(clientX: number, clientY: number) {
    const svg = svgRef.current;
    if (!svg) {
      return { x: GRAPH_WIDTH / 2, y: GRAPH_HEIGHT / 2 };
    }
    const bounds = svg.getBoundingClientRect();
    const viewX = ((clientX - bounds.left) / bounds.width) * GRAPH_WIDTH;
    const viewY = ((clientY - bounds.top) / bounds.height) * GRAPH_HEIGHT;
    return {
      x: (viewX - pan.x) / zoom,
      y: (viewY - pan.y) / zoom,
    };
  }

  function handleWheel(event: WheelEvent<SVGSVGElement>) {
    event.preventDefault();
    const nextZoom = Math.max(
      0.55,
      Math.min(2.6, zoom * (event.deltaY > 0 ? 0.9 : 1.1))
    );
    setZoom(nextZoom);
  }

  function handleCanvasPointerDown(event: PointerEvent<SVGSVGElement>) {
    setPanDrag({
      x: event.clientX,
      y: event.clientY,
      startPanX: pan.x,
      startPanY: pan.y,
    });
  }

  function handleNodePointerDown(
    event: PointerEvent<SVGGElement>,
    rxcui: string
  ) {
    event.stopPropagation();
    setNodeDrag(rxcui);
  }

  function handlePointerMove(event: PointerEvent<SVGSVGElement>) {
    if (nodeDrag) {
      const point = screenToGraph(event.clientX, event.clientY);
      setNodeOverrides((current) => {
        const next = new Map(current);
        next.set(nodeDrag, {
          x: Math.max(24, Math.min(GRAPH_WIDTH - 24, point.x)),
          y: Math.max(24, Math.min(GRAPH_HEIGHT - 24, point.y)),
        });
        return next;
      });
      return;
    }

    if (panDrag) {
      const svg = svgRef.current;
      if (!svg) {
        return;
      }
      const bounds = svg.getBoundingClientRect();
      const scaleX = GRAPH_WIDTH / bounds.width;
      const scaleY = GRAPH_HEIGHT / bounds.height;
      setPan({
        x: panDrag.startPanX + (event.clientX - panDrag.x) * scaleX,
        y: panDrag.startPanY + (event.clientY - panDrag.y) * scaleY,
      });
    }
  }

  function handlePointerUp() {
    setPanDrag(null);
    setNodeDrag(null);
  }

  function edgeIsIncident(edge: RxNormEdge) {
    if (!selectedRxcui) {
      return false;
    }
    return (
      edge.source_rxcui === selectedRxcui || edge.target_rxcui === selectedRxcui
    );
  }

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
                ref={svgRef}
                viewBox={`0 0 ${GRAPH_WIDTH} ${GRAPH_HEIGHT}`}
                className="h-[380px] w-full cursor-grab touch-none sm:h-[520px]"
                role="img"
                aria-label="RxNorm local knowledge graph"
                onPointerDown={handleCanvasPointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                onPointerLeave={handlePointerUp}
                onWheel={handleWheel}
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
                <g transform={`translate(${pan.x} ${pan.y}) scale(${zoom})`}>
                {visualEdges.map((edge) => {
                  const source = positionedNodes.get(edge.target_rxcui);
                  const target = positionedNodes.get(edge.source_rxcui);
                  if (!source || !target) {
                    return null;
                  }
                  const tooltipText = edgeTooltip(edge);
                  const touchesCenter =
                    edge.source_rxcui === centerRxcui ||
                    edge.target_rxcui === centerRxcui;
                  const incident = edgeIsIncident(edge);
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
                        stroke={
                          incident
                            ? "#0f172a"
                            : touchesCenter
                              ? "#64748b"
                              : "#d1d5db"
                        }
                        strokeOpacity={
                          selectedRxcui && !incident && selectedRxcui !== centerRxcui
                            ? 0.28
                            : touchesCenter
                              ? 0.78
                              : 0.5
                        }
                        strokeWidth={incident ? 2.5 : touchesCenter ? 1.8 : 1.25}
                        markerEnd="url(#arrow)"
                        pointerEvents="none"
                      />
                    </g>
                  );
                })}
                {visualRxcuis.map((rxcui) => {
                  const point = positionedNodes.get(rxcui);
                  if (!point) {
                    return null;
                  }
                  const isCenter = rxcui === centerRxcui;
                  const isSelected = rxcui === selectedRxcui;
                  const isHighlighted = selectedNeighborIds.has(rxcui);
                  const style = getTtyStyle(point.tty);
                  const radius = nodeRadius(point);
                  const showLabel =
                    isCenter ||
                    isSelected ||
                    (selectedRxcui ? isHighlighted : false);
                  return (
                    <g
                      key={rxcui}
                      className="cursor-grab"
                      onClick={() => setSelectedRxcui(rxcui)}
                      onPointerDown={(event) =>
                        handleNodePointerDown(event, rxcui)
                      }
                      onMouseEnter={(event) =>
                        updateTooltip(event, nodeTooltip(point))
                      }
                      onMouseMove={(event) =>
                        updateTooltip(event, nodeTooltip(point))
                      }
                      onMouseLeave={() => setTooltip(null)}
                    >
                      <circle
                        cx={point.x}
                        cy={point.y}
                        r={radius}
                        fill={style.fill}
                        stroke={
                          isSelected || (isCenter && !selectedRxcui)
                            ? "#0f172a"
                            : style.stroke
                        }
                        strokeWidth={
                          isSelected || (isCenter && !selectedRxcui) ? 4 : 2
                        }
                        opacity={
                          selectedRxcui && !isHighlighted && !isCenter ? 0.26 : 1
                        }
                      />
                      {showLabel ? (
                        <text
                          x={point.x}
                          y={point.y + radius + 15}
                          className="pointer-events-none fill-slate-700 text-[11px] font-medium"
                          opacity={
                            selectedRxcui && !isHighlighted && !isCenter ? 0.32 : 1
                          }
                          textAnchor="middle"
                        >
                          {shortLabel(
                            displayNodeName(point.name),
                            isCenter ? 28 : 20
                          )}
                        </text>
                      ) : null}
                    </g>
                  );
                })}
                </g>
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
                  <div className="mt-2 space-y-2">
                    <p className="text-sm text-slate-600">
                      Showing a local network around the searched concept.
                    </p>
                    {searchedNode ? (
                      <div className="flex flex-wrap gap-2">
                        <Badge>Search: {displayNodeName(searchedNode.name)}</Badge>
                      </div>
                    ) : null}
                  </div>
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
