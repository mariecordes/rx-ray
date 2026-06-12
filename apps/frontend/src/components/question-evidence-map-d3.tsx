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
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [hoverTooltip, setHoverTooltip] = useState<HoverTooltip | null>(null);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set());
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
    startGraphX: number;
    startGraphY: number;
    origins: Map<string, { x: number; y: number }>;
  } | null>(null);
  const [nodeOverrides, setNodeOverrides] = useState<
    Map<string, { x: number; y: number }>
  >(new Map());

  const visibleMap = useMemo(() => withoutTerminologyContext(map), [map]);
  const graph = useMemo(() => buildD3EvidenceGraph(visibleMap), [visibleMap]);
  const positionedNodes = useMemo(() => {
    return graph.nodes.map((node) => {
      const override = nodeOverrides.get(node.id);
      return override ? { ...node, ...override } : node;
    });
  }, [graph.nodes, nodeOverrides]);
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
    setNodeOverrides(new Map());
    const fittedView = fitGraphToView(graph.nodes);
    setPan(fittedView.pan);
    setZoom(fittedView.zoom);
  }, [graph.nodes]);

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
      const deltaX = point.x - nodeDrag.startGraphX;
      const deltaY = point.y - nodeDrag.startGraphY;
      const hasMoved =
        nodeDrag.moved ||
        Math.hypot(
          event.clientX - nodeDrag.startClientX,
          event.clientY - nodeDrag.startClientY
        ) > 4;
      setNodeOverrides((current) => {
        const next = new Map(current);
        for (const [nodeId, origin] of nodeDrag.origins) {
          next.set(nodeId, {
            x: origin.x + deltaX,
            y: origin.y + deltaY,
          });
        }
        return next;
      });
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
                    const startPoint = screenToGraph(event.clientX, event.clientY);
                    setNodeDrag({
                      id: node.id,
                      moved: false,
                      startClientX: event.clientX,
                      startClientY: event.clientY,
                      startGraphX: startPoint.x,
                      startGraphY: startPoint.y,
                      origins: buildNodeDragOrigins(node, positionedNodeById, graph.links),
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
            <p className="line-clamp-2 min-h-12 text-sm leading-6 text-slate-600">
              Select a bubble to inspect the extracted concept, medication,
              source, or label section.
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
  const topology = buildEvidenceMapTopology(map);
  const nodes: VisualNode[] = map.nodes.map((node) => {
    const anchor = evidenceMapAnchor(node, topology);
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
        .strength((link) => evidenceMapLinkStrength(link.kind))
    )
    .force("charge", forceManyBody().strength(-150))
    .force(
      "collide",
      forceCollide<VisualNode>(
        (node) => evidenceNodeStyle(node).radius + 9
      ).iterations(3)
    )
    .force("center", forceCenter(GRAPH_WIDTH / 2, GRAPH_HEIGHT / 2))
    .force("x", forceX<VisualNode>((node) => evidenceMapAnchor(node, topology).x).strength(0.13))
    .force("y", forceY<VisualNode>((node) => evidenceMapAnchor(node, topology).y).strength(0.12))
    .stop();

  for (let index = 0; index < 360; index += 1) {
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

type EvidenceMapTopology = {
  anchorsById: Map<string, { x: number; y: number }>;
};

function buildEvidenceMapTopology(map: QuestionEvidenceMap): EvidenceMapTopology {
  const nodeById = new Map(map.nodes.map((node) => [node.id, node]));
  const childIdsByParentId = new Map<string, string[]>();
  const parentIdsByChildId = new Map<string, string[]>();
  for (const edge of map.edges) {
    if (!nodeById.has(edge.source) || !nodeById.has(edge.target)) {
      continue;
    }
    const children = childIdsByParentId.get(edge.source) ?? [];
    children.push(edge.target);
    childIdsByParentId.set(edge.source, children);

    const parents = parentIdsByChildId.get(edge.target) ?? [];
    parents.push(edge.source);
    parentIdsByChildId.set(edge.target, parents);
  }

  const questionNodes = map.nodes.filter((node) => node.kind === "question");
  const rootId = questionNodes[0]?.id ?? map.nodes[0]?.id;
  const anchorsById = new Map<string, { x: number; y: number }>();
  if (!rootId) {
    return { anchorsById };
  }

  anchorsById.set(rootId, graphCenter());
  const depthsById = new Map<string, number>([[rootId, 0]]);
  const queue = [rootId];
  for (let index = 0; index < queue.length; index += 1) {
    const parentId = queue[index];
    const parentDepth = depthsById.get(parentId) ?? 0;
    for (const childId of childIdsByParentId.get(parentId) ?? []) {
      if (!depthsById.has(childId)) {
        depthsById.set(childId, parentDepth + 1);
        queue.push(childId);
      }
    }
  }

  const rootChildren = childIdsByParentId.get(rootId) ?? [];
  const branchAngleById = new Map<string, number>();
  rootChildren.forEach((childId, index) => {
    branchAngleById.set(childId, radialAngle(index, rootChildren.length));
  });

  for (const node of map.nodes) {
    if (node.id === rootId) {
      continue;
    }
    const depth = depthsById.get(node.id) ?? evidenceMapFallbackDepth(node.kind);
    const parents = parentIdsByChildId.get(node.id) ?? [];
    const parentAngles = parents
      .map((parentId) => branchAngleById.get(parentId))
      .filter((angle): angle is number => typeof angle === "number");
    const baseAngle =
      branchAngleById.get(node.id) ??
      averageAngle(parentAngles) ??
      radialAngle(map.nodes.indexOf(node), map.nodes.length);

    branchAngleById.set(node.id, baseAngle);
    const siblings = parents.length
      ? parents.flatMap((parentId) => childIdsByParentId.get(parentId) ?? [])
      : map.nodes.filter((otherNode) => otherNode.kind === node.kind).map((otherNode) => otherNode.id);
    const siblingIndex = Math.max(0, siblings.indexOf(node.id));
    const siblingOffsetAngle = siblingAngleOffset(siblingIndex, siblings.length, depth);
    const radius = evidenceMapDepthRadius(depth, node.kind);
    anchorsById.set(
      node.id,
      polarToPoint(radius, baseAngle + siblingOffsetAngle)
    );
  }

  return { anchorsById };
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

function evidenceMapAnchor(
  nodeOrKind: QuestionEvidenceMapNode | string,
  topology?: EvidenceMapTopology
) {
  const kind = typeof nodeOrKind === "string" ? nodeOrKind : nodeOrKind.kind;
  const node = typeof nodeOrKind === "string" ? null : nodeOrKind;
  if (node && topology?.anchorsById.has(node.id)) {
    return topology.anchorsById.get(node.id) ?? graphCenter();
  }

  const anchors: Record<string, { x: number; y: number }> = {
    question: { x: GRAPH_WIDTH * 0.5, y: GRAPH_HEIGHT * 0.5 },
    query_concept: polarToPoint(88, -Math.PI / 2),
    resolved_medication: polarToPoint(152, 0),
    label_source: polarToPoint(228, Math.PI / 2),
    label_section: polarToPoint(300, Math.PI),
    rxnorm_context: polarToPoint(180, Math.PI / 4),
  };
  return anchors[kind] ?? { x: GRAPH_WIDTH * 0.5, y: GRAPH_HEIGHT * 0.5 };
}

function graphCenter() {
  return { x: GRAPH_WIDTH / 2, y: GRAPH_HEIGHT / 2 };
}

function radialAngle(index: number, count: number) {
  if (count <= 1) {
    return -Math.PI / 2;
  }
  return -Math.PI / 2 + (index * Math.PI * 2) / count;
}

function siblingAngleOffset(index: number, count: number, depth: number) {
  if (count <= 1) {
    return 0;
  }
  const center = (count - 1) / 2;
  const maxSpread = depth >= 3 ? 0.42 : 0.3;
  const step = Math.min(0.16, maxSpread / Math.max(1, count - 1));
  return (index - center) * step;
}

function evidenceMapDepthRadius(depth: number, kind: string) {
  const depthRadius: Record<number, number> = {
    0: 0,
    1: 72,
    2: 128,
    3: 188,
    4: 246,
  };
  if (kind === "label_section") {
    return 254;
  }
  return depthRadius[Math.min(4, depth)] ?? 210;
}

function evidenceMapFallbackDepth(kind: string) {
  const fallbackDepths: Record<string, number> = {
    question: 0,
    query_concept: 1,
    resolved_medication: 2,
    label_source: 3,
    label_section: 4,
    rxnorm_context: 3,
  };
  return fallbackDepths[kind] ?? 2;
}

function polarToPoint(radius: number, angle: number) {
  return {
    x: GRAPH_WIDTH / 2 + Math.cos(angle) * radius,
    y: GRAPH_HEIGHT / 2 + Math.sin(angle) * radius,
  };
}

function averageAngle(angles: number[]) {
  if (angles.length === 0) {
    return null;
  }
  const x = angles.reduce((total, angle) => total + Math.cos(angle), 0);
  const y = angles.reduce((total, angle) => total + Math.sin(angle), 0);
  return Math.atan2(y, x);
}

function evidenceMapLinkDistance(kind: string) {
  const distances: Record<string, number> = {
    resolved_as: 82,
    has_role: 78,
    has_label_source: 72,
    interaction_lookup_source: 78,
    has_label_section: 32,
    mentions_in_interaction_section: 36,
    has_terminology_context: 82,
  };
  return distances[kind] ?? 64;
}

function evidenceMapLinkStrength(kind: string) {
  const strengths: Record<string, number> = {
    resolved_as: 0.42,
    has_role: 0.32,
    has_label_source: 0.58,
    interaction_lookup_source: 0.62,
    has_label_section: 0.86,
    mentions_in_interaction_section: 0.9,
    has_terminology_context: 0.32,
  };
  return strengths[kind] ?? 0.45;
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

function buildNodeDragOrigins(
  node: VisualNode,
  nodeById: Map<string, VisualNode>,
  links: VisualLink[]
) {
  const draggedIds = new Set([node.id]);
  const childIdsByParentId = new Map<string, string[]>();
  for (const link of links) {
    const children = childIdsByParentId.get(link.sourceNode.id) ?? [];
    children.push(link.targetNode.id);
    childIdsByParentId.set(link.sourceNode.id, children);
  }

  const queue = [node.id];
  for (let index = 0; index < queue.length; index += 1) {
    const parentId = queue[index];
    for (const childId of childIdsByParentId.get(parentId) ?? []) {
      if (!draggedIds.has(childId)) {
        draggedIds.add(childId);
        queue.push(childId);
      }
    }
  }

  const origins = new Map<string, { x: number; y: number }>();
  for (const nodeId of draggedIds) {
    const draggedNode = nodeById.get(nodeId);
    if (draggedNode) {
      origins.set(nodeId, { x: draggedNode.x, y: draggedNode.y });
    }
  }
  return origins;
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
  if (node.rxcui) {
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
