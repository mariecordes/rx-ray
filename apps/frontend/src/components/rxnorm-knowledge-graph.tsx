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
import type { Simulation } from "d3-force";
import { Info, Maximize2, Minus, Plus } from "lucide-react";
import type { MouseEvent, PointerEvent, WheelEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { CardTitle } from "@/components/ui/card";
import { DrugDossier, RxNormConcept, RxNormEdge } from "@/lib/types";

const GRAPH_WIDTH = 1180;
const GRAPH_HEIGHT = 1180;
const MAX_VISUAL_NODES = 80;
const DEFAULT_DISPLAYED_EDGES = 100;
const MAX_DISPLAYED_EDGES = 400;
const MIN_ZOOM = 0.42;
const MAX_ZOOM = 2;
const FOCUS_ZOOM = 1.55;
const TYPE_CLUSTER_STRENGTH = 0.035;

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

function displayTtyCode(tty?: string | null) {
  const normalizedTty = tty?.toUpperCase();
  if (!normalizedTty) {
    return "Type";
  }
  if (["BN", "IN", "MIN", "PIN"].includes(normalizedTty)) {
    return getTtyStyle(normalizedTty).label;
  }
  return normalizedTty;
}

function ttyBadgeTitle(tty?: string | null) {
  const label = getTtyStyle(tty).label;
  const code = tty?.toUpperCase();
  if (!code || displayTtyCode(tty) === label) {
    return label;
  }
  return `${code}: ${label}`;
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
  return {
    title: displayNodeName(node.name),
    body: `Type: ${style.label}\nRXCUI: ${node.rxcui}`,
  };
}

function edgeTooltip(edge: RxNormEdge) {
  return {
    title: `${displayNodeName(edge.target_name)} ${humanizeRelation(
      edge.relation
    )} ${displayNodeName(edge.source_name)}`,
  };
}

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

type VisualNode = RxNormConcept & {
  depthLevel: number;
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
  edges: RxNormEdge[],
  edgeLimit: number
) {
  const nodeMap = buildNodeMap(nodes);
  const centerEdges = centerRxcui
    ? edges.filter(
        (edge) =>
          edge.source_rxcui === centerRxcui || edge.target_rxcui === centerRxcui
      )
    : [];
  const selectedIds = new Set<string>();
  if (centerRxcui) {
    selectedIds.add(centerRxcui);
  }

  const visualEdges: RxNormEdge[] = [];
  const centerEdgeLimit = Math.max(24, Math.floor(edgeLimit * 0.35));
  for (const edge of centerEdges) {
    if (visualEdges.length >= centerEdgeLimit) {
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
    if (visualEdges.length >= edgeLimit) {
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

  const depthLevelsByRxcui = buildDepthLevels(centerRxcui, visualEdges);
  const visualNodes: VisualNode[] = Array.from(selectedIds)
    .map((rxcui) => nodeMap.get(rxcui))
    .filter((node): node is RxNormConcept => Boolean(node))
    .map((node) => ({
      ...node,
      depthLevel: depthLevelsByRxcui.get(node.rxcui) ?? 2,
    }));

  return { visualEdges, visualNodes };
}

function buildDepthLevels(centerRxcui: string | null, edges: RxNormEdge[]) {
  const depthLevelsByRxcui = new Map<string, number>();
  if (!centerRxcui) {
    return depthLevelsByRxcui;
  }

  const neighborsByRxcui = new Map<string, Set<string>>();
  for (const edge of edges) {
    const sourceNeighbors =
      neighborsByRxcui.get(edge.source_rxcui) ?? new Set<string>();
    sourceNeighbors.add(edge.target_rxcui);
    neighborsByRxcui.set(edge.source_rxcui, sourceNeighbors);

    const targetNeighbors =
      neighborsByRxcui.get(edge.target_rxcui) ?? new Set<string>();
    targetNeighbors.add(edge.source_rxcui);
    neighborsByRxcui.set(edge.target_rxcui, targetNeighbors);
  }

  depthLevelsByRxcui.set(centerRxcui, 0);
  const queue = [centerRxcui];
  for (let index = 0; index < queue.length; index += 1) {
    const rxcui = queue[index];
    const nextDepth = (depthLevelsByRxcui.get(rxcui) ?? 0) + 1;
    for (const neighbor of neighborsByRxcui.get(rxcui) ?? []) {
      if (depthLevelsByRxcui.has(neighbor)) {
        continue;
      }
      depthLevelsByRxcui.set(neighbor, nextDepth);
      queue.push(neighbor);
    }
  }

  return depthLevelsByRxcui;
}

function computeLayout(
  centerRxcui: string | null,
  visualNodes: VisualNode[],
  visualEdges: RxNormEdge[]
) {
  const simulationNodes = visualNodes.map((node, index) => {
    const angle = (2 * Math.PI * index) / Math.max(visualNodes.length, 1);
    const radius = initialRadiusForDepth(node.depthLevel);
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

  const simulation = createRxNormSimulation(simulationNodes, links)
    .stop();

  for (let tick = 0; tick < 260; tick += 1) {
    simulation.tick();
  }

  return new Map(
    simulationNodes.map((node) => [
      node.rxcui,
      {
        ...node,
        x: node.x ?? GRAPH_WIDTH / 2,
        y: node.y ?? GRAPH_HEIGHT / 2,
      },
    ])
  );
}

function createRxNormSimulation(nodes: ForceNode[], links: ForceLink[]) {
  return forceSimulation<ForceNode>(nodes)
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
          return rxNormLinkDistance(source, target);
        })
        .strength(0.34)
    )
    .force("charge", forceManyBody().strength(-310))
    .force(
      "clusterX",
      forceX<ForceNode>((node) => typeClusterPoint(node).x).strength(
        TYPE_CLUSTER_STRENGTH
      )
    )
    .force(
      "clusterY",
      forceY<ForceNode>((node) => typeClusterPoint(node).y).strength(
        TYPE_CLUSTER_STRENGTH
      )
    )
    .force(
      "collide",
      forceCollide((node) => {
        return nodeRadius(node as ForceNode) + 10;
      })
    )
    .force("center", forceCenter(GRAPH_WIDTH / 2, GRAPH_HEIGHT / 2));
}

function rxNormLinkDistance(source: VisualNode, target: VisualNode) {
  const shallowestDepth = Math.min(source.depthLevel, target.depthLevel);
  const deepestDepth = Math.max(source.depthLevel, target.depthLevel);

  if (shallowestDepth === 0) {
    return 138;
  }
  if (deepestDepth >= 3) {
    return 58;
  }
  if (deepestDepth === 2) {
    return 72;
  }
  return 88;
}

function typeClusterPoint(node: Pick<VisualNode, "depthLevel" | "tty">) {
  if (node.depthLevel === 0) {
    return { x: GRAPH_WIDTH / 2, y: GRAPH_HEIGHT / 2 };
  }

  const code = (node.tty ?? "").toUpperCase();
  const clusters: Record<string, { x: number; y: number }> = {
    IN: { x: GRAPH_WIDTH * 0.28, y: GRAPH_HEIGHT * 0.42 },
    PIN: { x: GRAPH_WIDTH * 0.28, y: GRAPH_HEIGHT * 0.42 },
    MIN: { x: GRAPH_WIDTH * 0.28, y: GRAPH_HEIGHT * 0.58 },
    BN: { x: GRAPH_WIDTH * 0.72, y: GRAPH_HEIGHT * 0.42 },
    SBDC: { x: GRAPH_WIDTH * 0.72, y: GRAPH_HEIGHT * 0.42 },
    SBDF: { x: GRAPH_WIDTH * 0.72, y: GRAPH_HEIGHT * 0.5 },
    SBDFP: { x: GRAPH_WIDTH * 0.72, y: GRAPH_HEIGHT * 0.5 },
    SBDG: { x: GRAPH_WIDTH * 0.72, y: GRAPH_HEIGHT * 0.58 },
    SBD: { x: GRAPH_WIDTH * 0.72, y: GRAPH_HEIGHT * 0.58 },
    SCDC: { x: GRAPH_WIDTH * 0.5, y: GRAPH_HEIGHT * 0.25 },
    SCDF: { x: GRAPH_WIDTH * 0.5, y: GRAPH_HEIGHT * 0.28 },
    SCDFP: { x: GRAPH_WIDTH * 0.5, y: GRAPH_HEIGHT * 0.28 },
    SCDG: { x: GRAPH_WIDTH * 0.5, y: GRAPH_HEIGHT * 0.75 },
    SCDGP: { x: GRAPH_WIDTH * 0.5, y: GRAPH_HEIGHT * 0.75 },
    SCD: { x: GRAPH_WIDTH * 0.5, y: GRAPH_HEIGHT * 0.72 },
  };

  return (
    clusters[code] ?? {
      x: GRAPH_WIDTH * (node.depthLevel === 1 ? 0.42 : 0.58),
      y: GRAPH_HEIGHT * (node.depthLevel === 1 ? 0.45 : 0.55),
    }
  );
}

function initialRadiusForDepth(depthLevel: number) {
  if (depthLevel === 0) {
    return 96;
  }
  if (depthLevel === 1) {
    return 260;
  }
  if (depthLevel === 2) {
    return 380;
  }
  return Math.min(520, 380 + (depthLevel - 2) * 80);
}

function nodeRadius(node: Pick<VisualNode, "depthLevel">) {
  if (node.depthLevel === 0) {
    return 24;
  }
  if (node.depthLevel === 1) {
    return 14;
  }
  if (node.depthLevel === 2) {
    return 12;
  }
  return 8;
}

function fitGraphToView(nodes: LayoutPoint[]) {
  if (nodes.length === 0) {
    return { pan: { x: 0, y: 0 }, zoom: 1 };
  }

  let minX = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;

  for (const node of nodes) {
    const radius = nodeRadius(node) + 28;
    const x = node.x ?? GRAPH_WIDTH / 2;
    const y = node.y ?? GRAPH_HEIGHT / 2;
    minX = Math.min(minX, x - radius);
    maxX = Math.max(maxX, x + radius);
    minY = Math.min(minY, y - radius);
    maxY = Math.max(maxY, y + radius);
  }

  const graphWidth = Math.max(1, maxX - minX);
  const graphHeight = Math.max(1, maxY - minY);
  const zoom = Math.max(
    MIN_ZOOM,
    Math.min(
      1,
      Math.min(GRAPH_WIDTH / graphWidth, GRAPH_HEIGHT / graphHeight)
    )
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

type LayoutPoint = VisualNode & {
  x: number;
  y: number;
};

function trimEdge(
  source: LayoutPoint,
  target: LayoutPoint,
  sourceRadius: number,
  targetRadius: number
) {
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const distance = Math.hypot(dx, dy) || 1;
  const unitX = dx / distance;
  const unitY = dy / distance;
  return {
    x1: source.x + unitX * (sourceRadius + 2),
    y1: source.y + unitY * (sourceRadius + 2),
    x2: target.x - unitX * (targetRadius + 2),
    y2: target.y - unitY * (targetRadius + 2),
  };
}

export function RxNormKnowledgeGraph({
  dossier,
  onSelectedNodeChange,
  variant = "card",
}: {
  dossier: DrugDossier;
  onSelectedNodeChange?: (node: RxNormConcept | null) => void;
  variant?: "card" | "embedded";
}) {
  const [selectedRxcui, setSelectedRxcui] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<{
    title: string;
    body?: string;
    x: number;
    y: number;
  } | null>(null);
  const [displayedEdges, setDisplayedEdges] = useState(DEFAULT_DISPLAYED_EDGES);
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set());
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [panDrag, setPanDrag] = useState<{
    x: number;
    y: number;
    startPanX: number;
    startPanY: number;
    moved: boolean;
  } | null>(null);
  const [nodeDrag, setNodeDrag] = useState<string | null>(null);
  const [simulationNodeMap, setSimulationNodeMap] = useState<
    Map<string, LayoutPoint>
  >(new Map());
  const simulationRef = useRef<Simulation<ForceNode, ForceLink> | null>(null);
  const latestNodesRef = useRef<ForceNode[]>([]);
  const graphFrameRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const edges = dossier.rxnorm_neighborhood.edges;
  const nodes = dossier.rxnorm_neighborhood.nodes;
  const centerRxcui = dossier.resolved_drug?.rxcui ?? null;
  const edgeLimit = Math.min(displayedEdges, MAX_DISPLAYED_EDGES, edges.length);
  const { visualEdges, visualNodes } = useMemo(
    () => buildVisualGraph(centerRxcui, nodes, edges, edgeLimit),
    [centerRxcui, edgeLimit, edges, nodes]
  );
  const layoutNodes = useMemo(
    () => computeLayout(centerRxcui, visualNodes, visualEdges),
    [centerRxcui, visualEdges, visualNodes]
  );
  const positionedNodes = simulationNodeMap.size ? simulationNodeMap : layoutNodes;
  useEffect(() => {
    const simulationNodes: ForceNode[] = Array.from(layoutNodes.values()).map(
      (node) => ({ ...node })
    );
    latestNodesRef.current = simulationNodes;
    setSimulationNodeMap(
      new Map(simulationNodes.map((node) => [node.rxcui, node as LayoutPoint]))
    );

    const links: ForceLink[] = visualEdges.map((edge) => ({
      source: edge.target_rxcui,
      target: edge.source_rxcui,
    }));

    let animationFrame: number | null = null;
    const simulation = createRxNormSimulation(simulationNodes, links).on(
      "tick",
      () => {
        latestNodesRef.current = simulationNodes;
        if (animationFrame !== null) {
          return;
        }
        animationFrame = window.requestAnimationFrame(() => {
          setSimulationNodeMap(
            new Map(
              simulationNodes.map((node) => [node.rxcui, node as LayoutPoint])
            )
          );
          animationFrame = null;
        });
      }
    );
    simulationRef.current = simulation;

    return () => {
      simulation.stop();
      simulationRef.current = null;
      if (animationFrame !== null) {
        window.cancelAnimationFrame(animationFrame);
      }
    };
  }, [layoutNodes, visualEdges]);
  const visualRxcuis = useMemo(
    () => visualNodes.map((node) => node.rxcui),
    [visualNodes]
  );
  const filteredRxcuis = useMemo(() => {
    if (selectedTypes.size === 0) {
      return visualRxcuis;
    }
    return visualRxcuis.filter((rxcui) => {
      if (rxcui === centerRxcui || rxcui === selectedRxcui) {
        return true;
      }
      const tty = positionedNodes.get(rxcui)?.tty;
      return tty ? selectedTypes.has(tty.toUpperCase()) : false;
    });
  }, [centerRxcui, positionedNodes, selectedRxcui, selectedTypes, visualRxcuis]);
  const filteredRxcuiSet = useMemo(
    () => new Set(filteredRxcuis),
    [filteredRxcuis]
  );
  const filteredEdges = useMemo(() => {
    return visualEdges.filter(
      (edge) =>
        filteredRxcuiSet.has(edge.source_rxcui) &&
        filteredRxcuiSet.has(edge.target_rxcui)
    );
  }, [filteredRxcuiSet, visualEdges]);
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
    for (const edge of filteredEdges) {
      if (edge.source_rxcui === selectedRxcui) {
        ids.add(edge.target_rxcui);
      }
      if (edge.target_rxcui === selectedRxcui) {
        ids.add(edge.source_rxcui);
      }
    }
    return ids;
  }, [filteredEdges, selectedRxcui]);
  const positionedNodeList = useMemo(
    () =>
      filteredRxcuis
        .map((rxcui) => positionedNodes.get(rxcui))
        .filter((node): node is LayoutPoint => Boolean(node)),
    [filteredRxcuis, positionedNodes]
  );
  const layoutNodeList = useMemo(
    () =>
      filteredRxcuis
        .map((rxcui) => layoutNodes.get(rxcui))
        .filter((node): node is LayoutPoint => Boolean(node)),
    [filteredRxcuis, layoutNodes]
  );
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
  function toggleNodeType(tty: string) {
    setSelectedTypes((current) => {
      const next = new Set(current);
      if (next.has(tty)) {
        next.delete(tty);
      } else {
        next.add(tty);
      }
      return next;
    });
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

  function handleWheel(event: WheelEvent<SVGSVGElement>) {
    event.preventDefault();
    const svg = svgRef.current;
    if (!svg) {
      return;
    }
    const bounds = svg.getBoundingClientRect();
    const viewX = ((event.clientX - bounds.left) / bounds.width) * GRAPH_WIDTH;
    const viewY = ((event.clientY - bounds.top) / bounds.height) * GRAPH_HEIGHT;
    const graphX = (viewX - pan.x) / zoom;
    const graphY = (viewY - pan.y) / zoom;
    const nextZoom = Math.max(
      MIN_ZOOM,
      Math.min(MAX_ZOOM, zoom * (event.deltaY > 0 ? 0.9 : 1.1))
    );
    setZoom(nextZoom);
    setPan({
      x: viewX - graphX * nextZoom,
      y: viewY - graphY * nextZoom,
    });
  }

  function setBoundedZoom(value: number) {
    setZoom(Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, value)));
  }

  function resetView() {
    const fittedView = fitGraphToView(positionedNodeList);
    setZoom(fittedView.zoom);
    setPan(fittedView.pan);
  }

  useEffect(() => {
    const fittedView = fitGraphToView(layoutNodeList);
    setZoom(fittedView.zoom);
    setPan(fittedView.pan);
  }, [layoutNodeList]);

  function selectGraphNode(rxcui: string | null) {
    setSelectedRxcui(rxcui);
    onSelectedNodeChange?.(rxcui ? positionedNodes.get(rxcui) ?? null : null);
  }

  function handleCanvasPointerDown(event: PointerEvent<SVGSVGElement>) {
    setPanDrag({
      x: event.clientX,
      y: event.clientY,
      startPanX: pan.x,
      startPanY: pan.y,
      moved: false,
    });
  }

  function handleNodePointerDown(
    event: PointerEvent<SVGGElement>,
    rxcui: string
  ) {
    event.stopPropagation();
    const simulationNode = latestNodesRef.current.find(
      (node) => node.rxcui === rxcui
    );
    if (simulationNode) {
      simulationNode.fx = simulationNode.x;
      simulationNode.fy = simulationNode.y;
    }
    simulationRef.current?.alphaTarget(0.25).restart();
    setNodeDrag(rxcui);
  }

  function focusNode(rxcui: string) {
    const node = positionedNodes.get(rxcui);
    if (!node) {
      return;
    }
    selectGraphNode(rxcui);
    setBoundedZoom(FOCUS_ZOOM);
    setPan({
      x: GRAPH_WIDTH / 2 - node.x * FOCUS_ZOOM,
      y: GRAPH_HEIGHT / 2 - node.y * FOCUS_ZOOM,
    });
  }

  function handlePointerMove(event: PointerEvent<SVGSVGElement>) {
    if (nodeDrag) {
      const point = screenToGraph(event.clientX, event.clientY);
      const simulationNode = latestNodesRef.current.find(
        (node) => node.rxcui === nodeDrag
      );
      if (simulationNode) {
        simulationNode.fx = point.x;
        simulationNode.fy = point.y;
        simulationRef.current?.alphaTarget(0.25).restart();
      }
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
      const deltaX = event.clientX - panDrag.x;
      const deltaY = event.clientY - panDrag.y;
      setPan({
        x: panDrag.startPanX + deltaX * scaleX,
        y: panDrag.startPanY + deltaY * scaleY,
      });
      if (!panDrag.moved && Math.hypot(deltaX, deltaY) > 4) {
        setPanDrag({ ...panDrag, moved: true });
      }
    }
  }

  function handlePointerUp() {
    if (panDrag && !panDrag.moved && !nodeDrag) {
      selectGraphNode(null);
    }
    if (nodeDrag) {
      const simulationNode = latestNodesRef.current.find(
        (node) => node.rxcui === nodeDrag
      );
      if (simulationNode) {
        simulationNode.fx = undefined;
        simulationNode.fy = undefined;
      }
      simulationRef.current?.alphaTarget(0);
    }
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

  function updateTooltip(
    event: MouseEvent<SVGElement>,
    content: { title: string; body?: string }
  ) {
    const frame = graphFrameRef.current;
    if (!frame) {
      return;
    }
    const bounds = frame.getBoundingClientRect();
    const rawX = event.clientX - bounds.left + 14;
    const rawY = event.clientY - bounds.top + 14;
    setTooltip({
      ...content,
      x: Math.min(rawX, Math.max(12, bounds.width - 300)),
      y: Math.min(rawY, Math.max(12, bounds.height - 120)),
    });
  }

  return (
    <section
      className={
        variant === "card"
          ? "rounded-lg border border-slate-200 bg-white shadow-sm"
          : undefined
      }
    >
      <div
        className={
          variant === "embedded"
            ? "border-t border-slate-200 p-0 pt-6"
            : "border-b border-slate-100 p-4"
        }
      >
        <div>
          <div className="flex items-center gap-2">
            <CardTitle>Drug Network</CardTitle>
            <InfoTooltip text="The drug network uses RxNorm, a public medication terminology, to show relationships between medication concepts such as ingredients, brands, dose forms, and related products. For large drug networks, the app may return only the first requested set of relationships, so additional RxNorm relationships may exist beyond what is shown." />
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            Explore how the matched drug connects to related medication
            concepts.
          </p>
        </div>
      </div>
      <div className={variant === "embedded" ? "space-y-4 p-0 pt-4" : "space-y-4 p-4"}>
        {edges.length === 0 ? (
          <p className="text-sm text-slate-600">
            No relationship data returned.
          </p>
        ) : (
          <div className="grid items-stretch gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
            <div
              ref={graphFrameRef}
              className="relative h-[700px] overflow-hidden rounded-md border border-slate-200 bg-white"
            >
              <svg
                ref={svgRef}
                viewBox={`0 0 ${GRAPH_WIDTH} ${GRAPH_HEIGHT}`}
                className="h-full w-full cursor-grab touch-none"
                role="img"
                aria-label="Local drug relationship network"
                onPointerDown={handleCanvasPointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                onPointerLeave={handlePointerUp}
                onWheel={handleWheel}
              >
                <defs>
                  <marker
                    id="arrow"
                    markerHeight="5"
                    markerWidth="5"
                    orient="auto"
                    refX="5"
                    refY="2.5"
                  >
                    <path d="M0,0 L5,2.5 L0,5 Z" fill="context-stroke" />
                  </marker>
                </defs>
                <g transform={`translate(${pan.x} ${pan.y}) scale(${zoom})`}>
                {filteredEdges.map((edge) => {
                  const source = positionedNodes.get(edge.target_rxcui);
                  const target = positionedNodes.get(edge.source_rxcui);
                  if (!source || !target) {
                    return null;
                  }
                  const trimmed = trimEdge(
                    source,
                    target,
                    nodeRadius(source),
                    nodeRadius(target)
                  );
                  const tooltipText = edgeTooltip(edge);
                  const touchesCenter =
                    edge.source_rxcui === centerRxcui ||
                    edge.target_rxcui === centerRxcui;
                  const incident = edgeIsIncident(edge);
                  return (
                    <g key={`${edge.source_rxcui}-${edge.relation}-${edge.target_rxcui}`}>
                      <line
                        x1={trimmed.x1}
                        x2={trimmed.x2}
                        y1={trimmed.y1}
                        y2={trimmed.y2}
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
                        x1={trimmed.x1}
                        x2={trimmed.x2}
                        y1={trimmed.y1}
                        y2={trimmed.y2}
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
                        strokeWidth={incident ? 1.8 : touchesCenter ? 1.5 : 1.15}
                        markerEnd={incident ? "url(#arrow)" : undefined}
                        pointerEvents="none"
                      />
                    </g>
                  );
                })}
                {filteredRxcuis.map((rxcui) => {
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
                  const label = shortLabel(
                    displayNodeName(point.name),
                    isCenter ? 28 : 20
                  );
                  const labelWidth = Math.min(
                    isCenter ? 190 : 150,
                    Math.max(48, label.length * 6.4 + 14)
                  );
                  const labelY = point.y + radius + 15;
                  return (
                    <g
                      key={rxcui}
                      className="cursor-grab"
                      onClick={() =>
                        selectGraphNode(selectedRxcui === rxcui ? null : rxcui)
                      }
                      onDoubleClick={() => focusNode(rxcui)}
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
                      {isSelected ? (
                        <circle
                          cx={point.x}
                          cy={point.y}
                          r={radius + 5}
                          fill="none"
                          stroke={style.stroke}
                          strokeOpacity="0.32"
                          strokeWidth="3"
                        />
                      ) : null}
                      <circle
                        cx={point.x}
                        cy={point.y}
                        r={radius}
                        fill={isSelected ? style.stroke : style.fill}
                        fillOpacity={isSelected ? 0.18 : 1}
                        stroke={
                          isSelected || (isCenter && !selectedRxcui)
                            ? style.stroke
                            : style.stroke
                        }
                        strokeWidth={
                          isSelected || (isCenter && !selectedRxcui) ? 2.5 : 2
                        }
                        opacity={
                          selectedRxcui && !isHighlighted && !isCenter ? 0.26 : 1
                        }
                      />
                      {showLabel ? (
                        <g
                          className="pointer-events-none"
                          opacity={
                            selectedRxcui && !isHighlighted && !isCenter ? 0.32 : 1
                          }
                        >
                          <rect
                            x={point.x - labelWidth / 2}
                            y={labelY - 12}
                            width={labelWidth}
                            height="17"
                            rx="4"
                            fill="white"
                            fillOpacity="0.88"
                            stroke="#e2e8f0"
                            strokeOpacity="0.8"
                          />
                          <text
                            x={point.x}
                            y={labelY}
                            className="fill-slate-800 text-[11px] font-semibold"
                            textAnchor="middle"
                          >
                            {label}
                          </text>
                        </g>
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
                  <div className="font-semibold text-slate-900">
                    {tooltip.title}
                  </div>
                  {tooltip.body ? <div>{tooltip.body}</div> : null}
                </div>
              ) : null}
            </div>
            <div className="space-y-3">
              <div className="rounded-md border border-slate-200 bg-white p-3">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div className="text-xs font-medium uppercase text-slate-500">
                    Graph controls
                  </div>
                  <div className="flex gap-1">
                    <button
                      type="button"
                      aria-label="Zoom out"
                      className="grid size-8 place-items-center rounded-md border border-slate-200 text-slate-700 hover:bg-slate-50"
                      onClick={() => setBoundedZoom(zoom - 0.18)}
                    >
                      <Minus className="size-4" />
                    </button>
                    <button
                      type="button"
                      aria-label="Reset graph view"
                      className="grid size-8 place-items-center rounded-md border border-slate-200 text-slate-700 hover:bg-slate-50"
                      onClick={resetView}
                    >
                      <Maximize2 className="size-4" />
                    </button>
                    <button
                      type="button"
                      aria-label="Zoom in"
                      className="grid size-8 place-items-center rounded-md border border-slate-200 text-slate-700 hover:bg-slate-50"
                      onClick={() => setBoundedZoom(zoom + 0.18)}
                    >
                      <Plus className="size-4" />
                    </button>
                  </div>
                </div>
                <label className="flex flex-col gap-2 text-xs text-slate-600">
                  <span className="flex items-center justify-between gap-3">
                    <span>Displayed relationships</span>
                    <span className="font-medium text-slate-900">
                      {edgeLimit}
                    </span>
                  </span>
                  <input
                    min={20}
                    max={MAX_DISPLAYED_EDGES}
                    step={10}
                    type="range"
                    value={displayedEdges}
                    onChange={(event) =>
                      setDisplayedEdges(Number(event.target.value))
                    }
                    className="w-full accent-slate-900"
                  />
                </label>
              </div>

              <div className="h-32 rounded-md border border-slate-200 bg-slate-50 p-3">
                <div className="text-xs font-medium uppercase text-slate-500">
                  Selected node
                </div>
                {selectedNode ? (
                  <div className="mt-2 grid h-[88px] grid-rows-[48px_24px] gap-2">
                    <div className="line-clamp-2 min-h-12 font-semibold leading-6 text-slate-950">
                      {displayNodeName(selectedNode.name)}
                    </div>
                    <div className="flex min-w-0 gap-2">
                      <Badge className="max-w-[56%] shrink-0 truncate overflow-hidden">
                        RXCUI {selectedNode.rxcui}
                      </Badge>
                      <span className="group relative inline-flex shrink-0">
                        <Badge
                          className="border"
                          style={{
                            backgroundColor: getTtyStyle(selectedNode.tty).fill,
                            borderColor: getTtyStyle(selectedNode.tty).stroke,
                            color: getTtyStyle(selectedNode.tty).stroke,
                          }}
                        >
                          {displayTtyCode(selectedNode.tty)}
                        </Badge>
                        <span className="pointer-events-none absolute bottom-full left-0 z-20 mb-2 hidden w-max max-w-60 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs leading-5 text-slate-700 shadow-lg group-hover:block">
                          {ttyBadgeTitle(selectedNode.tty)}
                        </span>
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="mt-2 grid h-[88px] grid-rows-[48px_24px] gap-2">
                    <p className="line-clamp-2 min-h-12 text-sm leading-6 text-slate-600">
                      Showing a local network around the searched concept.
                    </p>
                    <div className="flex min-w-0 gap-2 overflow-hidden">
                      {searchedNode ? (
                        <Badge className="min-w-0 max-w-full truncate">
                          Search: {displayNodeName(searchedNode.name)}
                        </Badge>
                      ) : null}
                    </div>
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
                    onClick={() => setSelectedTypes(new Set())}
                  >
                    Clear
                  </button>
                </div>
                <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
                  {visibleNodeTypes.map((tty) => {
                    const style = getTtyStyle(tty);
                    const isActive = selectedTypes.has(tty.toUpperCase());
                    return (
                      <button
                        key={tty}
                        type="button"
                        className={[
                          "flex min-w-0 items-center gap-2 rounded-md border px-2 py-1 text-left transition",
                          isActive
                            ? "border-slate-400 bg-slate-100 text-slate-950"
                            : "border-transparent text-slate-700 hover:border-slate-200 hover:bg-slate-50",
                        ].join(" ")}
                        style={{ fontSize: "12px", lineHeight: "13px" }}
                        onClick={() => toggleNodeType(tty.toUpperCase())}
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
                </div>
              </div>
              <p className="text-xs leading-5 text-slate-500">
                Showing {filteredEdges.length} of {edges.length} returned
                relationships
                {selectedTypes.size > 0 ? " after type filtering" : ""}. Hover
                over a line to see the relationship. Double-click a node to
                focus it.
              </p>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
