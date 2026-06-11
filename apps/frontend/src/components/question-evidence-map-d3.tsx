"use client";

import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
} from "d3-force";
import { Maximize2, Minus, Plus } from "lucide-react";
import type { MouseEvent, PointerEvent, WheelEvent } from "react";
import { useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  EvidenceCitation,
  QuestionEvidenceMap,
  QuestionEvidenceMapEdge,
  QuestionEvidenceMapNode,
} from "@/lib/types";
import type { EvidenceMapNavigationTarget } from "./question-evidence-map-react-flow";

const GRAPH_WIDTH = 900;
const GRAPH_HEIGHT = 520;
const MIN_ZOOM = 0.75;
const MAX_ZOOM = 2;

const sectionLabels: Record<string, string> = {
  boxed_warning: "Boxed Warning",
  contraindications: "Contraindications",
  warnings: "Warnings",
  drug_interactions: "Drug Interactions",
  pregnancy: "Pregnancy",
  lactation: "Lactation",
  adverse_reactions: "Adverse Reactions",
  indications_and_usage: "Indications & Usage",
  use_in_specific_populations: "Specific Populations",
};

const nodeStyles: Record<
  string,
  { label: string; fill: string; stroke: string; radius: number }
> = {
  question: {
    label: "Question",
    fill: "#FFFFFF",
    stroke: "#64748B",
    radius: 20,
  },
  query_concept: {
    label: "Extracted concept",
    fill: "#EEF2FF",
    stroke: "#6366F1",
    radius: 12,
  },
  resolved_medication: {
    label: "Medication",
    fill: "#E8DDF9",
    stroke: "#7C3AED",
    radius: 18,
  },
  label_source: {
    label: "Label source",
    fill: "#E0F2FE",
    stroke: "#0284C7",
    radius: 10,
  },
  label_section: {
    label: "Label section",
    fill: "#CBD5E1",
    stroke: "#64748B",
    radius: 5,
  },
  rxnorm_context: {
    label: "Terminology context",
    fill: "#FEF3C7",
    stroke: "#D97706",
    radius: 12,
  },
};

type EvidenceMapD3Props = {
  map: QuestionEvidenceMap;
  onCitationClick: (citation: EvidenceCitation) => void;
  onRxcuiClick: (target: EvidenceMapNavigationTarget) => void;
};

type VisualNode = QuestionEvidenceMapNode & {
  x: number;
  y: number;
};

type VisualLink = QuestionEvidenceMapEdge & {
  sourceNode: VisualNode;
  targetNode: VisualNode;
};

type HoverTooltip = {
  x: number;
  y: number;
  title: string;
  body?: string;
};

export function EvidenceMapD3({
  map,
  onCitationClick,
  onRxcuiClick,
}: EvidenceMapD3Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [hoverTooltip, setHoverTooltip] = useState<HoverTooltip | null>(null);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [dragState, setDragState] = useState<{
    startClientX: number;
    startClientY: number;
    startPanX: number;
    startPanY: number;
  } | null>(null);

  const graph = useMemo(() => buildD3EvidenceGraph(map), [map]);
  const selectedNode =
    graph.nodes.find((node) => node.id === selectedNodeId) ?? null;
  const selectedRelatedIds = useMemo(() => {
    if (!selectedNodeId) {
      return null;
    }
    return new Set([
      selectedNodeId,
      ...graph.links
        .filter(
          (link) =>
            link.sourceNode.id === selectedNodeId ||
            link.targetNode.id === selectedNodeId
        )
        .flatMap((link) => [link.sourceNode.id, link.targetNode.id]),
    ]);
  }, [graph.links, selectedNodeId]);

  function updateZoom(nextZoom: number) {
    setZoom(Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, nextZoom)));
  }

  function handleWheel(event: WheelEvent<SVGSVGElement>) {
    event.preventDefault();
    updateZoom(zoom + (event.deltaY < 0 ? 0.08 : -0.08));
  }

  function handlePointerDown(event: PointerEvent<SVGSVGElement>) {
    if (event.target !== svgRef.current) {
      return;
    }
    setSelectedNodeId(null);
    setDragState({
      startClientX: event.clientX,
      startClientY: event.clientY,
      startPanX: pan.x,
      startPanY: pan.y,
    });
  }

  function handlePointerMove(event: PointerEvent<SVGSVGElement>) {
    if (!dragState) {
      return;
    }
    setPan({
      x: dragState.startPanX + event.clientX - dragState.startClientX,
      y: dragState.startPanY + event.clientY - dragState.startClientY,
    });
  }

  function resetView() {
    setPan({ x: 0, y: 0 });
    setZoom(1);
  }

  return (
    <div className="relative h-[560px] overflow-hidden rounded-md border border-slate-200 bg-white">
      <EvidenceMapLegend />
      <div className="absolute right-3 top-3 z-10 flex gap-1 rounded-md border border-slate-200 bg-white/90 p-1 shadow-sm backdrop-blur">
        <button
          type="button"
          onClick={() => updateZoom(zoom + 0.12)}
          className="rounded p-1.5 text-slate-600 hover:bg-slate-100"
          title="Zoom in"
        >
          <Plus className="size-3.5" />
        </button>
        <button
          type="button"
          onClick={() => updateZoom(zoom - 0.12)}
          className="rounded p-1.5 text-slate-600 hover:bg-slate-100"
          title="Zoom out"
        >
          <Minus className="size-3.5" />
        </button>
        <button
          type="button"
          onClick={resetView}
          className="rounded p-1.5 text-slate-600 hover:bg-slate-100"
          title="Reset view"
        >
          <Maximize2 className="size-3.5" />
        </button>
      </div>

      <svg
        ref={svgRef}
        className="h-full w-full touch-none"
        viewBox={`0 0 ${GRAPH_WIDTH} ${GRAPH_HEIGHT}`}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={() => setDragState(null)}
        onPointerCancel={() => setDragState(null)}
        onWheel={handleWheel}
      >
        <rect width={GRAPH_WIDTH} height={GRAPH_HEIGHT} fill="#FFFFFF" />
        <g transform={`translate(${pan.x} ${pan.y}) scale(${zoom})`}>
          {graph.links.map((link) => {
            const isSelectedIncident =
              selectedNodeId &&
              (link.sourceNode.id === selectedNodeId ||
                link.targetNode.id === selectedNodeId);
            const isDimmed = Boolean(selectedNodeId && !isSelectedIncident);
            const endpoints = evidenceMapLinkEndpoints(link);
            return (
              <line
                key={link.id}
                x1={endpoints.x1}
                y1={endpoints.y1}
                x2={endpoints.x2}
                y2={endpoints.y2}
                stroke={edgeStroke(link.kind)}
                strokeDasharray={
                  link.kind === "has_terminology_context" ? "4 4" : undefined
                }
                strokeOpacity={isDimmed ? 0.18 : 0.78}
                strokeWidth={isSelectedIncident ? 2 : 1.15}
              />
            );
          })}

          {graph.nodes.map((node) => {
            const style = evidenceNodeStyle(node);
            const isSelected = selectedNodeId === node.id;
            const isDimmed = Boolean(
              selectedRelatedIds && !selectedRelatedIds.has(node.id)
            );
            const showLabel =
              node.kind === "resolved_medication" || node.kind === "question";
            return (
              <g
                key={node.id}
                className="cursor-pointer"
                opacity={isDimmed ? 0.25 : 1}
                onClick={(event: MouseEvent<SVGGElement>) => {
                  event.stopPropagation();
                  setSelectedNodeId((current) =>
                    current === node.id ? null : node.id
                  );
                }}
                onMouseEnter={() =>
                  setHoverTooltip({
                    x: node.x,
                    y: node.y,
                    title:
                      node.kind === "resolved_medication"
                        ? displayGraphNodeName(node.label)
                        : node.label,
                    body: nodeTooltipBody(node),
                  })
                }
                onMouseLeave={() => setHoverTooltip(null)}
              >
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={style.radius}
                  fill={style.fill}
                  stroke={isSelected ? "#371E8F" : style.stroke}
                  strokeDasharray={isSelected ? "3 2" : undefined}
                  strokeWidth={isSelected ? 2.2 : 1.4}
                />
                {showLabel ? (
                  <text
                    x={node.x}
                    y={node.y + style.radius + 13}
                    textAnchor="middle"
                    className="pointer-events-none fill-slate-900 text-[10px] font-semibold"
                  >
                    {shortLabel(
                      node.kind === "resolved_medication"
                        ? displayGraphNodeName(node.label)
                        : node.label,
                      18
                    )}
                  </text>
                ) : null}
              </g>
            );
          })}
        </g>
      </svg>

      {hoverTooltip ? (
        <div
          className="pointer-events-none absolute z-20 max-w-xs rounded-md border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 shadow-lg"
          style={{
            left: `${Math.min(760, Math.max(14, hoverTooltip.x + pan.x + 18))}px`,
            top: `${Math.min(470, Math.max(48, hoverTooltip.y + pan.y + 18))}px`,
          }}
        >
          <div className="font-semibold text-slate-950">{hoverTooltip.title}</div>
          {hoverTooltip.body ? (
            <div className="mt-1 whitespace-pre-line leading-5">
              {hoverTooltip.body}
            </div>
          ) : null}
        </div>
      ) : null}

      {selectedNode ? (
        <EvidenceMapDetailPanel
          node={selectedNode}
          onCitationClick={onCitationClick}
          onRxcuiClick={onRxcuiClick}
        />
      ) : null}
    </div>
  );
}

function buildD3EvidenceGraph(map: QuestionEvidenceMap) {
  const nodes: VisualNode[] = map.nodes.map((node) => {
    const anchor = evidenceMapAnchor(node.kind);
    return {
      ...node,
      x: anchor.x + evidenceMapSeedOffset(node.id, "x"),
      y: anchor.y + evidenceMapSeedOffset(node.id, "y"),
    };
  });
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const simulationLinks = map.edges
    .filter((edge) => nodeById.has(edge.source) && nodeById.has(edge.target))
    .map((edge) => ({ source: edge.source, target: edge.target, kind: edge.kind }));

  const simulation = forceSimulation(nodes)
    .force(
      "link",
      forceLink<VisualNode, { source: string | VisualNode; target: string | VisualNode; kind: string }>(
        simulationLinks
      )
        .id((node) => node.id)
        .distance((link) => evidenceMapLinkDistance(link.kind))
        .strength(0.44)
    )
    .force("charge", forceManyBody().strength(-120))
    .force(
      "collide",
      forceCollide<VisualNode>((node) => evidenceNodeStyle(node).radius + 8)
    )
    .force("center", forceCenter(GRAPH_WIDTH / 2, GRAPH_HEIGHT / 2))
    .force("x", forceX<VisualNode>((node) => evidenceMapAnchor(node.kind).x).strength(0.09))
    .force("y", forceY<VisualNode>((node) => evidenceMapAnchor(node.kind).y).strength(0.09))
    .stop();

  for (let index = 0; index < 220; index += 1) {
    simulation.tick();
  }

  const links: VisualLink[] = map.edges
    .map((edge) => {
      const sourceNode = nodeById.get(edge.source);
      const targetNode = nodeById.get(edge.target);
      if (!sourceNode || !targetNode) {
        return null;
      }
      return { ...edge, sourceNode, targetNode };
    })
    .filter((link): link is VisualLink => Boolean(link));

  return { nodes, links };
}

function evidenceMapAnchor(kind: string) {
  const anchors: Record<string, { x: number; y: number }> = {
    question: { x: GRAPH_WIDTH * 0.18, y: GRAPH_HEIGHT * 0.5 },
    query_concept: { x: GRAPH_WIDTH * 0.35, y: GRAPH_HEIGHT * 0.5 },
    resolved_medication: { x: GRAPH_WIDTH * 0.48, y: GRAPH_HEIGHT * 0.42 },
    label_source: { x: GRAPH_WIDTH * 0.66, y: GRAPH_HEIGHT * 0.5 },
    label_section: { x: GRAPH_WIDTH * 0.82, y: GRAPH_HEIGHT * 0.5 },
    rxnorm_context: { x: GRAPH_WIDTH * 0.52, y: GRAPH_HEIGHT * 0.72 },
  };
  return anchors[kind] ?? { x: GRAPH_WIDTH * 0.5, y: GRAPH_HEIGHT * 0.5 };
}

function evidenceMapLinkDistance(kind: string) {
  const distances: Record<string, number> = {
    resolved_as: 90,
    has_role: 100,
    has_label_source: 76,
    has_label_section: 36,
    mentions_in_interaction_section: 70,
    has_terminology_context: 110,
  };
  return distances[kind] ?? 80;
}

function evidenceMapSeedOffset(id: string, axis: "x" | "y") {
  const seed = Array.from(id).reduce(
    (total, character) => total + character.charCodeAt(0),
    axis === "x" ? 19 : 47
  );
  return (seed % 80) - 40;
}

function evidenceMapLinkEndpoints(link: VisualLink) {
  const sourceRadius = evidenceNodeStyle(link.sourceNode).radius;
  const targetRadius = evidenceNodeStyle(link.targetNode).radius;
  const dx = link.targetNode.x - link.sourceNode.x;
  const dy = link.targetNode.y - link.sourceNode.y;
  const distance = Math.sqrt(dx * dx + dy * dy) || 1;
  return {
    x1: link.sourceNode.x + (dx / distance) * sourceRadius,
    y1: link.sourceNode.y + (dy / distance) * sourceRadius,
    x2: link.targetNode.x - (dx / distance) * targetRadius,
    y2: link.targetNode.y - (dy / distance) * targetRadius,
  };
}

function evidenceNodeStyle(node: QuestionEvidenceMapNode) {
  return nodeStyles[node.kind] ?? nodeStyles.query_concept;
}

function edgeStroke(kind: string) {
  if (kind === "mentions_in_interaction_section") {
    return "#371E8F";
  }
  if (kind === "has_terminology_context") {
    return "#D97706";
  }
  return "#94A3B8";
}

function nodeTooltipBody(node: QuestionEvidenceMapNode) {
  const lines = [evidenceNodeStyle(node).label];
  if (node.role) {
    lines.push(displayMentionRole(node.role));
  }
  if (node.rxcui) {
    lines.push(`RXCUI ${node.rxcui}`);
  }
  if (node.section) {
    lines.push(displaySectionName(node.section));
  }
  if (node.subtitle) {
    lines.push(node.subtitle);
  }
  return lines.join("\n");
}

function EvidenceMapLegend() {
  const items = Object.entries(nodeStyles).map(([kind, style]) => ({
    kind,
    ...style,
  }));

  return (
    <div className="pointer-events-none absolute left-3 top-3 z-10 flex max-w-[680px] flex-wrap gap-2 rounded-md border border-slate-200 bg-white/90 px-2 py-1.5 shadow-sm backdrop-blur">
      {items.map((item) => (
        <div key={item.kind} className="flex items-center gap-1.5">
          <span
            className="size-2.5 rounded-full border"
            style={{ backgroundColor: item.fill, borderColor: item.stroke }}
          />
          <span className="text-[10px] font-medium uppercase text-slate-500">
            {item.label}
          </span>
        </div>
      ))}
    </div>
  );
}

function EvidenceMapDetailPanel({
  node,
  onCitationClick,
  onRxcuiClick,
}: {
  node: QuestionEvidenceMapNode;
  onCitationClick: (citation: EvidenceCitation) => void;
  onRxcuiClick: (target: EvidenceMapNavigationTarget) => void;
}) {
  const canJumpToEvidence = Boolean(node.source_id && node.section);
  const canJumpToMedication = Boolean(node.rxcui);

  return (
    <aside className="absolute bottom-4 right-4 z-10 max-h-[410px] w-[300px] overflow-auto rounded-md border border-slate-200 bg-white/95 p-4 shadow-lg backdrop-blur">
      <div className="text-xs font-medium uppercase text-slate-500">
        Selected map item
      </div>
      <div className="mt-3 space-y-3">
        <div>
          <div className="flex flex-wrap gap-1.5">
            <Badge className="border-slate-200 bg-white text-slate-700">
              {displayEvidenceMapNodeKind(node)}
            </Badge>
            {node.tags.includes("interaction_targeted_lookup") ? (
              <Badge className="border-slate-300 bg-slate-100 text-slate-700">
                Interaction-specific
              </Badge>
            ) : null}
          </div>
          <div className="mt-3 text-base font-semibold leading-6 text-slate-950">
            {node.kind === "resolved_medication"
              ? displayGraphNodeName(node.label)
              : node.label}
          </div>
          {node.subtitle ? (
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {node.subtitle}
            </p>
          ) : null}
        </div>

        <div className="space-y-1 text-sm leading-6 text-slate-600">
          {node.rxcui ? <div>RXCUI {node.rxcui}</div> : null}
          {node.section ? (
            <div>Section {displaySectionName(node.section)}</div>
          ) : null}
        </div>

        {canJumpToEvidence || canJumpToMedication ? (
          <Button
            type="button"
            className="px-3 py-1.5 text-xs"
            onClick={() => {
              if (node.source_id && node.section) {
                onCitationClick({
                  source_id: node.source_id,
                  section: node.section,
                });
                return;
              }
              if (node.rxcui) {
                onRxcuiClick({ rxcui: node.rxcui });
              }
            }}
          >
            Open supporting evidence
          </Button>
        ) : null}
      </div>
    </aside>
  );
}

function displayEvidenceMapNodeKind(node: QuestionEvidenceMapNode) {
  if (node.role) {
    return displayMentionRole(node.role);
  }
  return evidenceNodeStyle(node).label;
}

function displayMentionRole(value: string) {
  const labels: Record<string, string> = {
    primary_drug: "Primary medication",
    current_medication: "Current medication",
    mentioned_drug: "Mentioned medication",
    allergy: "Allergy",
  };
  return labels[value] ?? sentenceCase(value.replaceAll("_", " "));
}

function displayGraphNodeName(name: string) {
  return name.toUpperCase();
}

function displaySectionName(section: string) {
  return sectionLabels[section] ?? section.replaceAll("_", " ");
}

function sentenceCase(value: string) {
  return value
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function shortLabel(value: string, maxLength = 24) {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength - 3)}...`;
}
