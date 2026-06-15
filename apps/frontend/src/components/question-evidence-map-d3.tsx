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
import type { Force, Simulation, SimulationNodeDatum } from "d3-force";
import { Info, Maximize2, Minus, Plus } from "lucide-react";
import type { MouseEvent, PointerEvent, WheelEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  EvidenceCitation,
  QuestionEvidenceMap,
  QuestionEvidenceMapEdge,
  QuestionEvidenceMapNode,
} from "@/lib/types";

export type EvidenceMapNavigationTarget = {
  rxcui: string;
};

const GRAPH_WIDTH = 900;
const GRAPH_HEIGHT = 520;
const MIN_ZOOM = 0.28;
const MAX_ZOOM = 2;
const FOCUS_ZOOM = 1.55;
const FIT_PADDING = 0;
const CONCEPT_SPREAD_DISTANCE = 160;
const CONCEPT_SPREAD_STRENGTH = 0.55;
const CONCEPT_SPREAD_MAX_PUSH = 8;
const CONCEPT_LABEL_REPULSION_DISTANCE = 140;
const CONCEPT_LABEL_REPULSION_STRENGTH = 0.5;
const MEDICATION_SPREAD_DISTANCE = 420;
const MEDICATION_SPREAD_STRENGTH = 0.72;
const MEDICATION_SPREAD_MAX_PUSH = 14;
const CONCEPT_RING_RADIUS = 118;
const MEDICATION_RING_RADIUS = 310;
const HIERARCHY_RING_STRENGTH = 0.22;
const INITIAL_LAYOUT_TICKS = 160;

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

const edgeRelationshipLabels: Record<string, string> = {
  has_role: "Question extraction",
  resolved_as: "RxNorm resolution",
  has_label_source: "Label source retrieval",
  interaction_lookup_source: "Interaction-specific lookup",
  has_label_section: "Label section retrieval",
  mentions_in_interaction_section: "Interaction-text evidence",
  has_terminology_context: "RxNorm terminology context",
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
    label: "Drug label",
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
  // Hidden from the evidence-map UI for now; kept here in case we reintroduce
  // terminology context as a clearer visual layer later.
  rxnorm_context: {
    label: "Terminology context",
    fill: "#FEF3C7",
    stroke: "#D97706",
    radius: 12,
  },
};

const evidenceNodeTypeOrder = [
  "question",
  "query_concept",
  "resolved_medication",
  "label_source",
  "label_section",
  "rxnorm_context",
];

const evidenceMapRoleTags = new Set([
  "primary_drug",
  "current_medication",
  "mentioned_drug",
  "allergy",
  "condition",
  "patient_context",
]);

const rxNormTypeLabels: Record<string, string> = {
  IN: "Ingredient",
  PIN: "Precise Ingredient",
  MIN: "Multiple Ingredients",
  BN: "Brand Name",
  SCDC: "Semantic Clinical Drug Component",
  SCDF: "Semantic Clinical Drug Form",
  SCDFP: "Semantic Clinical Drug Form Precise",
  SCDG: "Semantic Clinical Drug Group",
  SCDGP: "Semantic Clinical Drug Form Group Precise",
  SCD: "Semantic Clinical Drug",
  GPCK: "Generic Pack",
  SBDC: "Semantic Branded Drug Component",
  SBDF: "Semantic Branded Drug Form",
  SBDFP: "Semantic Branded Drug Form Precise",
  SBDG: "Semantic Branded Drug Group",
  SBD: "Semantic Branded Drug",
  BPCK: "Brand Name Pack",
  DF: "Dose Form",
  DFG: "Dose Form Group",
  PSN: "Prescribable Name",
  SY: "Synonym",
  TMSY: "Tall Man Lettering Synonym",
};

type EvidenceMapD3Props = {
  map: QuestionEvidenceMap;
  onCitationClick: (citation: EvidenceCitation) => void;
  onRxcuiClick: (target: EvidenceMapNavigationTarget) => void;
};

type VisualNode = QuestionEvidenceMapNode &
  SimulationNodeDatum & {
  x: number;
  y: number;
  hierarchyAngle: number | null;
  labelSectionCount: number;
  medicationIndex: number;
  medicationCount: number;
  medicationParentCount: number;
};

type SimulationLink = {
  source: string | VisualNode;
  target: string | VisualNode;
  kind: string;
  hasParallelInteractionLookup: boolean;
  sourceNode: VisualNode;
  targetNode: VisualNode;
};

type VisualLink = QuestionEvidenceMapEdge & {
  hasParallelInteractionLookup: boolean;
  sourceNode: VisualNode;
  targetNode: VisualNode;
};

type HoverTooltip = {
  x: number;
  y: number;
  title?: string | React.ReactNode;
  body?: string | React.ReactNode;
};

function InfoTooltip({ text }: { text: string }) {
  return (
    <span className="group relative inline-flex">
      <Info className="size-3.5 text-slate-400" />
      <span className="pointer-events-none absolute left-0 top-full z-20 mt-2 hidden w-72 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs normal-case leading-5 text-slate-700 shadow-lg group-hover:block">
        {text}
      </span>
    </span>
  );
}

export function EvidenceMapD3({
  map,
  onCitationClick,
  onRxcuiClick,
}: EvidenceMapD3Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const graphFrameRef = useRef<HTMLDivElement>(null);
  const suppressNodeClickRef = useRef(false);
  const simulationRef = useRef<Simulation<VisualNode, SimulationLink> | null>(
    null
  );
  const latestNodesRef = useRef<VisualNode[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [hoverTooltip, setHoverTooltip] = useState<HoverTooltip | null>(null);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set());
  const [simulationNodes, setSimulationNodes] = useState<VisualNode[]>([]);
  const [dragState, setDragState] = useState<{
    startClientX: number;
    startClientY: number;
    startPanX: number;
    startPanY: number;
    moved: boolean;
  } | null>(null);
  const [nodeDrag, setNodeDrag] = useState<{
    id: string;
    moved: boolean;
    startClientX: number;
    startClientY: number;
  } | null>(null);

  const visibleMap = useMemo(() => withoutTerminologyContext(map), [map]);
  const graph = useMemo(() => buildD3EvidenceGraph(visibleMap), [visibleMap]);
  const positionedNodes = simulationNodes.length ? simulationNodes : graph.nodes;
  const positionedNodeById = useMemo(
    () => new Map(positionedNodes.map((node) => [node.id, node])),
    [positionedNodes]
  );
  const filteredNodes = useMemo(() => {
    if (selectedTypes.size === 0) {
      return positionedNodes;
    }
    return positionedNodes.filter(
      (node) =>
        node.id === selectedNodeId ||
        node.kind === "question" ||
        selectedTypes.has(node.kind)
    );
  }, [positionedNodes, selectedNodeId, selectedTypes]);
  const filteredNodeIds = useMemo(
    () => new Set(filteredNodes.map((node) => node.id)),
    [filteredNodes]
  );
  const filteredLinks = useMemo(() => {
    const links: VisualLink[] = [];
    for (const link of graph.links) {
      const sourceNode = positionedNodeById.get(link.sourceNode.id);
      const targetNode = positionedNodeById.get(link.targetNode.id);
      if (
        sourceNode &&
        targetNode &&
        filteredNodeIds.has(sourceNode.id) &&
        filteredNodeIds.has(targetNode.id)
      ) {
        links.push({ ...link, sourceNode, targetNode });
      }
    }
    return links;
  }, [filteredNodeIds, graph.links, positionedNodeById]);
  const selectedNode =
    positionedNodes.find((node) => node.id === selectedNodeId) ?? null;
  const visibleNodeTypes = useMemo(() => {
    return Array.from(new Set(graph.nodes.map((node) => node.kind))).sort(
      (left, right) =>
        nodeTypeSortIndex(left) - nodeTypeSortIndex(right) ||
        evidenceNodeStyle(left).label.localeCompare(evidenceNodeStyle(right).label)
    );
  }, [graph.nodes]);
  const selectedRelatedIds = useMemo(() => {
    if (!selectedNodeId) {
      return null;
    }
    return new Set([
      selectedNodeId,
      ...filteredLinks
        .filter(
          (link) =>
            link.sourceNode.id === selectedNodeId ||
            link.targetNode.id === selectedNodeId
        )
        .flatMap((link) => [link.sourceNode.id, link.targetNode.id]),
    ]);
  }, [filteredLinks, selectedNodeId]);
  const selectedNodeCitation = useMemo(
    () => selectedNode ? citationForEvidenceMapNode(selectedNode, graph.links) : null,
    [graph.links, selectedNode]
  );

  useEffect(() => {
    const nodes = graph.nodes.map((node) => ({ ...node }));
    latestNodesRef.current = nodes;

    const simulationLinks = graph.links.map((link) => ({
      source: link.sourceNode.id,
      target: link.targetNode.id,
      kind: link.kind,
      hasParallelInteractionLookup: link.hasParallelInteractionLookup,
      sourceNode:
        nodes.find((node) => node.id === link.sourceNode.id) ?? link.sourceNode,
      targetNode:
        nodes.find((node) => node.id === link.targetNode.id) ?? link.targetNode,
    }));

    let animationFrame: number | null = null;
    const simulation = createEvidenceMapSimulation(nodes, simulationLinks);
    simulation.stop();
    for (let tick = 0; tick < INITIAL_LAYOUT_TICKS; tick += 1) {
      simulation.tick();
    }

    latestNodesRef.current = nodes;
    setSimulationNodes([...nodes]);
    const fittedView = fitGraphToView(nodes);
    setPan(fittedView.pan);
    setZoom(fittedView.zoom);

    simulation
      .on("tick", () => {
        latestNodesRef.current = nodes;
        if (animationFrame !== null) {
          return;
        }
        animationFrame = window.requestAnimationFrame(() => {
          setSimulationNodes([...nodes]);
          animationFrame = null;
        });
      })
      .alpha(0.42)
      .restart();

    simulationRef.current = simulation;

    return () => {
      simulation.stop();
      simulationRef.current = null;
      if (animationFrame !== null) {
        window.cancelAnimationFrame(animationFrame);
      }
    };
  }, [graph]);

  function updateZoom(nextZoom: number) {
    setZoom(Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, nextZoom)));
  }

  function handleWheel(event: WheelEvent<SVGSVGElement>) {
    event.preventDefault();
    const svg = svgRef.current;
    if (!svg) {
      updateZoom(zoom + (event.deltaY < 0 ? 0.08 : -0.08));
      return;
    }
    const bounds = svg.getBoundingClientRect();
    const viewX = ((event.clientX - bounds.left) / bounds.width) * GRAPH_WIDTH;
    const viewY = ((event.clientY - bounds.top) / bounds.height) * GRAPH_HEIGHT;
    const graphX = (viewX - pan.x) / zoom;
    const graphY = (viewY - pan.y) / zoom;
    const nextZoom = Math.min(
      MAX_ZOOM,
      Math.max(MIN_ZOOM, zoom * (event.deltaY > 0 ? 0.9 : 1.1))
    );
    setZoom(nextZoom);
    setPan({
      x: viewX - graphX * nextZoom,
      y: viewY - graphY * nextZoom,
    });
  }

  function handlePointerDown(event: PointerEvent<SVGSVGElement>) {
    if (
      event.target !== svgRef.current &&
      !(event.target instanceof SVGRectElement)
    ) {
      return;
    }
    setDragState({
      startClientX: event.clientX,
      startClientY: event.clientY,
      startPanX: pan.x,
      startPanY: pan.y,
      moved: false,
    });
  }

  function handlePointerMove(event: PointerEvent<SVGSVGElement>) {
    if (nodeDrag) {
      const point = screenToGraph(event.clientX, event.clientY);
      const simulationNode = latestNodesRef.current.find(
        (node) => node.id === nodeDrag.id
      );
      if (simulationNode) {
        simulationNode.fx = point.x;
        simulationNode.fy = point.y;
        simulationRef.current?.alphaTarget(0.3).restart();
      }
      const hasMoved =
        nodeDrag.moved ||
        Math.hypot(
          event.clientX - nodeDrag.startClientX,
          event.clientY - nodeDrag.startClientY
        ) > 4;
      if (hasMoved && !nodeDrag.moved) {
        setNodeDrag({ ...nodeDrag, moved: true });
      }
      return;
    }
    if (!dragState) {
      return;
    }
    const svg = svgRef.current;
    if (!svg) {
      return;
    }
    const bounds = svg.getBoundingClientRect();
    const scaleX = GRAPH_WIDTH / bounds.width;
    const scaleY = GRAPH_HEIGHT / bounds.height;
    const deltaX = event.clientX - dragState.startClientX;
    const deltaY = event.clientY - dragState.startClientY;
    setPan({
      x: dragState.startPanX + deltaX * scaleX,
      y: dragState.startPanY + deltaY * scaleY,
    });
    if (!dragState.moved && Math.hypot(deltaX, deltaY) > 4) {
      setDragState({ ...dragState, moved: true });
    }
  }

  function handlePointerUp() {
    if (dragState && !dragState.moved && !nodeDrag) {
      setSelectedNodeId(null);
    }
    if (nodeDrag?.moved) {
      suppressNodeClickRef.current = true;
    }
    if (nodeDrag) {
      const simulationNode = latestNodesRef.current.find(
        (node) => node.id === nodeDrag.id
      );
      if (simulationNode) {
        simulationNode.fx = null;
        simulationNode.fy = null;
      }
      simulationRef.current?.alphaTarget(0);
    }
    setDragState(null);
    setNodeDrag(null);
  }

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

  function resetView() {
    const fittedView = fitGraphToView(positionedNodes);
    setPan(fittedView.pan);
    setZoom(fittedView.zoom);
  }

  function focusNode(nodeId: string) {
    const node = positionedNodes.find((n) => n.id === nodeId);
    if (!node) {
      return;
    }
    setSelectedNodeId(nodeId);
    setZoom(FOCUS_ZOOM);
    setPan({
      x: GRAPH_WIDTH / 2 - node.x * FOCUS_ZOOM,
      y: GRAPH_HEIGHT / 2 - node.y * FOCUS_ZOOM,
    });
  }

  function toggleNodeType(kind: string) {
    setSelectedTypes((current) => {
      const next = new Set(current);
      if (next.has(kind)) {
        next.delete(kind);
      } else {
        next.add(kind);
      }
      return next;
    });
  }

  function updateTooltip(
    event: MouseEvent<SVGElement>,
    content: { title?: string | React.ReactNode; body?: string | React.ReactNode }
  ) {
    const frame = graphFrameRef.current;
    if (!frame) {
      return;
    }
    const bounds = frame.getBoundingClientRect();
    const rawX = event.clientX - bounds.left + 14;
    const rawY = event.clientY - bounds.top + 14;
    const maxX = Math.max(12, bounds.width - 300);
    const maxY = Math.max(12, bounds.height - 120);
    setHoverTooltip({
      ...content,
      x: clamp(rawX, 12, maxX),
      y: clamp(rawY, 12, maxY),
    });
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <CardTitle>Evidence Map</CardTitle>
          <InfoTooltip text="This map connects extracted question concepts, RxNorm medication resolution, public FDA label sources, and retrieved label sections. Interaction-specific edges show retrieval paths, not clinical interaction claims." />
        </div>
        <p className="mt-1 text-sm leading-6 text-slate-500">
          Follow how the question is translated into medication concepts and linked
          to the retrieved public label evidence.
        </p>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
      <div
        ref={graphFrameRef}
        className="relative h-[560px] overflow-hidden rounded-md border border-slate-200 bg-white"
      >
        <svg
          ref={svgRef}
          className="h-full w-full touch-none"
          viewBox={`0 0 ${GRAPH_WIDTH} ${GRAPH_HEIGHT}`}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
          onPointerLeave={handlePointerUp}
          onWheel={handleWheel}
        >
          <rect width={GRAPH_WIDTH} height={GRAPH_HEIGHT} fill="#FFFFFF" />
          <g transform={`translate(${pan.x} ${pan.y}) scale(${zoom})`}>
            {filteredLinks.map((link) => {
              const isSelectedIncident =
                selectedNodeId &&
                (link.sourceNode.id === selectedNodeId ||
                  link.targetNode.id === selectedNodeId);
              const isDimmed = Boolean(selectedNodeId && !isSelectedIncident);
              const endpoints = evidenceMapLinkEndpoints(link);
              const tooltipText = edgeTooltipContent(link);
              return (
                <g key={link.id}>
                  <line
                    x1={endpoints.x1}
                    y1={endpoints.y1}
                    x2={endpoints.x2}
                    y2={endpoints.y2}
                    stroke="transparent"
                    strokeWidth="10"
                    className="cursor-default"
                    onMouseEnter={(event) => updateTooltip(event, tooltipText)}
                    onMouseMove={(event) => updateTooltip(event, tooltipText)}
                    onMouseLeave={() => setHoverTooltip(null)}
                  />
                  <line
                    x1={endpoints.x1}
                    y1={endpoints.y1}
                    x2={endpoints.x2}
                    y2={endpoints.y2}
                    stroke={edgeStroke(link.kind)}
                    strokeDasharray={edgeDashArray(link.kind)}
                    strokeOpacity={isDimmed ? 0.18 : 0.78}
                    strokeWidth={isSelectedIncident ? 2 : 1.15}
                    pointerEvents="none"
                  />
                </g>
              );
            })}

            {filteredNodes.map((node) => {
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
                    if (suppressNodeClickRef.current) {
                      suppressNodeClickRef.current = false;
                      return;
                    }
                    setSelectedNodeId((current) =>
                      current === node.id ? null : node.id
                    );
                  }}
                  onDoubleClick={(event: MouseEvent<SVGGElement>) => {
                    event.stopPropagation();
                    focusNode(node.id);
                  }}
                  onPointerDown={(event) => {
                    event.stopPropagation();
                    const simulationNode = latestNodesRef.current.find(
                      (candidate) => candidate.id === node.id
                    );
                    if (simulationNode) {
                      simulationNode.fx = simulationNode.x;
                      simulationNode.fy = simulationNode.y;
                    }
                    simulationRef.current?.alphaTarget(0.3).restart();
                    setNodeDrag({
                      id: node.id,
                      moved: false,
                      startClientX: event.clientX,
                      startClientY: event.clientY,
                    });
                  }}
                  onMouseEnter={(event: MouseEvent<SVGGElement>) => {
                    event.stopPropagation();
                    updateTooltip(event, {
                      title:
                        node.kind === "resolved_medication"
                          ? displayGraphNodeName(node.label)
                          : node.label,
                      body: nodeTooltipBody(node),
                    });
                  }}
                  onMouseLeave={() => setHoverTooltip(null)}
                >
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={style.radius}
                    fill={style.fill}
                    stroke={isSelected ? "#371E8F" : style.stroke}
                    strokeDasharray={
                      isSelected
                        ? "3 2"
                        : node.kind === "label_source" &&
                            node.tags.includes("interaction_targeted_lookup")
                          ? "4 3"
                          : undefined
                    }
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
              left: `${hoverTooltip.x}px`,
              top: `${hoverTooltip.y}px`,
            }}
          >
            {hoverTooltip.title ? (
              <div className="font-semibold text-slate-950">
                {hoverTooltip.title}
              </div>
            ) : null}
            {hoverTooltip.body ? (
              <div className={hoverTooltip.title ? "mt-1 whitespace-pre-line leading-5" : "leading-5"}>
                {hoverTooltip.body}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      <EvidenceMapSidePanel
        filteredLinkCount={filteredLinks.length}
        filteredNodeCount={filteredNodes.length}
        nodeTypes={visibleNodeTypes}
        onClearTypes={() => setSelectedTypes(new Set())}
        onResetView={resetView}
        onSelectType={toggleNodeType}
        onZoomIn={() => updateZoom(zoom + 0.12)}
        onZoomOut={() => updateZoom(zoom - 0.12)}
        selectedNodeCitation={selectedNodeCitation}
        selectedNode={selectedNode}
        selectedTypes={selectedTypes}
        totalLinkCount={graph.links.length}
        totalNodeCount={graph.nodes.length}
        onCitationClick={onCitationClick}
        onRxcuiClick={onRxcuiClick}
      />
        </div>
      </CardContent>
    </Card>
  );
}

function EvidenceMapSidePanel({
  filteredLinkCount,
  filteredNodeCount,
  nodeTypes,
  onClearTypes,
  onCitationClick,
  onResetView,
  onRxcuiClick,
  onSelectType,
  onZoomIn,
  onZoomOut,
  selectedNodeCitation,
  selectedNode,
  selectedTypes,
  totalLinkCount,
  totalNodeCount,
}: {
  filteredLinkCount: number;
  filteredNodeCount: number;
  nodeTypes: string[];
  onClearTypes: () => void;
  onCitationClick: (citation: EvidenceCitation) => void;
  onResetView: () => void;
  onRxcuiClick: (target: EvidenceMapNavigationTarget) => void;
  onSelectType: (kind: string) => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  selectedNodeCitation: EvidenceCitation | null;
  selectedNode: VisualNode | null;
  selectedTypes: Set<string>;
  totalLinkCount: number;
  totalNodeCount: number;
}) {
  return (
    <aside className="space-y-3">
      <div className="rounded-md border border-slate-200 bg-white p-3">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div className="text-xs font-medium uppercase text-slate-500">
            Graph controls
          </div>
          <div className="flex gap-1">
            <button
              type="button"
              onClick={onZoomOut}
              className="grid size-8 place-items-center rounded-md border border-slate-200 text-slate-700 hover:bg-slate-50"
              title="Zoom out"
            >
              <Minus className="size-4" />
            </button>
            <button
              type="button"
              onClick={onResetView}
              className="grid size-8 place-items-center rounded-md border border-slate-200 text-slate-700 hover:bg-slate-50"
              title="Reset view"
            >
              <Maximize2 className="size-4" />
            </button>
            <button
              type="button"
              onClick={onZoomIn}
              className="grid size-8 place-items-center rounded-md border border-slate-200 text-slate-700 hover:bg-slate-50"
              title="Zoom in"
            >
              <Plus className="size-4" />
            </button>
          </div>
        </div>
      </div>

      <div className="h-40 rounded-md border border-slate-200 bg-slate-50 p-3">
        <div className="mb-2 text-xs font-medium uppercase text-slate-500">
          Selected node
        </div>
        {selectedNode ? (
          <div className="grid h-[112px] grid-rows-[48px_24px_24px] gap-2">
            <div>
              <div className="flex flex-wrap gap-1.5">
                <Badge className="border-slate-200 bg-white text-slate-700">
                  {displayEvidenceMapNodeKind(selectedNode)}
                </Badge>
                {selectedNode.tags.includes("interaction_targeted_lookup") ? (
                  <Badge className="border-slate-300 bg-slate-100 text-slate-700">
                    Interaction-specific
                  </Badge>
                ) : null}
              </div>
              <div className="mt-2 line-clamp-2 font-semibold leading-6 text-slate-950">
                {selectedNode.kind === "resolved_medication"
                  ? displayGraphNodeName(selectedNode.label)
                  : selectedNode.label}
              </div>
            </div>

            <div className="flex min-w-0 gap-2 overflow-hidden">
              {selectedNode.rxcui ? (
                <Badge className="max-w-[56%] shrink-0 truncate overflow-hidden">
                  RXCUI {selectedNode.rxcui}
                </Badge>
              ) : null}
              {selectedNode.label_rxcuis?.length ? (
                <Badge
                  className="min-w-0 truncate"
                  title={`OpenFDA label RXCUIs: ${selectedNode.label_rxcuis.join(", ")}`}
                >
                  Label RXCUIs {formatList(selectedNode.label_rxcuis)}
                </Badge>
              ) : null}
              {selectedNode.section ? (
                <Badge className="min-w-0 truncate">
                  {displaySectionName(selectedNode.section)}
                </Badge>
              ) : null}
            </div>

            {selectedNodeCitation ? (
              <Badge
                className="w-fit cursor-pointer !border-[#371E8F] !bg-[#371E8F] !text-white hover:!bg-[#371E8F]"
                onClick={() => onCitationClick(selectedNodeCitation)}
                title="Show in supporting evidence"
              >
                Show in supporting evidence
              </Badge>
            ) : selectedNode.rxcui ? (
              <Badge
                className="w-fit cursor-pointer !border-[#371E8F] !bg-[#371E8F] !text-white hover:!bg-[#371E8F]"
                onClick={() =>
                  onRxcuiClick({ rxcui: selectedNode.rxcui as string })
                }
                title="Show in supporting evidence"
              >
                Show in supporting evidence
              </Badge>
            ) : null}
          </div>
        ) : (
          <div className="grid h-[112px] grid-rows-[48px_24px] gap-2">
            <p className="min-h-12 text-sm leading-6 text-slate-600">
              Select a bubble to inspect it. Double-click a bubble to zoom in on it in the graph.
            </p>
          </div>
        )}
      </div>

      <div className="rounded-md border border-slate-200 bg-white p-3">
        <div className="flex items-center justify-between gap-3">
          <div className="text-xs font-medium uppercase text-slate-500">
            Node types
          </div>
          <button
            type="button"
            className={[
              "w-10 text-right font-medium transition",
              selectedTypes.size > 0
                ? "text-slate-600 hover:text-slate-950"
                : "pointer-events-none text-transparent",
            ].join(" ")}
            style={{ fontSize: "12px", lineHeight: "14px" }}
            onClick={onClearTypes}
          >
            Clear
          </button>
        </div>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
          {nodeTypes.map((kind) => {
            const style = evidenceNodeStyle(kind);
            const isActive = selectedTypes.has(kind);
            return (
              <button
                key={kind}
                type="button"
                className={[
                  "flex min-w-0 items-center gap-2 rounded-md border px-2 py-1 text-left transition",
                  isActive
                    ? "border-slate-400 bg-slate-100 text-slate-950"
                    : "border-transparent text-slate-700 hover:border-slate-200 hover:bg-slate-50",
                ].join(" ")}
                style={{ fontSize: "12px", lineHeight: "13px" }}
                onClick={() => onSelectType(kind)}
              >
                <span
                  className="size-3 shrink-0 rounded-full border"
                  style={{
                    backgroundColor: style.fill,
                    borderColor: style.stroke,
                  }}
                />
                <span className="truncate">{style.label}</span>
              </button>
            );
          })}
          <div
            className="flex min-w-0 items-center gap-2 rounded-md px-2 py-1 text-left text-slate-700"
            style={{ fontSize: "12px", lineHeight: "13px" }}
          >
            <span className="flex h-3 w-3 shrink-0 items-center">
              <span className="w-3 border-t border-dashed border-[#371E8F]" />
            </span>
            <span className="truncate">Interaction-specific</span>
          </div>
        </div>
      </div>
      <p className="px-1 text-xs leading-5 text-slate-500">
        Showing {filteredNodeCount} of {totalNodeCount} nodes and{" "}
        {filteredLinkCount} of {totalLinkCount} links. Hover over a line to see
        the relationship. Double click a node to focus it.
      </p>
    </aside>
  );
}

function buildD3EvidenceGraph(map: QuestionEvidenceMap) {
  const hierarchyAnglesById = buildHierarchyAngles(map);
  const medicationIds = map.nodes
    .filter((candidate) => candidate.kind === "resolved_medication")
    .map((candidate) => candidate.id);
  const nodes: VisualNode[] = map.nodes.map((node, index) => {
    const hierarchyAngle = hierarchyAnglesById.get(node.id) ?? null;
    const medicationIndex = medicationIds.indexOf(node.id);
    const initialPoint =
      node.kind === "question"
        ? graphCenter()
        : hierarchyAngle !== null
        ? hierarchySeedPoint(node.kind, hierarchyAngle)
        : naturalGraphSeedPoint(index);
    return {
      ...node,
      x: initialPoint.x + evidenceMapSeedOffset(node.id, "x"),
      y: initialPoint.y + evidenceMapSeedOffset(node.id, "y"),
      hierarchyAngle,
      labelSectionCount: 0,
      medicationIndex,
      medicationCount: medicationIds.length,
      medicationParentCount: 0,
    };
  });
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const interactionLookupPairKeys = new Set(
    map.edges
      .filter((edge) => edge.kind === "interaction_lookup_source")
      .map((edge) => medicationLabelPairKey(edge.source, edge.target))
  );

  const links: VisualLink[] = map.edges
    .map((edge) => {
      const sourceNode = nodeById.get(edge.source);
      const targetNode = nodeById.get(edge.target);
      if (!sourceNode || !targetNode) {
        return null;
      }
      return {
        ...edge,
        hasParallelInteractionLookup:
          edge.kind === "has_label_source" &&
          interactionLookupPairKeys.has(
            medicationLabelPairKey(edge.source, edge.target)
          ),
        sourceNode,
        targetNode,
      };
    })
    .filter((link): link is VisualLink => Boolean(link));

  applyEvidenceGraphMetrics(nodes, links);

  return { nodes, links };
}

function buildHierarchyAngles(map: QuestionEvidenceMap) {
  const conceptIds = map.nodes
    .filter((node) => node.kind === "query_concept")
    .map((node) => node.id);
  const angleById = new Map<string, number>();
  conceptIds.forEach((nodeId, index) => {
    angleById.set(nodeId, hierarchyRingAngle(index, conceptIds.length));
  });

  for (const edge of map.edges) {
    if (edge.kind !== "resolved_as") {
      continue;
    }
    const conceptAngle = angleById.get(edge.source);
    if (conceptAngle !== undefined) {
      angleById.set(edge.target, conceptAngle);
    }
  }

  return angleById;
}

function applyEvidenceGraphMetrics(nodes: VisualNode[], links: VisualLink[]) {
  const labelSectionIdsBySourceId = new Map<string, Set<string>>();
  const medicationParentIdsByLabelId = new Map<string, Set<string>>();

  for (const link of links) {
    if (
      link.kind === "has_label_section" &&
      link.sourceNode.kind === "label_source" &&
      link.targetNode.kind === "label_section"
    ) {
      const sectionIds =
        labelSectionIdsBySourceId.get(link.sourceNode.id) ?? new Set<string>();
      sectionIds.add(link.targetNode.id);
      labelSectionIdsBySourceId.set(link.sourceNode.id, sectionIds);
    }

    if (
      isMedicationLabelLink(link.kind) &&
      link.sourceNode.kind === "resolved_medication" &&
      link.targetNode.kind === "label_source"
    ) {
      const medicationParentIds =
        medicationParentIdsByLabelId.get(link.targetNode.id) ??
        new Set<string>();
      medicationParentIds.add(link.sourceNode.id);
      medicationParentIdsByLabelId.set(link.targetNode.id, medicationParentIds);
    }
  }

  for (const node of nodes) {
    node.labelSectionCount = labelSectionIdsBySourceId.get(node.id)?.size ?? 0;
    node.medicationParentCount =
      medicationParentIdsByLabelId.get(node.id)?.size ?? 0;
  }
}

function createEvidenceMapSimulation(
  nodes: VisualNode[],
  links: SimulationLink[]
) {
  return forceSimulation<VisualNode>(nodes)
    .force(
      "link",
      forceLink<VisualNode, SimulationLink>(links)
        .id((node) => node.id)
        .distance(evidenceMapLinkDistance)
        .strength(evidenceMapLinkStrength)
        .iterations(2)
    )
    .force("charge", forceManyBody<VisualNode>().strength(nodeChargeStrength))
    .force("questionCenter", questionCenterForce())
    .force("medicationSpread", medicationSpreadForce())
    .force("hierarchyRing", hierarchyRingForce())
    .force("interactionLabelCentroid", interactionLabelCentroidForce(links))
    .force("conceptSpread", conceptSpreadForce())
    .force("conceptLabelRepulsion", conceptLabelRepulsionForce())
    .force(
      "collide",
      forceCollide<VisualNode>(
        (node) => evidenceNodeStyle(node).radius + nodeCollisionPadding(node)
      )
        .strength(1)
        .iterations(5)
    )
    .force("center", forceCenter(GRAPH_WIDTH / 2, GRAPH_HEIGHT / 2))
    .force(
      "x",
      forceX<VisualNode>(GRAPH_WIDTH / 2).strength(0.025)
    )
    .force(
      "y",
      forceY<VisualNode>(GRAPH_HEIGHT / 2).strength(0.025)
    )
    .alpha(0.95);
}

function questionCenterForce(): Force<VisualNode, SimulationLink> {
  let questionNodes: VisualNode[] = [];

  function force(alpha: number) {
    for (const node of questionNodes) {
      node.vx =
        (node.vx ?? 0) +
        (GRAPH_WIDTH / 2 - (node.x ?? GRAPH_WIDTH / 2)) * alpha * 0.16;
      node.vy =
        (node.vy ?? 0) +
        (GRAPH_HEIGHT / 2 - (node.y ?? GRAPH_HEIGHT / 2)) * alpha * 0.16;
    }
  }

  force.initialize = (nodes: VisualNode[]) => {
    questionNodes = nodes.filter(
      (node: VisualNode) => node.kind === "question"
    );
  };

  return force;
}

function conceptSpreadForce(): Force<VisualNode, SimulationLink> {
  let conceptNodes: VisualNode[] = [];

  function force(alpha: number) {
    for (let i = 0; i < conceptNodes.length; i++) {
      const source = conceptNodes[i];
      for (let j = i + 1; j < conceptNodes.length; j++) {
        const target = conceptNodes[j];
        const dx = (target.x ?? GRAPH_WIDTH / 2) - (source.x ?? GRAPH_WIDTH / 2);
        const dy = (target.y ?? GRAPH_HEIGHT / 2) - (source.y ?? GRAPH_HEIGHT / 2);
        const distance = Math.hypot(dx, dy) || 1;
        if (distance >= CONCEPT_SPREAD_DISTANCE) continue;

        const push = Math.min(
          CONCEPT_SPREAD_MAX_PUSH,
          ((CONCEPT_SPREAD_DISTANCE - distance) / distance) *
            alpha *
            CONCEPT_SPREAD_STRENGTH
        );
        source.vx = (source.vx ?? 0) - dx * push * 0.5;
        source.vy = (source.vy ?? 0) - dy * push * 0.5;
        target.vx = (target.vx ?? 0) + dx * push * 0.5;
        target.vy = (target.vy ?? 0) + dy * push * 0.5;
      }
    }
  }

  force.initialize = (nodes: VisualNode[]) => {
    conceptNodes = nodes.filter((n) => n.kind === "query_concept");
  };

  return force;
}

function conceptLabelRepulsionForce(): Force<VisualNode, SimulationLink> {
  let conceptNodes: VisualNode[] = [];
  let sharedLabelNodes: VisualNode[] = [];

  function force(alpha: number) {
    for (const concept of conceptNodes) {
      for (const label of sharedLabelNodes) {
        const dx = (concept.x ?? GRAPH_WIDTH / 2) - (label.x ?? GRAPH_WIDTH / 2);
        const dy = (concept.y ?? GRAPH_HEIGHT / 2) - (label.y ?? GRAPH_HEIGHT / 2);
        const distance = Math.hypot(dx, dy) || 1;
        if (distance >= CONCEPT_LABEL_REPULSION_DISTANCE) continue;

        const push =
          ((CONCEPT_LABEL_REPULSION_DISTANCE - distance) / distance) *
          alpha *
          CONCEPT_LABEL_REPULSION_STRENGTH;
        // Only push the concept away, not the label (label has its own centroid force)
        concept.vx = (concept.vx ?? 0) + dx * push;
        concept.vy = (concept.vy ?? 0) + dy * push;
      }
    }
  }

  force.initialize = (nodes: VisualNode[]) => {
    conceptNodes = nodes.filter((n) => n.kind === "query_concept");
    sharedLabelNodes = nodes.filter(
      (n) => n.kind === "label_source" && n.medicationParentCount > 1
    );
  };

  return force;
}

function medicationSpreadForce(): Force<VisualNode, SimulationLink> {
  let medicationNodes: VisualNode[] = [];

  function force(alpha: number) {
    for (let sourceIndex = 0; sourceIndex < medicationNodes.length; sourceIndex += 1) {
      const source = medicationNodes[sourceIndex];
      for (
        let targetIndex = sourceIndex + 1;
        targetIndex < medicationNodes.length;
        targetIndex += 1
      ) {
        const target = medicationNodes[targetIndex];
        const dx = (target.x ?? GRAPH_WIDTH / 2) - (source.x ?? GRAPH_WIDTH / 2);
        const dy = (target.y ?? GRAPH_HEIGHT / 2) - (source.y ?? GRAPH_HEIGHT / 2);
        const distance = Math.hypot(dx, dy) || 1;
        if (distance >= MEDICATION_SPREAD_DISTANCE) {
          continue;
        }

        const push = Math.min(
          MEDICATION_SPREAD_MAX_PUSH,
          ((MEDICATION_SPREAD_DISTANCE - distance) / distance) *
            alpha *
            MEDICATION_SPREAD_STRENGTH
        );
        const pushX = dx * push * 0.5;
        const pushY = dy * push * 0.5;
        source.vx = (source.vx ?? 0) - pushX;
        source.vy = (source.vy ?? 0) - pushY;
        target.vx = (target.vx ?? 0) + pushX;
        target.vy = (target.vy ?? 0) + pushY;
      }
    }
  }

  force.initialize = (nodes: VisualNode[]) => {
    medicationNodes = nodes.filter(
      (node: VisualNode) => node.kind === "resolved_medication"
    );
  };

  return force;
}

function hierarchyRingForce(): Force<VisualNode, SimulationLink> {
  let hierarchyNodes: VisualNode[] = [];

  function force(alpha: number) {
    for (const node of hierarchyNodes) {
      const target = hierarchySeedPoint(
        node.kind,
        node.hierarchyAngle ?? 0
      );
      const strength =
        node.kind === "query_concept"
          ? HIERARCHY_RING_STRENGTH * 0.72
          : HIERARCHY_RING_STRENGTH;
      node.vx =
        (node.vx ?? 0) + (target.x - (node.x ?? target.x)) * alpha * strength;
      node.vy =
        (node.vy ?? 0) + (target.y - (node.y ?? target.y)) * alpha * strength;
    }
  }

  force.initialize = (nodes: VisualNode[]) => {
    hierarchyNodes = nodes.filter(
      (node: VisualNode) =>
        (node.kind === "query_concept" ||
          node.kind === "resolved_medication") &&
        node.hierarchyAngle !== null
    );
  };

  return force;
}

function interactionLabelCentroidForce(links: SimulationLink[]): Force<VisualNode, SimulationLink> {
  let labelNodes: VisualNode[] = [];

  function force(alpha: number) {
    for (const node of labelNodes) {
      const parentPositions = links
        .filter(
          (link) =>
            isMedicationLabelLink(link.kind) &&
            (link.target as VisualNode).id === node.id
        )
        .map((link) => link.source as VisualNode)
        .filter((p) => p.x !== undefined);

      if (parentPositions.length < 2) continue;

      const centroidX = parentPositions.reduce((s, p) => s + (p.x ?? 0), 0) / parentPositions.length;
      const centroidY = parentPositions.reduce((s, p) => s + (p.y ?? 0), 0) / parentPositions.length;

      node.vx = (node.vx ?? 0) + (centroidX - (node.x ?? centroidX)) * alpha * 0.38;
      node.vy = (node.vy ?? 0) + (centroidY - (node.y ?? centroidY)) * alpha * 0.38;
    }
  }

  force.initialize = (allNodes: VisualNode[]) => {
    labelNodes = allNodes.filter((n) => n.kind === "label_source" && n.medicationParentCount > 1);
  };

  return force;
}

function withoutTerminologyContext(map: QuestionEvidenceMap): QuestionEvidenceMap {
  const visibleNodeIds = new Set(
    map.nodes
      .filter((node) => node.kind !== "rxnorm_context")
      .map((node) => node.id)
  );
  return {
    ...map,
    nodes: map.nodes.filter((node) => visibleNodeIds.has(node.id)),
    edges: map.edges.filter(
      (edge) =>
        edge.kind !== "has_terminology_context" &&
        visibleNodeIds.has(edge.source) &&
        visibleNodeIds.has(edge.target)
    ),
  };
}

function naturalGraphSeedPoint(index: number) {
  const angle = index * Math.PI * (3 - Math.sqrt(5));
  const radius = 42 * Math.sqrt(index + 1);
  const maxRadius = Math.min(GRAPH_WIDTH, GRAPH_HEIGHT) * 0.36;
  const normalizedRadius = Math.min(radius, maxRadius);
  return {
    x: GRAPH_WIDTH / 2 + Math.cos(angle) * normalizedRadius,
    y: GRAPH_HEIGHT / 2 + Math.sin(angle) * normalizedRadius,
  };
}

function graphCenter() {
  return { x: GRAPH_WIDTH / 2, y: GRAPH_HEIGHT / 2 };
}

function hierarchySeedPoint(kind: string, angle: number) {
  const radius =
    kind === "query_concept" ? CONCEPT_RING_RADIUS : MEDICATION_RING_RADIUS;
  return {
    x: GRAPH_WIDTH / 2 + Math.cos(angle) * radius,
    y: GRAPH_HEIGHT / 2 + Math.sin(angle) * radius,
  };
}

function hierarchyRingAngle(index: number, count: number) {
  if (count <= 1) {
    return -Math.PI / 2;
  }
  return -Math.PI / 2 + (index * Math.PI * 2) / count;
}

function medicationLabelPairKey(sourceId: string, targetId: string) {
  return `${sourceId}->${targetId}`;
}

function evidenceMapLinkDistance(link: SimulationLink) {
  if (link.kind === "has_label_section") {
    return 30 + Math.min(5, link.sourceNode.labelSectionCount) * 4;
  }

  if (isMedicationLabelLink(link.kind)) {
    const sharedParentBonus =
      Math.max(0, link.targetNode.medicationParentCount - 1) * 40;
    if (
      link.kind === "interaction_lookup_source" ||
      link.hasParallelInteractionLookup
    ) {
      return link.targetNode.medicationParentCount > 1
        ? 280 + sharedParentBonus
        : 230;
    }
    return link.targetNode.medicationParentCount > 1
      ? 200 + sharedParentBonus
      : 150;
  }

  const distances: Record<string, number> = {
    resolved_as: 118,
    has_role: 130,
    mentions_in_interaction_section: 120,
    has_terminology_context: 96,
  };
  return distances[link.kind] ?? 104;
}

function evidenceMapLinkStrength(link: SimulationLink) {
  if (link.kind === "has_label_section") {
    return 1.15;
  }

  if (isMedicationLabelLink(link.kind)) {
    if (
      link.kind === "interaction_lookup_source" ||
      link.hasParallelInteractionLookup
    ) {
      return link.targetNode.medicationParentCount > 1 ? 0.22 : 0.28;
    }
    return link.targetNode.medicationParentCount > 1 ? 0.28 : 0.58;
  }

  const strengths: Record<string, number> = {
    resolved_as: 0.76,
    has_role: 0.72,
    mentions_in_interaction_section: 0.58,
    has_terminology_context: 0.58,
  };
  return strengths[link.kind] ?? 0.66;
}

function isMedicationLabelLink(kind: string) {
  return kind === "has_label_source" || kind === "interaction_lookup_source";
}

function nodeChargeStrength(node: VisualNode) {
  if (node.kind === "question") {
    return -620;
  }
  if (node.kind === "resolved_medication") {
    return -700;
  }
  if (node.kind === "label_source") {
    return node.medicationParentCount > 1 ? -1180 : -420;
  }
  if (node.kind === "query_concept") {
    return -320;
  }
  if (node.kind === "label_section") {
    return -30;
  }
  return -150;
}

function nodeCollisionPadding(node: VisualNode) {
  if (node.kind === "question" || node.kind === "resolved_medication") {
    return 28;
  }
  if (node.kind === "label_source") {
    return node.medicationParentCount > 1 ? 52 : 24;
  }
  if (node.kind === "query_concept") {
    return 20;
  }
  if (node.kind === "label_section") {
    return 10;
  }
  return 14;
}

function evidenceMapSeedOffset(
  id: string,
  axis: "x" | "y"
) {
  const seed = Array.from(id).reduce(
    (total, character) => total + character.charCodeAt(0),
    axis === "x" ? 19 : 47
  );
  return (seed % 54) - 27;
}

function fitGraphToView(nodes: VisualNode[]) {
  if (nodes.length === 0) {
    return { pan: { x: 0, y: 0 }, zoom: 1 };
  }
  let minX = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;

  for (const node of nodes) {
    const radius = evidenceNodeStyle(node).radius;
    minX = Math.min(minX, node.x - radius);
    maxX = Math.max(maxX, node.x + radius);
    minY = Math.min(minY, node.y - radius);
    maxY = Math.max(maxY, node.y + radius);
  }

  const graphWidth = Math.max(1, maxX - minX);
  const graphHeight = Math.max(1, maxY - minY);
  const zoom = clamp(
    Math.min(
      (GRAPH_WIDTH - FIT_PADDING * 2) / graphWidth,
      (GRAPH_HEIGHT - FIT_PADDING * 2) / graphHeight
    ),
    MIN_ZOOM,
    1.08
  );
  const centerX = (minX + maxX) / 2;
  const centerY = (minY + maxY) / 2;

  return {
    pan: {
      x: GRAPH_WIDTH / 2 - centerX * zoom,
      y: GRAPH_HEIGHT / 2 - centerY * zoom,
    },
    zoom,
  };
}

function citationForEvidenceMapNode(
  node: VisualNode,
  links: VisualLink[]
): EvidenceCitation | null {
  if (node.source_id && node.section) {
    return {
      source_id: node.source_id,
      section: node.section,
      rxcui: node.rxcui,
    };
  }
  if (node.source_id) {
    const sectionLink = links.find(
      (link) =>
        link.sourceNode.id === node.id &&
        link.targetNode.source_id === node.source_id &&
        Boolean(link.targetNode.section)
    );
    if (sectionLink?.targetNode.section) {
      return {
        source_id: node.source_id,
        section: sectionLink.targetNode.section,
        rxcui: node.rxcui ?? sectionLink.targetNode.rxcui,
      };
    }
  }
  return null;
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

function evidenceNodeStyle(nodeOrKind: QuestionEvidenceMapNode | string) {
  const kind = typeof nodeOrKind === "string" ? nodeOrKind : nodeOrKind.kind;
  return nodeStyles[kind] ?? nodeStyles.query_concept;
}

function edgeStroke(kind: string) {
  if (
    kind === "mentions_in_interaction_section" ||
    kind === "interaction_lookup_source"
  ) {
    return "#371E8F";
  }
  if (kind === "has_terminology_context") {
    return "#D97706";
  }
  return "#94A3B8";
}

function edgeDashArray(kind: string) {
  if (kind === "interaction_lookup_source") {
    return "5 4";
  }
  if (kind === "has_terminology_context") {
    return "4 4";
  }
  return undefined;
}

function edgeTooltipContent(link: VisualLink) {
  const source = displayEvidenceMapEdgeNode(link.sourceNode);
  const target = displayEvidenceMapEdgeNode(link.targetNode);
  const sectionName = displaySectionName(link.section ?? link.targetNode.section ?? target);
  const title =
    edgeRelationshipLabels[link.kind] ??
    sentenceCase(link.kind.replaceAll("_", " "));

  switch (link.kind) {
    case "has_role":
      return {
        title,
        body: (
          <>
            <strong>{target.toUpperCase()}</strong> was extracted from the user
            question
            {conceptRoleLabels(link.targetNode).length
              ? ` as ${formatList(conceptRoleLabels(link.targetNode).map((role) => role.toLowerCase()))}`
              : ""}
            .
          </>
        ),
      };
    case "resolved_as":
      return {
        title,
        body: (
          <>
            The mentioned medication <strong>{source}</strong> was resolved through RxNorm
            and matched the concept <strong>{target.toUpperCase()}</strong>
            {link.rxcui ? ` (RXCUI: ${link.rxcui})` : ""}.
          </>
        ),
      };
    case "has_label_source":
      return {
        title,
        body: (
          <>
            The label source <strong>{target}</strong> belongs to the medication{" "}
            <strong>{source.toUpperCase()}</strong>.
          </>
        ),
      };
    case "interaction_lookup_source":
      const interactionTerms = link.interaction_terms?.length
        ? link.interaction_terms.map((term) => term.toUpperCase())
        : [source.toUpperCase()];
      return {
        title,
        body: (
          <>
            An interaction-specific lookup for{" "}
            <strong>{formatList(interactionTerms)}</strong> returned the drug
            label <strong>{target}</strong>.
          </>
        ),
      };
    case "has_label_section":
      return {
        title,
        body: (
          <>
            The section <strong>{sentenceCase(sectionName)}</strong> belongs to the{" "}
            <strong>{source}</strong> label.
          </>
        ),
      };
    case "mentions_in_interaction_section":
      return {
        title,
        body: (
          <>
            The section <strong>{sentenceCase(sectionName)}</strong> belongs to the{" "}
            <strong>{source}</strong> label.
          </>
        ),
      };
    case "has_terminology_context":
      return {
        title,
        body: (
          <>
            The medication <strong>{source.toUpperCase()}</strong> is associated with the terminology context <strong>{target}</strong>.
          </>
        ),
      };
    default:
      return {
        title,
        body: (
          <>
            {link.label && <>{link.label}<br /></>}
            <strong>{source.toUpperCase()}</strong> is related to <strong>{target.toUpperCase()}</strong>.
          </>
        ),
      };
  }
}

function nodeTooltipBody(node: QuestionEvidenceMapNode) {
  const lines = [evidenceNodeStyle(node).label];
  if (node.kind === "query_concept") {
    const roles = conceptRoleLabels(node);
    if (roles.length) {
      lines.push(formatList(roles));
    }
    if (node.subtitle && !roles.includes(node.subtitle)) {
      lines.push(node.subtitle);
    }
    return lines.join("\n");
  }
  if (node.kind === "resolved_medication" && node.subtitle) {
    lines.push(displayRxNormType(node.subtitle));
  }
  if (node.label_rxcuis?.length) {
    const label = node.label_rxcuis.length > 1 ? "RXCUIs" : "RXCUI";
    lines.push(`${label} ${node.label_rxcuis.join(", ")}`);
  } else if (node.rxcui) {
    lines.push(`RXCUI ${node.rxcui}`);
  }
  if (node.section) {
    lines.push(displaySectionName(node.section));
  }
  if (node.subtitle && node.kind !== "resolved_medication") {
    lines.push(node.subtitle);
  }
  return lines.join("\n");
}

function displayEvidenceMapNodeKind(node: QuestionEvidenceMapNode) {
  return evidenceNodeStyle(node).label;
}

function displayEvidenceMapEdgeNode(node: QuestionEvidenceMapNode) {
  if (node.kind === "resolved_medication") {
    return displayGraphNodeName(node.label);
  }
  return node.label;
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

function conceptRoleLabels(node: QuestionEvidenceMapNode) {
  return roleTags(node).map(displayMentionRole);
}

function roleTags(node: QuestionEvidenceMapNode) {
  const tags = new Set(
    [
      node.role,
      ...node.tags.filter((tag) => evidenceMapRoleTags.has(tag)),
    ].filter((tag): tag is string => Boolean(tag))
  );
  return Array.from(tags);
}

function displayRxNormType(value: string) {
  return rxNormTypeLabels[value.toUpperCase()] ?? sentenceCase(value);
}

function formatList(values: string[]) {
  if (values.length <= 1) {
    return values[0] ?? "";
  }
  if (values.length === 2) {
    return `${values[0]} and ${values[1]}`;
  }
  return `${values.slice(0, -1).join(", ")}, and ${values[values.length - 1]}`;
}

function nodeTypeSortIndex(kind: string) {
  const index = evidenceNodeTypeOrder.indexOf(kind);
  return index === -1 ? Number.MAX_SAFE_INTEGER : index;
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

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(value, max));
}
