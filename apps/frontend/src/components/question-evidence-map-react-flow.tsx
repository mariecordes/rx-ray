"use client";

import {
  Background,
  BaseEdge,
  Controls,
  type Edge,
  type EdgeProps,
  type EdgeTypes,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  type Node,
  type NodeProps,
  type NodeTypes,
  useInternalNode,
} from "@xyflow/react";
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";
import { useCallback, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  EvidenceCitation,
  QuestionEvidenceMap,
  QuestionEvidenceMapEdge,
  QuestionEvidenceMapNode,
} from "@/lib/types";
import { cn } from "@/lib/utils";

export type EvidenceMapNavigationTarget = {
  rxcui: string;
};

type EvidenceMapReactFlowProps = {
  map: QuestionEvidenceMap;
  onCitationClick: (citation: EvidenceCitation) => void;
  onRxcuiClick: (target: EvidenceMapNavigationTarget) => void;
};

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

function displaySectionName(section: string) {
  return sectionLabels[section] ?? section.replaceAll("_", " ");
}

function sentenceCase(value: string) {
  return value
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function displayGraphNodeName(name: string) {
  return name.toUpperCase();
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

const interactionSpecificBadgeClasses =
  "border-slate-300 bg-slate-100 text-slate-700";

export function EvidenceMapReactFlow({
  map,
  onCitationClick,
  onRxcuiClick,
}: EvidenceMapReactFlowProps) {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const selectedMapNode =
    map.nodes.find((node) => node.id === selectedNodeId) ?? null;
  const handleNodeClick = useCallback((node: QuestionEvidenceMapNode) => {
    setSelectedNodeId((current) => (current === node.id ? null : node.id));
  }, []);
  const { edges, nodes } = useMemo(
    () => buildEvidenceFlowElements(map, handleNodeClick, selectedNodeId),
    [handleNodeClick, map, selectedNodeId]
  );

  return (
    <div className="relative h-[560px] overflow-hidden rounded-md border border-slate-200 bg-white">
      <EvidenceMapLegend />
      <ReactFlow
        key={evidenceMapSignature(map)}
        colorMode="light"
        edges={edges}
        edgeTypes={evidenceMapEdgeTypes}
        edgesFocusable
        fitView
        fitViewOptions={{ maxZoom: 1.05, padding: 0.24 }}
        maxZoom={1.8}
        minZoom={0.35}
        nodeTypes={evidenceMapNodeTypes}
        nodes={nodes}
        nodesConnectable={false}
        nodesDraggable={false}
        onPaneClick={() => setSelectedNodeId(null)}
        panOnScroll
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#ECE4F7" gap={28} size={1} />
        <MiniMap
          nodeColor={(node) =>
            evidenceMapMiniMapColor(String(node.data?.kind ?? ""))
          }
          pannable
          zoomable
        />
        <Controls showInteractive={false} />
      </ReactFlow>
      {selectedMapNode ? (
        <EvidenceMapDetailPanel
          node={selectedMapNode}
          onCitationClick={onCitationClick}
          onRxcuiClick={onRxcuiClick}
        />
      ) : null}
    </div>
  );
}

type EvidenceFlowNodeData = Record<string, unknown> & {
  dimmed: boolean;
  kind: string;
  mapNode: QuestionEvidenceMapNode;
  onSelect: (node: QuestionEvidenceMapNode) => void;
  selected: boolean;
};

type EvidenceFlowNode = Node<EvidenceFlowNodeData, "evidence">;

const evidenceMapNodeTypes: NodeTypes = {
  evidence: EvidenceMapFlowNode,
};

const evidenceMapEdgeTypes: EdgeTypes = {
  floating: FloatingEvidenceMapEdge,
};

function EvidenceMapFlowNode({ data }: NodeProps<EvidenceFlowNode>) {
  const node = data.mapNode;
  const shortLabel = evidenceMapShortLabel(node);
  const showLabel =
    node.kind === "question" ||
    node.kind === "resolved_medication" ||
    (node.kind === "query_concept" && Boolean(node.role));
  return (
    <button
      type="button"
      onClick={() => data.onSelect(node)}
      title={node.subtitle ?? node.label}
      className={cn(
        "relative grid place-items-center rounded-full border text-center shadow-sm transition hover:scale-105 hover:border-[#371E8F]",
        evidenceMapNodeClasses(node.kind),
        data.selected && "border-[#371E8F] ring-2 ring-[#D7C8F4]",
        data.dimmed && "opacity-25",
        node.kind === "question" && "h-14 w-14",
        node.kind === "query_concept" && "h-8 w-8",
        node.kind === "resolved_medication" && "h-10 w-28 rounded-full px-3",
        node.kind === "label_source" && "h-7 w-7",
        node.kind === "label_section" && "h-4 w-4 shadow-none",
        node.kind === "rxnorm_context" && "h-8 w-8"
      )}
    >
      <Handle
        className="!h-1.5 !w-1.5 !border-white !bg-transparent"
        position={Position.Left}
        type="target"
      />
      <Handle
        className="!h-1.5 !w-1.5 !border-white !bg-transparent"
        position={Position.Right}
        type="source"
      />
      {showLabel ? (
        <span
          className={cn(
            "max-w-full truncate px-1 text-[10px] font-semibold uppercase leading-4 text-slate-900",
            node.kind === "question" && "text-[9px]",
            node.kind === "query_concept" && "sr-only"
          )}
        >
          {shortLabel}
        </span>
      ) : (
        <span className="sr-only">{shortLabel}</span>
      )}
    </button>
  );
}

function FloatingEvidenceMapEdge({
  id,
  source,
  target,
  style,
  interactionWidth,
}: EdgeProps) {
  const sourceNode = useInternalNode(source);
  const targetNode = useInternalNode(target);

  if (!sourceNode || !targetNode) {
    return null;
  }

  const sourcePoint = evidenceMapFloatingPoint(sourceNode, targetNode);
  const targetPoint = evidenceMapFloatingPoint(targetNode, sourceNode);
  const path = `M ${sourcePoint.x},${sourcePoint.y} L ${targetPoint.x},${targetPoint.y}`;

  return (
    <BaseEdge
      id={id}
      interactionWidth={interactionWidth}
      path={path}
      style={style}
    />
  );
}

function evidenceMapFloatingPoint(
  node: ReturnType<typeof useInternalNode>,
  oppositeNode: ReturnType<typeof useInternalNode>
) {
  if (!node || !oppositeNode) {
    return { x: 0, y: 0 };
  }

  const nodeWidth = node.measured.width ?? node.width ?? 1;
  const nodeHeight = node.measured.height ?? node.height ?? 1;
  const oppositeWidth = oppositeNode.measured.width ?? oppositeNode.width ?? 1;
  const oppositeHeight = oppositeNode.measured.height ?? oppositeNode.height ?? 1;
  const nodeCenter = {
    x: node.internals.positionAbsolute.x + nodeWidth / 2,
    y: node.internals.positionAbsolute.y + nodeHeight / 2,
  };
  const oppositeCenter = {
    x: oppositeNode.internals.positionAbsolute.x + oppositeWidth / 2,
    y: oppositeNode.internals.positionAbsolute.y + oppositeHeight / 2,
  };
  const radiusX = nodeWidth / 2;
  const radiusY = nodeHeight / 2;
  const dx = oppositeCenter.x - nodeCenter.x;
  const dy = oppositeCenter.y - nodeCenter.y;
  if (dx === 0 && dy === 0) {
    return nodeCenter;
  }
  const scale =
    1 /
    Math.sqrt((dx * dx) / (radiusX * radiusX) + (dy * dy) / (radiusY * radiusY));

  return {
    x: nodeCenter.x + dx * scale,
    y: nodeCenter.y + dy * scale,
  };
}

function EvidenceMapLegend() {
  const items = [
    ["Question", "bg-white border-slate-300"],
    ["Extracted", "bg-[#EEF2FF] border-[#C7D2FE]"],
    ["Medication", "bg-[#E8DDF9] border-[#C7B4EF]"],
    ["Source", "bg-[#E0F2FE] border-[#7DD3FC]"],
    ["Section", "bg-slate-300 border-slate-400"],
    ["Context", "bg-amber-100 border-amber-300"],
  ];

  return (
    <div className="pointer-events-none absolute left-3 top-3 z-10 flex flex-wrap gap-2 rounded-md border border-slate-200 bg-white/90 px-2 py-1.5 shadow-sm backdrop-blur">
      {items.map(([label, classes]) => (
        <div key={label} className="flex items-center gap-1.5">
          <span className={cn("size-2.5 rounded-full border", classes)} />
          <span className="text-[10px] font-medium uppercase text-slate-500">
            {label}
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
  node: QuestionEvidenceMapNode | null;
  onCitationClick: (citation: EvidenceCitation) => void;
  onRxcuiClick: (target: EvidenceMapNavigationTarget) => void;
}) {
  const canJumpToEvidence = Boolean(node?.source_id && node?.section);
  const canJumpToMedication = Boolean(node?.rxcui);

  return (
    <aside className="absolute bottom-4 right-4 z-10 max-h-[430px] w-[300px] overflow-auto rounded-md border border-slate-200 bg-white/95 p-4 shadow-lg backdrop-blur">
      <div className="text-xs font-medium uppercase text-slate-500">
        Selected map item
      </div>
      {node ? (
        <div className="mt-3 space-y-3">
          <div>
            <div className="flex flex-wrap gap-1.5">
              <Badge className="border-slate-200 bg-white text-slate-700">
                {displayEvidenceMapNodeKind(node)}
              </Badge>
              {node.evidence_scope ? (
                <Badge className="border-slate-200 bg-white text-slate-700">
                  {sentenceCase(node.evidence_scope)}
                </Badge>
              ) : null}
              {node.tags.includes("interaction_targeted_lookup") ? (
                <Badge className={interactionSpecificBadgeClasses}>
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
      ) : null}
    </aside>
  );
}

function buildEvidenceFlowElements(
  map: QuestionEvidenceMap,
  onNodeSelect: (node: QuestionEvidenceMapNode) => void,
  selectedNodeId: string | null
): { nodes: EvidenceFlowNode[]; edges: Edge[] } {
  const width = 980;
  const height = 520;
  const simulationNodes: EvidenceSimulationNode[] = map.nodes.map((node) => {
    const anchor = evidenceMapAnchor(node.kind, width, height);
    return {
      id: node.id,
      mapNode: node,
      x: anchor.x + evidenceMapSeedOffset(node.id, "x"),
      y: anchor.y + evidenceMapSeedOffset(node.id, "y"),
    };
  });
  const simulationNodeIds = new Set(simulationNodes.map((node) => node.id));
  const simulationLinks: EvidenceSimulationLink[] = map.edges
    .filter(
      (edge) =>
        simulationNodeIds.has(edge.source) && simulationNodeIds.has(edge.target)
    )
    .map((edge) => ({
      source: edge.source,
      target: edge.target,
      kind: edge.kind,
    }));

  const simulation = forceSimulation<EvidenceSimulationNode>(simulationNodes)
    .force(
      "link",
      forceLink<EvidenceSimulationNode, EvidenceSimulationLink>(simulationLinks)
        .id((node) => node.id)
        .distance((link) => evidenceMapLinkDistance(link.kind))
        .strength(0.42)
    )
    .force("charge", forceManyBody().strength(-170))
    .force(
      "collide",
      forceCollide<EvidenceSimulationNode>((node) =>
        evidenceMapNodeRadius(node.mapNode) + 7
      ).strength(0.95)
    )
    .force("center", forceCenter(width / 2, height / 2))
    .force(
      "x",
      forceX<EvidenceSimulationNode>((node) =>
        evidenceMapAnchor(node.mapNode.kind, width, height).x
      ).strength(0.13)
    )
    .force(
      "y",
      forceY<EvidenceSimulationNode>((node) =>
        evidenceMapAnchor(node.mapNode.kind, width, height).y
      ).strength(0.1)
    )
    .stop();

  for (let index = 0; index < 190; index += 1) {
    simulation.tick();
  }

  const selectedRelatedIds = selectedNodeId
    ? new Set([
        selectedNodeId,
        ...map.edges
          .filter(
            (edge) =>
              edge.source === selectedNodeId || edge.target === selectedNodeId
          )
          .flatMap((edge) => [edge.source, edge.target]),
      ])
    : null;

  const flowNodes = simulationNodes.map((simulationNode) => {
    const size = evidenceMapNodeSize(simulationNode.mapNode);
    return evidenceFlowNode(
      simulationNode.mapNode,
      Math.min(
        width - size.width - 12,
        Math.max(12, (simulationNode.x ?? width / 2) - size.width / 2)
      ),
      Math.min(
        height - size.height - 12,
        Math.max(12, (simulationNode.y ?? height / 2) - size.height / 2)
      ),
      onNodeSelect,
      selectedNodeId,
      Boolean(selectedRelatedIds && !selectedRelatedIds.has(simulationNode.id))
    );
  });

  const visibleNodeIds = new Set(flowNodes.map((node) => node.id));
  const flowEdges = map.edges
    .filter(
      (edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)
    )
    .map((edge) => evidenceFlowEdge(edge, selectedNodeId));
  return { nodes: flowNodes, edges: flowEdges };
}

type EvidenceSimulationNode = SimulationNodeDatum & {
  id: string;
  mapNode: QuestionEvidenceMapNode;
};

type EvidenceSimulationLink = SimulationLinkDatum<EvidenceSimulationNode> & {
  kind: string;
};

function evidenceMapAnchor(kind: string, width: number, height: number) {
  const anchors: Record<string, { x: number; y: number }> = {
    question: { x: width * 0.14, y: height * 0.5 },
    query_concept: { x: width * 0.33, y: height * 0.5 },
    resolved_medication: { x: width * 0.48, y: height * 0.42 },
    label_source: { x: width * 0.68, y: height * 0.5 },
    label_section: { x: width * 0.84, y: height * 0.5 },
    rxnorm_context: { x: width * 0.54, y: height * 0.72 },
  };
  return anchors[kind] ?? { x: width * 0.5, y: height * 0.5 };
}

function evidenceMapNodeSize(node: QuestionEvidenceMapNode) {
  const sizes: Record<string, { width: number; height: number }> = {
    question: { width: 56, height: 56 },
    query_concept: { width: 32, height: 32 },
    resolved_medication: { width: 112, height: 40 },
    label_source: { width: 28, height: 28 },
    label_section: { width: 16, height: 16 },
    rxnorm_context: { width: 32, height: 32 },
  };
  return sizes[node.kind] ?? { width: 28, height: 28 };
}

function evidenceMapNodeRadius(node: QuestionEvidenceMapNode) {
  const size = evidenceMapNodeSize(node);
  return Math.max(size.width, size.height) / 2;
}

function evidenceMapLinkDistance(kind: string) {
  const distances: Record<string, number> = {
    resolved_as: 90,
    has_role: 110,
    has_label_source: 95,
    has_label_section: 58,
    mentions_in_interaction_section: 86,
    has_terminology_context: 120,
  };
  return distances[kind] ?? 90;
}

function evidenceMapSeedOffset(id: string, axis: "x" | "y") {
  const seed = Array.from(id).reduce(
    (total, character) => total + character.charCodeAt(0),
    axis === "x" ? 17 : 43
  );
  return (seed % 90) - 45;
}

function evidenceFlowNode(
  node: QuestionEvidenceMapNode,
  x: number,
  y: number,
  onNodeSelect: (node: QuestionEvidenceMapNode) => void,
  selectedNodeId: string | null,
  dimmed: boolean
): EvidenceFlowNode {
  return {
    id: node.id,
    type: "evidence",
    position: { x, y },
    data: {
      dimmed,
      kind: node.kind,
      mapNode: node,
      onSelect: onNodeSelect,
      selected: selectedNodeId === node.id,
    },
  };
}

function evidenceFlowEdge(
  edge: QuestionEvidenceMapEdge,
  selectedNodeId: string | null
): Edge {
  const isInteraction = edge.kind === "mentions_in_interaction_section";
  const isTerminology = edge.kind === "has_terminology_context";
  const isSelectedIncident =
    selectedNodeId && (edge.source === selectedNodeId || edge.target === selectedNodeId);
  const isDimmed = Boolean(selectedNodeId && !isSelectedIncident);
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: "floating",
    animated: isInteraction,
    style: {
      opacity: isDimmed ? 0.25 : 1,
      stroke: isInteraction ? "#371E8F" : isTerminology ? "#d97706" : "#94a3b8",
      strokeWidth: isSelectedIncident ? 2 : isInteraction ? 1.5 : 1,
    },
  };
}

function evidenceMapMiniMapColor(kind: string) {
  const colors: Record<string, string> = {
    question: "#F8FAFC",
    query_concept: "#FFFFFF",
    resolved_medication: "#E8DDF9",
    label_source: "#F8FAFC",
    label_section: "#E2E8F0",
    rxnorm_context: "#FEF3C7",
  };
  return colors[kind] ?? "#F8FAFC";
}

function evidenceMapShortLabel(node: QuestionEvidenceMapNode) {
  if (node.kind === "question") {
    return "Question";
  }
  if (node.kind === "label_source") {
    return node.label.replace(/^Source\s+/i, "Source ");
  }
  if (node.kind === "label_section" && node.section) {
    return displaySectionName(node.section);
  }
  if (node.kind === "resolved_medication") {
    return displayGraphNodeName(node.label);
  }
  return node.label;
}

function evidenceMapSignature(map: QuestionEvidenceMap) {
  return `${map.nodes.map((node) => node.id).join("|")}::${map.edges
    .map((edge) => edge.id)
    .join("|")}`;
}

function evidenceMapNodeClasses(kind: string) {
  const classes: Record<string, string> = {
    question: "border-slate-300 bg-white",
    query_concept: "border-[#C7D2FE] bg-[#EEF2FF]",
    resolved_medication: "border-[#C7B4EF] bg-[#E8DDF9]",
    label_source: "border-[#7DD3FC] bg-[#E0F2FE]",
    label_section: "border-slate-400 bg-slate-300",
    rxnorm_context: "border-amber-300 bg-amber-100",
  };
  return classes[kind] ?? "border-slate-200 bg-white";
}

function displayEvidenceMapNodeKind(node: QuestionEvidenceMapNode) {
  if (node.role) {
    return displayMentionRole(node.role);
  }
  const labels: Record<string, string> = {
    question: "Question",
    query_concept: "Question concept",
    resolved_medication: "Medication",
    label_source: "Label source",
    label_section: "Label section",
    rxnorm_context: "Terminology context",
  };
  return labels[node.kind] ?? sentenceCase(node.kind.replaceAll("_", " "));
}
