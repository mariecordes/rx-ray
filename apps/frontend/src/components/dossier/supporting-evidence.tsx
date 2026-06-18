"use client";

import {
  type RefObject,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  ChevronDown,
  ChevronRight,
  Database,
  ExternalLink,
  Info,
  Loader2,
} from "lucide-react";

import {
  QuestionRxNormNetworkGraph,
  RxNormKnowledgeGraph,
} from "@/components/rxnorm-knowledge-graph";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import {
  contextSpecificBadgeClasses,
  displaySectionName,
  hasOpenFdaProductMetadata,
  interactionSpecificBadgeClasses,
  metadataUnavailableLabel,
  nodeSpecificBadgeClasses,
  nodeSpecificClasses,
  searchSourceClasses,
  searchSpecificBadgeClasses,
  sourceNumberBadgeClasses,
  sourceSelectionClasses,
  unidentifiedDrugLabel,
} from "@/components/dossier/display";
import {
  buildDisplayEvidenceModel,
  DisplayEvidenceModel,
  DisplayLabelSection,
  DisplaySourceRecord,
  groupLabelSectionsBySource,
} from "@/components/dossier/evidence-model";
import {
  buildLabelSourceProfile,
  hasLabelSourceProfileDetails,
  LabelSourceProfileDetails,
} from "@/components/dossier/label-source-profile";
import {
  DrugDossier,
  EvidenceCitation,
  IngredientFallbackEvidence,
  OpenFDALabelEvidence,
  OpenFDALabelRecord,
  QuestionRxNormNetwork,
  RxNormConcept,
  SecondaryDrugEvidence,
} from "@/lib/types";
import {
  displayBrandName,
  displayGenericName,
  displayGraphNodeName,
  displayMentionRole,
  displayRxNormType,
  primaryValue,
} from "@/lib/format";
import { requestJsonWithRetry } from "@/lib/api-client";
import { cn } from "@/lib/utils";

const productContextSections = new Set([
  "active_ingredient",
  "inactive_ingredient",
  "description",
  "purpose",
  "dosage_and_administration",
]);
const productContextSection = "product_context";

export function SupportingEvidence({
  dossier,
  drugLabelsNavRef,
  drugNetworkNavRef,
  evidenceNavRef,
  highlightCitation,
  highlightRxcui,
  questionRxNormNetwork,
  secondaryEvidence,
  onCitationHandled,
  onRxcuiHandled,
}: {
  dossier: DrugDossier;
  drugLabelsNavRef?: RefObject<HTMLDivElement | null>;
  drugNetworkNavRef?: RefObject<HTMLDivElement | null>;
  evidenceNavRef?: RefObject<HTMLDivElement | null>;
  highlightCitation: EvidenceCitation | null;
  highlightRxcui: string | null;
  questionRxNormNetwork: QuestionRxNormNetwork;
  secondaryEvidence: SecondaryDrugEvidence[];
  onCitationHandled: () => void;
  onRxcuiHandled: () => void;
}) {
  const evidenceTabs = useMemo(
    () => buildSupportingEvidenceTabs(dossier, secondaryEvidence),
    [dossier, secondaryEvidence]
  );
  const [activeTabKey, setActiveTabKey] = useState("network");

  useEffect(() => {
    setActiveTabKey("network");
  }, [dossier, secondaryEvidence]);

  useEffect(() => {
    if (!highlightCitation) {
      return;
    }
    const matchingTab = supportingEvidenceTabForCitation(
      evidenceTabs,
      highlightCitation
    );
    if (matchingTab) {
      setActiveTabKey(matchingTab.key);
    }
  }, [evidenceTabs, highlightCitation]);

  useEffect(() => {
    if (!highlightRxcui) {
      return;
    }
    const matchingTab = evidenceTabs.find((tab) => tab.rxcui === highlightRxcui);
    if (matchingTab) {
      setActiveTabKey(matchingTab.key);
    }
    onRxcuiHandled();
  }, [evidenceTabs, highlightRxcui, onRxcuiHandled]);

  const highlightedTab = highlightCitation
    ? supportingEvidenceTabForCitation(evidenceTabs, highlightCitation)
    : null;
  const activeTab =
    highlightedTab ??
    evidenceTabs.find((tab) => tab.key === activeTabKey) ??
    evidenceTabs[0];
  const activeTabHighlightCitation =
    highlightedTab && highlightedTab.key === activeTab.key
      ? highlightCitation
      : null;

  return (
    <div ref={evidenceNavRef} className="scroll-mt-6">
      <Card className="border-[#C7B4EF] shadow-md">
        <CardHeader>
          <CardTitle>Supporting Evidence</CardTitle>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            Inspect the retrieved dossier behind the generated response.
          </p>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="flex flex-wrap items-end gap-1">
            {evidenceTabs.map((tab) => (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTabKey(tab.key)}
                className={cn(
                  "rounded-t-md px-4 py-2 text-sm font-semibold shadow-sm",
                  tab.kind === "network"
                    ? activeTab.key === tab.key
                      ? "bg-[#21408F] text-white"
                      : "border border-[#B5E3F2] bg-[#DEE9FC] text-[#155E75]"
                    : activeTab.key === tab.key
                      ? "bg-[#371E8F] text-white"
                      : "border border-[#E9DDF8] bg-[#F7F3FD] text-[#371E8F]"
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div className="-mt-5 rounded-b-md rounded-tr-md border border-slate-200 bg-white p-4 shadow-sm">
            {activeTab.kind === "network" ? (
              <div
                ref={(el) => {
                  if (drugNetworkNavRef) drugNetworkNavRef.current = el;
                }}
              >
                <QuestionRxNormNetworkGraph
                  network={questionRxNormNetwork}
                  variant="embedded"
                  tabRxcuis={
                    new Set(
                      evidenceTabs
                        .map((tab) => tab.rxcui)
                        .filter((rxcui): rxcui is string => Boolean(rxcui))
                    )
                  }
                  onOpenTab={(rxcui) => {
                    const tab = evidenceTabs.find((t) => t.rxcui === rxcui);
                    if (tab) setActiveTabKey(tab.key);
                  }}
                  onOpenDossier={(name) => {
                    const params = new URLSearchParams({ drug: name, auto: "1" });
                    window.open(
                      `/dossier?${params.toString()}`,
                      "_blank",
                      "noopener,noreferrer"
                    );
                  }}
                />
              </div>
            ) : activeTab.kind === "primary" ? (
              <DossierResults
                dossier={dossier}
                drugLabelsNavRef={drugLabelsNavRef}
                highlightCitation={activeTabHighlightCitation}
                showGraph={false}
                variant="embedded"
                onCitationHandled={onCitationHandled}
              />
            ) : (
              <SecondaryEvidenceResults
                evidence={activeTab.evidence}
                highlightCitation={activeTabHighlightCitation}
                onCitationHandled={onCitationHandled}
              />
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function supportingEvidenceTabForCitation(
  tabs: SupportingEvidenceTab[],
  citation: EvidenceCitation
) {
  return citation.rxcui
    ? tabs.find((tab) => tab.rxcui === citation.rxcui)
    : tabs.find((tab) => tab.sourceIds.has(citation.source_id));
}

type SupportingEvidenceTab =
  | {
      key: "network";
      kind: "network";
      label: string;
      rxcui?: undefined;
      sourceIds: Set<string>;
    }
  | {
      key: "primary";
      kind: "primary";
      label: string;
      rxcui?: string;
      sourceIds: Set<string>;
    }
  | {
      key: string;
      kind: "secondary";
      label: string;
      rxcui?: string;
      sourceIds: Set<string>;
      evidence: SecondaryDrugEvidence;
    };

function buildSupportingEvidenceTabs(
  dossier: DrugDossier,
  secondaryEvidence: SecondaryDrugEvidence[]
): SupportingEvidenceTab[] {
  const primaryLabel = dossier.resolved_drug
    ? displayGraphNodeName(dossier.resolved_drug.name)
    : "Matched drug";
  return [
    {
      key: "network",
      kind: "network",
      label: "Drug Network",
      sourceIds: new Set(),
    },
    {
      key: "primary",
      kind: "primary",
      label: primaryLabel,
      rxcui: dossier.resolved_drug?.rxcui,
      sourceIds: labelEvidenceSourceIds(dossier.label_evidence ?? null),
    },
    ...secondaryEvidence.map((evidence) => ({
      key: `secondary-${evidence.resolved_concept.rxcui}`,
      kind: "secondary" as const,
      label: displayGraphNodeName(evidence.resolved_concept.name),
      rxcui: evidence.resolved_concept.rxcui,
      sourceIds: labelEvidenceSourceIds(evidence.label_evidence ?? null),
      evidence,
    })),
  ];
}

function labelEvidenceSourceIds(evidence: OpenFDALabelEvidence | null) {
  return new Set(
    (evidence?.label_records ?? [])
      .map((record) => record.source_id)
      .filter((sourceId): sourceId is string => Boolean(sourceId))
  );
}

function SecondaryEvidenceResults({
  evidence,
  highlightCitation,
  onCitationHandled,
}: {
  evidence: SecondaryDrugEvidence;
  highlightCitation: EvidenceCitation | null;
  onCitationHandled?: () => void;
}) {
  const [selectedSection, setSelectedSection] = useState<string | null>(null);
  const [selectedSourceKey, setSelectedSourceKey] = useState<string | null>(null);
  const labelEvidencePanelRef = useRef<HTMLDivElement>(null);
  const labelEvidence = evidence.label_evidence ?? null;
  const displayEvidence = useMemo(
    () => buildDisplayEvidenceModel(labelEvidence, null),
    [labelEvidence]
  );
  const sectionEntries = useMemo(
    () => labelTextSectionEntries(displayEvidence),
    [displayEvidence]
  );
  const activeSection =
    selectedSection &&
    (selectedSection === productContextSection ||
      displayEvidence.sections[selectedSection])
      ? selectedSection
      : sectionEntries[0]?.[0] ?? null;
  const activeTexts = activeSection
    ? displayEvidence.sections[activeSection] ?? []
    : [];

  useEffect(() => {
    const firstSection = firstLabelTextSection(labelEvidence);
    setSelectedSection(firstSection ?? null);
    setSelectedSourceKey(null);
  }, [labelEvidence]);

  useEffect(() => {
    if (!highlightCitation) {
      return;
    }
    if (!labelEvidenceSourceIds(labelEvidence).has(highlightCitation.source_id)) {
      return;
    }
    if (displayEvidence.sections[highlightCitation.section]) {
      setSelectedSection(highlightCitation.section);
    }
    const matchingSource = displayEvidence.records.find(
      (source) => source.record.source_id === highlightCitation.source_id
    );
    setSelectedSourceKey(matchingSource?.key ?? null);
    window.requestAnimationFrame(() => {
      labelEvidencePanelRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
      onCitationHandled?.();
    });
  }, [displayEvidence, highlightCitation, labelEvidence, onCitationHandled]);

  function toggleSourceSelection(sourceKey?: string | null) {
    if (!sourceKey) {
      return;
    }
    setSelectedSourceKey((current) =>
      current === sourceKey ? null : sourceKey
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <SecondaryEvidenceOverview evidence={evidence} />
      <LabelEvidencePanel
        ref={labelEvidencePanelRef}
        activeSection={activeSection}
        activeTexts={activeTexts}
        displayEvidence={displayEvidence}
        labelEvidence={labelEvidence}
        nodeEvidenceError={null}
        nodeLabelEvidence={null}
        isNodeEvidenceLoading={false}
        sectionEntries={sectionEntries}
        selectedGraphNode={null}
        selectedSourceKey={selectedSourceKey}
        showGraphContext={false}
        variant="embedded"
        onSelectSection={setSelectedSection}
        onSelectSource={toggleSourceSelection}
        onSelectSourceFromStrip={toggleSourceSelection}
      />
    </div>
  );
}

function SecondaryEvidenceOverview({
  evidence,
}: {
  evidence: SecondaryDrugEvidence;
}) {
  const labelCount = evidence.label_evidence?.labels_found ?? 0;
  const hasLabels = labelCount > 0;
  return (
    <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
      <div>
        <div className="text-sm text-slate-500">Matched drug</div>
        <div className="mt-2 space-y-2">
          <div className="text-xl font-semibold text-slate-950">
            {displayGraphNodeName(evidence.resolved_concept.name)}
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge>RXCUI {evidence.resolved_concept.rxcui}</Badge>
            <Badge>{displayRxNormType(evidence.resolved_concept.tty)}</Badge>
            <Badge>{displayMentionRole(evidence.role)}</Badge>
          </div>
        </div>
      </div>
      <div className="self-start rounded-md border border-slate-200 bg-slate-50 p-3 text-left">
        <div className="flex items-center justify-between gap-3">
          <div className="text-sm font-semibold text-slate-950">Drug Labels</div>
          <Badge
            style={{
              backgroundColor: hasLabels ? "#ecfdf5" : "#fffbeb",
              borderColor: hasLabels ? "#a7f3d0" : "#fde68a",
              color: hasLabels ? "#065f46" : "#92400e",
            }}
          >
            {hasLabels ? "Available" : "Not found"}
          </Badge>
        </div>
        <div className="mt-2 text-sm leading-5 text-slate-600">
          {hasLabels
            ? `${labelCount} label source${labelCount === 1 ? "" : "s"} available`
            : "No compact label sources were retrieved for this mentioned medication."}
        </div>
      </div>
    </section>
  );
}

export function DossierResults({
  dossier,
  drugLabelsNavRef,
  drugNetworkNavRef,
  highlightCitation = null,
  showGraph = true,
  onCitationHandled,
  variant = "cards",
}: {
  dossier: DrugDossier;
  drugLabelsNavRef?: RefObject<HTMLDivElement | null>;
  drugNetworkNavRef?: RefObject<HTMLDivElement | null>;
  highlightCitation?: EvidenceCitation | null;
  showGraph?: boolean;
  onCitationHandled?: () => void;
  variant?: "cards" | "embedded";
}) {
  const [selectedSection, setSelectedSection] = useState<string | null>(null);
  const [selectedSourceKey, setSelectedSourceKey] = useState<string | null>(null);
  const [selectedGraphNode, setSelectedGraphNode] =
    useState<RxNormConcept | null>(null);
  const [nodeLabelEvidence, setNodeLabelEvidence] =
    useState<OpenFDALabelEvidence | null>(null);
  const [isNodeEvidenceLoading, setIsNodeEvidenceLoading] = useState(false);
  const [nodeEvidenceError, setNodeEvidenceError] = useState<string | null>(null);
  const drugNetworkPanelRef = useRef<HTMLDivElement>(null);
  const labelEvidencePanelRef = useRef<HTMLDivElement>(null);
  const nodeEvidenceRequestRef = useRef(0);

  const labelEvidence = dossier.label_evidence ?? null;
  const displayEvidence = useMemo(
    () => buildDisplayEvidenceModel(labelEvidence, nodeLabelEvidence),
    [labelEvidence, nodeLabelEvidence]
  );
  const sectionEntries = useMemo(
    () => labelTextSectionEntries(displayEvidence),
    [displayEvidence]
  );
  const activeSection =
    selectedSection &&
    (selectedSection === productContextSection ||
      displayEvidence.sections[selectedSection])
      ? selectedSection
      : sectionEntries[0]?.[0] ?? null;
  const activeTexts: DisplayLabelSection[] = activeSection
    ? displayEvidence.sections[activeSection] ?? []
    : [];

  useEffect(() => {
    const firstSection = firstLabelTextSection(dossier.label_evidence ?? null);
    setSelectedSection(firstSection ?? null);
    setSelectedSourceKey(null);
    setSelectedGraphNode(null);
    setNodeLabelEvidence(null);
    setNodeEvidenceError(null);
    setIsNodeEvidenceLoading(false);
    nodeEvidenceRequestRef.current += 1;
  }, [dossier]);

  useEffect(() => {
    if (!highlightCitation) {
      return;
    }
    const matchingSource = displayEvidence.records.find(
      (source) => source.record.source_id === highlightCitation.source_id
    );
    if (!matchingSource) {
      return;
    }
    if (displayEvidence.sections[highlightCitation.section]) {
      setSelectedSection(highlightCitation.section);
    }
    setSelectedSourceKey(matchingSource.key);
    window.requestAnimationFrame(() => {
      labelEvidencePanelRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
      onCitationHandled?.();
    });
  }, [displayEvidence, highlightCitation, onCitationHandled]);

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
  }

  function scrollToSection(ref: RefObject<HTMLDivElement | null>) {
    ref.current?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
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
      const payload = await requestJsonWithRetry<OpenFDALabelEvidence>(
        "/api/label-evidence",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            rxcui: node.rxcui,
            name: node.name,
            limit: 3,
          }),
        },
        {
          userMessage:
            "The app could not reliably load selected-node label evidence after several retries.",
        }
      );

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
    <div
      className={cn(
        "flex flex-col",
        variant === "embedded" ? "gap-6" : "gap-5"
      )}
    >
      <Overview
        dossier={dossier}
        showNetwork={showGraph}
        variant={variant}
        onJumpToLabels={() => scrollToSection(labelEvidencePanelRef)}
        onJumpToNetwork={() => scrollToSection(drugNetworkPanelRef)}
      />
      {showGraph ? (
        <div
          ref={(element) => {
            drugNetworkPanelRef.current = element;
            if (drugNetworkNavRef) {
              drugNetworkNavRef.current = element;
            }
          }}
        >
          <RxNormKnowledgeGraph
            key={dossier.resolved_drug?.rxcui ?? dossier.query}
            dossier={dossier}
            variant={variant === "embedded" ? "embedded" : "card"}
            onSelectedNodeChange={handleSelectedGraphNodeChange}
          />
        </div>
      ) : null}
      <LabelEvidencePanel
        ref={labelEvidencePanelRef}
        navRef={drugLabelsNavRef}
        activeSection={activeSection}
        activeTexts={activeTexts}
        displayEvidence={displayEvidence}
        labelEvidence={labelEvidence}
        ingredientFallback={dossier.ingredient_fallback}
        nodeEvidenceError={nodeEvidenceError}
        nodeLabelEvidence={nodeLabelEvidence}
        isNodeEvidenceLoading={isNodeEvidenceLoading}
        sectionEntries={sectionEntries}
        selectedGraphNode={selectedGraphNode}
        selectedSourceKey={selectedSourceKey}
        showGraphContext={showGraph}
        variant={variant}
        onSelectSection={setSelectedSection}
        onSelectSource={toggleSourceSelection}
        onSelectSourceFromStrip={selectSourceFromStrip}
      />
    </div>
  );
}

export function EmptyState() {
  return (
    <div className="grid min-h-[320px] place-items-center rounded-lg border border-dashed border-slate-300 bg-white">
      <div className="max-w-md px-6 text-center">
        <Database className="mx-auto mb-3 size-8 text-slate-400" />
        <p className="text-sm text-slate-600">No dossier loaded.</p>
      </div>
    </div>
  );
}

function Overview({
  dossier,
  onJumpToLabels,
  onJumpToNetwork,
  showNetwork = true,
  variant = "cards",
}: {
  dossier: DrugDossier;
  onJumpToLabels: () => void;
  onJumpToNetwork: () => void;
  showNetwork?: boolean;
  variant?: "cards" | "embedded";
}) {
  const networkCount = dossier.rxnorm_neighborhood.edges.length;
  const labelCount = dossier.label_evidence?.labels_found ?? 0;
  const hasNetwork = networkCount > 0;
  const hasLabels = labelCount > 0;

  return (
    <section
      className={cn(
        variant === "cards" && "rounded-lg border border-slate-200 bg-white shadow-sm"
      )}
    >
      {variant === "cards" ? (
        <CardHeader>
          <CardTitle>Overview</CardTitle>
        </CardHeader>
      ) : null}
      <div
        className={cn(
          "grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]",
          variant === "cards" && "p-4"
        )}
      >
        <div>
          <div className="text-sm text-slate-500">Matched drug</div>
          {dossier.resolved_drug ? (
            <div className="mt-2 space-y-2">
              <div className="text-xl font-semibold text-slate-950">
                {displayGraphNodeName(dossier.resolved_drug.name)}
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge>RXCUI {dossier.resolved_drug.rxcui}</Badge>
                <Badge>{displayRxNormType(dossier.resolved_drug.tty)}</Badge>
                {variant === "embedded" ? (
                  <Badge>{displayMentionRole("primary_drug")}</Badge>
                ) : null}
              </div>
            </div>
          ) : (
            <div className="mt-2 text-sm text-slate-600">
              No matching drug concept was found for this search.
            </div>
          )}
        </div>
        {showNetwork ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <OverviewJumpCard
              description={
                hasNetwork
                  ? `${networkCount} relationship${
                      networkCount === 1 ? "" : "s"
                    } available`
                  : "No relationship data returned"
              }
              isAvailable={hasNetwork}
              label="Drug Network"
              onClick={onJumpToNetwork}
            />
            <OverviewJumpCard
              description={
                hasLabels
                  ? `${labelCount} label source${labelCount === 1 ? "" : "s"} available`
                  : "No public label sources returned"
              }
              isAvailable={hasLabels}
              label="Drug Labels"
              onClick={onJumpToLabels}
            />
          </div>
        ) : (
          <OverviewJumpCard
            description={
              hasLabels
                ? `${labelCount} label source${labelCount === 1 ? "" : "s"} available`
                : "No public label sources returned"
            }
            isAvailable={hasLabels}
            label="Drug Labels"
            onClick={onJumpToLabels}
          />
        )}
      </div>
    </section>
  );
}

function OverviewJumpCard({
  description,
  isAvailable,
  label,
  onClick,
}: {
  description: string;
  isAvailable: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="block self-start rounded-md border border-slate-200 bg-slate-50 p-3 text-left transition hover:border-slate-300 hover:bg-white"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-semibold text-slate-950">{label}</div>
        <Badge
          style={{
            backgroundColor: isAvailable ? "#ecfdf5" : "#fffbeb",
            borderColor: isAvailable ? "#a7f3d0" : "#fde68a",
            color: isAvailable ? "#065f46" : "#92400e",
          }}
        >
          {isAvailable ? "Available" : "Not found"}
        </Badge>
      </div>
      <div className="mt-2 text-sm leading-5 text-slate-600">{description}</div>
    </button>
  );
}

function ingredientFallbackNames(evidence: OpenFDALabelEvidence): string[] {
  const names = evidence.summary_metadata?.generic_names ?? [];
  return Array.from(new Set(names.map((name) => displayGenericName(name))));
}

function labelTextSectionEntries(
  displayEvidence: DisplayEvidenceModel
): [string, DisplayLabelSection[]][] {
  const entries = Object.entries(displayEvidence.sections).filter(
    ([section]) => !productContextSections.has(section)
  );
  if (displayEvidence.records.some((source) => hasProductContext(source.record))) {
    return [[productContextSection, []], ...entries];
  }
  return entries;
}

function firstLabelTextSection(evidence: OpenFDALabelEvidence | null) {
  if ((evidence?.label_records ?? []).some(hasProductContext)) {
    return productContextSection;
  }
  return Object.keys(evidence?.sections ?? {}).find(
    (section) => !productContextSections.has(section)
  );
}

function LabelEvidencePanel({
  ref,
  navRef,
  activeSection,
  activeTexts,
  displayEvidence,
  labelEvidence,
  ingredientFallback,
  nodeEvidenceError,
  nodeLabelEvidence,
  isNodeEvidenceLoading,
  sectionEntries,
  selectedGraphNode,
  selectedSourceKey,
  showGraphContext = true,
  variant = "cards",
  onSelectSection,
  onSelectSource,
  onSelectSourceFromStrip,
}: {
  ref: RefObject<HTMLDivElement | null>;
  navRef?: RefObject<HTMLDivElement | null>;
  activeSection: string | null;
  activeTexts: DisplayLabelSection[];
  displayEvidence: DisplayEvidenceModel;
  labelEvidence: OpenFDALabelEvidence | null;
  ingredientFallback?: IngredientFallbackEvidence[];
  nodeEvidenceError: string | null;
  nodeLabelEvidence: OpenFDALabelEvidence | null;
  isNodeEvidenceLoading: boolean;
  sectionEntries: [string, DisplayLabelSection[]][];
  selectedGraphNode: RxNormConcept | null;
  selectedSourceKey: string | null;
  showGraphContext?: boolean;
  variant?: "cards" | "embedded";
  onSelectSection: (section: string) => void;
  onSelectSource: (sourceKey?: string | null) => void;
  onSelectSourceFromStrip: (sourceKey?: string | null) => void;
}) {
  const records = displayEvidence.records;
  // When a specific concept had no labels and we broadened to multiple active
  // ingredients, group the source cards under each ingredient so it's clear
  // which labels describe which ingredient.
  const sourceIdToIngredient = useMemo(() => {
    const map = new Map<string, string>();
    for (const bundle of ingredientFallback ?? []) {
      for (const record of bundle.label_evidence.label_records) {
        if (record.source_id) {
          map.set(record.source_id, bundle.ingredient.name);
        }
      }
    }
    return map;
  }, [ingredientFallback]);
  const groupSourcesByIngredient = (ingredientFallback?.length ?? 0) > 1;
  const evidenceCardsRef = useRef<HTMLDivElement>(null);
  const evidenceCardRefs = useRef<Map<string, HTMLElement>>(new Map());
  const [expandedSourceKeys, setExpandedSourceKeys] = useState<Set<string>>(
    new Set()
  );
  const [expandedEvidenceKeys, setExpandedEvidenceKeys] = useState<Set<string>>(
    new Set()
  );
  const groupedActiveTexts = useMemo(
    () => groupLabelSectionsBySource(activeSection, activeTexts, displayEvidence),
    [activeSection, activeTexts, displayEvidence]
  );
  const sectionTabEntries = useMemo(
    () =>
      sectionEntries.map(([section, texts]) => ({
        section,
        count:
          section === productContextSection
            ? records.filter((source) => hasProductContext(source.record)).length
            : groupLabelSectionsBySource(section, texts, displayEvidence).length,
      })),
    [displayEvidence, records, sectionEntries]
  );

  function handleSourceStripClick(sourceKey: string) {
    onSelectSourceFromStrip(sourceKey);
    window.requestAnimationFrame(() => {
      scrollToEvidenceCardForSource(sourceKey);
    });
  }

  function evidenceCardRefKey(sourceKey: string | null, entryKey: string) {
    return `${sourceKey ?? "unknown"}::${entryKey}`;
  }

  function setEvidenceCardRef(
    sourceKey: string | null,
    entryKey: string,
    element: HTMLElement | null
  ) {
    const refKey = evidenceCardRefKey(sourceKey, entryKey);
    if (element) {
      evidenceCardRefs.current.set(refKey, element);
    } else {
      evidenceCardRefs.current.delete(refKey);
    }
  }

  const scrollToEvidenceCardForSource = useCallback((sourceKey: string) => {
    if (activeSection === productContextSection) {
      const element = evidenceCardRefs.current.get(
        evidenceCardRefKey(sourceKey, productContextCardKey(sourceKey))
      );
      if (element) {
        element.scrollIntoView({
          behavior: "smooth",
          block: "center",
        });
        return;
      }
    }
    const match = groupedActiveTexts.find((entry) => entry.sourceKey === sourceKey);
    const element = match
      ? evidenceCardRefs.current.get(evidenceCardRefKey(sourceKey, match.key))
      : null;
    if (element) {
      element.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
      return;
    }
    evidenceCardsRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
  }, [activeSection, groupedActiveTexts]);

  function toggleEvidenceExpansion(key: string) {
    setExpandedEvidenceKeys((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  function toggleSourceProfile(sourceKey: string) {
    setExpandedSourceKeys((current) => {
      const next = new Set(current);
      if (next.has(sourceKey)) {
        next.delete(sourceKey);
      } else {
        next.add(sourceKey);
      }
      return next;
    });
  }

  function toggleSourceProfileFromSection(sourceKey?: string | null) {
    if (!sourceKey) {
      return;
    }
    onSelectSource(sourceKey);
    setExpandedSourceKeys((current) => {
      const next = new Set(current);
      if (next.has(sourceKey)) {
        next.delete(sourceKey);
      } else {
        next.add(sourceKey);
      }
      return next;
    });
  }

  useEffect(() => {
    setExpandedSourceKeys(new Set());
  }, [labelEvidence, nodeLabelEvidence]);

  useEffect(() => {
    if (!selectedSourceKey) {
      return;
    }
    window.requestAnimationFrame(() => {
      scrollToEvidenceCardForSource(selectedSourceKey);
    });
  }, [scrollToEvidenceCardForSource, selectedSourceKey]);

  const renderSourceCard = (source: DisplaySourceRecord) => {
    const brandName = primaryValue(source.record.brand_names);
    const genericName = primaryValue(source.record.generic_names);
    const manufacturerName = primaryValue(source.record.manufacturer_names);
    const profile = buildLabelSourceProfile(source.record);
    const hasProfileDetails = hasLabelSourceProfileDetails(profile);
    const isProfileExpanded = expandedSourceKeys.has(source.key);
    const hasProductMetadata = hasOpenFdaProductMetadata(source.record);
    const isSelected = source.key === selectedSourceKey;
    const sourceClasses = isSelected
      ? sourceSelectionClasses
      : source.isSelectedNodeOnly
        ? nodeSpecificClasses
        : searchSourceClasses;
    return (
      <div
        key={source.key}
        role="button"
        tabIndex={0}
        onClick={() => handleSourceStripClick(source.key)}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            handleSourceStripClick(source.key);
          }
        }}
        className={cn(
          "w-full cursor-pointer rounded-md border p-2 text-left transition",
          sourceClasses
        )}
        style={{ fontSize: "14px", lineHeight: "20px" }}
      >
        <div className="mb-1 flex flex-wrap items-center gap-1.5">
          <Badge className={sourceNumberBadgeClasses}>
            Label {source.sourceNumber}
          </Badge>
          {!source.isSelectedNodeOnly ? (
            <Badge className={searchSpecificBadgeClasses}>
              Medication-specific
            </Badge>
          ) : null}
          {source.isSelectedNodeOnly || source.isSelectedNodeMatch ? (
            <Badge className={nodeSpecificBadgeClasses}>Node-specific</Badge>
          ) : null}
          {source.isInteractionTargeted ? (
            <Badge className={interactionSpecificBadgeClasses}>
              Interaction-specific
            </Badge>
          ) : null}
          {source.isContextTargeted ? (
            <Badge className={contextSpecificBadgeClasses}>
              Context-specific
            </Badge>
          ) : null}
        </div>
        <div className="mt-1.5 truncate font-medium text-slate-900">
          {brandName
            ? displayBrandName(brandName)
            : hasProductMetadata
              ? "Brand unavailable"
              : unidentifiedDrugLabel}
        </div>
        {hasProductMetadata ? (
          <>
            <div className="mt-0.5 truncate text-slate-600">
              {genericName
                ? displayGenericName(genericName)
                : "Generic unavailable"}
            </div>
            <div className="mt-0.5 truncate text-slate-500">
              {manufacturerName ?? "Manufacturer unavailable"}
            </div>
          </>
        ) : (
          <div className="mt-0.5 truncate text-slate-600">
            {metadataUnavailableLabel}
          </div>
        )}
        {hasProfileDetails ? (
          <div className="mt-2 border-t border-slate-200/70 pt-2">
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                toggleSourceProfile(source.key);
              }}
              className="inline-flex items-center gap-1 text-xs font-medium uppercase text-slate-500 hover:text-slate-900"
            >
              {isProfileExpanded ? (
                <ChevronDown className="size-3.5" />
              ) : (
                <ChevronRight className="size-3.5" />
              )}
              Details
            </button>
            {isProfileExpanded ? (
              <LabelSourceProfileDetails profile={profile} />
            ) : null}
          </div>
        ) : null}
      </div>
    );
  };

  return (
    <div
      ref={(element) => {
        ref.current = element;
        if (navRef) {
          navRef.current = element;
        }
      }}
    >
      <section
        className={cn(
          variant === "cards" && "rounded-lg border border-slate-200 bg-white shadow-sm"
        )}
      >
        <div
          className={cn(
            variant === "cards" && "border-b border-slate-200 p-4",
            variant === "embedded" && "border-t border-slate-200 p-0 pt-6"
          )}
        >
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <CardTitle>Drug Labels</CardTitle>
              <InfoTooltip text="Drug labels come from public FDA label data. They can include warnings, uses, interactions, pregnancy or lactation information, and other text from medication labels." />
            </div>
            <p className="mt-1 text-sm leading-6 text-slate-500">
              Public drug-label text retrieved for this medication
              {showGraphContext
                ? ", with graph selections used to highlight or add more specific label records."
                : "."}
            </p>
            {labelEvidence &&
            labelEvidence.labels_found > 0 &&
            labelEvidence.retrieval_mode === "ingredient_fallback" ? (
              <p className="mx-auto flex w-full items-center gap-2 mt-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm leading-5 text-amber-900">
                <Info className="size-4 shrink-0" />
                <span>
                  No product-specific labels were found for this medication.
                  Showing labels for its active ingredient
                  {ingredientFallbackNames(labelEvidence).length === 1 ? "" : "s"}
                  {ingredientFallbackNames(labelEvidence).length
                    ? ` (${ingredientFallbackNames(labelEvidence).join(", ")})`
                    : ""}
                  , which may describe other formulations than the one asked
                  about.
                </span>
              </p>
            ) : null}
          </div>
        </div>
        <div
          className={cn(
            "space-y-5",
            variant === "cards" ? "p-4 pt-5" : "p-0 pt-4"
          )}
        >
          {showGraphContext ? (
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
          ) : null}

          <div className="grid gap-4 xl:grid-cols-[minmax(240px,0.32fr)_minmax(0,1fr)]">
            <aside className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  <div className="text-xs font-medium uppercase text-slate-500">
                    Sources
                  </div>
                  <span className="group relative inline-flex">
                    <Info className="size-3.5 text-slate-400" />
                    <span className="pointer-events-none absolute left-0 top-full z-20 mt-2 hidden w-64 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs normal-case leading-5 text-slate-700 shadow-lg group-hover:block">
                      Each source card shows the drug brand name, generic drug
                      name, and manufacturer name. Expand Details for product
                      metadata.
                    </span>
                  </span>
                </div>
                <Badge className="bg-white text-slate-700">
                  {records.length}
                </Badge>
              </div>
              {records.length === 0 ? (
                <p className="text-sm text-slate-600">
                  No label records returned.
                </p>
              ) : groupSourcesByIngredient ? (
                <div className="space-y-3">
                  {(ingredientFallback ?? []).map((bundle) => {
                    const groupSources = records.filter(
                      (source) =>
                        sourceIdToIngredient.get(
                          source.record.source_id ?? ""
                        ) === bundle.ingredient.name
                    );
                    if (groupSources.length === 0) {
                      return null;
                    }
                    return (
                      <div key={bundle.ingredient.rxcui} className="space-y-2">
                        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
                          <span className="truncate">
                            {displayGenericName(bundle.ingredient.name)}
                          </span>
                          <span className="font-normal text-slate-400">
                            {groupSources.length} label
                            {groupSources.length === 1 ? "" : "s"}
                          </span>
                        </div>
                        {groupSources.map(renderSourceCard)}
                      </div>
                    );
                  })}
                  {records.some(
                    (source) =>
                      !sourceIdToIngredient.has(source.record.source_id ?? "")
                  ) ? (
                    <div className="space-y-2">
                      {records
                        .filter(
                          (source) =>
                            !sourceIdToIngredient.has(
                              source.record.source_id ?? ""
                            )
                        )
                        .map(renderSourceCard)}
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="space-y-2">{records.map(renderSourceCard)}</div>
              )}
            </aside>

            <section className="min-w-0">
              {sectionEntries.length === 0 ? (
                <p className="text-sm text-slate-600">
                  No public label sections returned.
                </p>
              ) : (
                <div className="flex flex-col gap-4">
                  <div className="flex flex-wrap gap-2">
                    {sectionTabEntries.map(({ section, count }) => {
                      const isProductContext =
                        section === productContextSection;
                      const isActive = activeSection === section;
                      return (
                        <Button
                          key={section}
                          type="button"
                          variant={isActive ? "primary" : "secondary"}
                          className={cn(
                            isProductContext &&
                              "border hover:brightness-[0.98]"
                          )}
                          style={
                            isProductContext
                              ? {
                                  backgroundColor: isActive
                                    ? "#3C796E"
                                    : "#E1F6EF",
                                  borderColor: isActive
                                    ? "#3C796E"
                                    : "#3C796E",
                                  color: isActive ? "#ffffff" : "#3C796E",
                                }
                              : undefined
                          }
                          onClick={() => onSelectSection(section)}
                        >
                          {displaySectionName(section)}
                          <span className="text-xs opacity-75">
                            {count}
                          </span>
                        </Button>
                      );
                    })}
                  </div>

                  <div ref={evidenceCardsRef} className="space-y-3">
                    {activeSection === productContextSection ? (
                      <ProductContextCards
                        records={records}
                        selectedSourceKey={selectedSourceKey}
                        setEvidenceCardRef={setEvidenceCardRef}
                        onSelectSource={onSelectSource}
                      />
                    ) : (
                    groupedActiveTexts.map((entry) => {
                      const sourceKey = entry.sourceKey;
                      const source = entry.source;
                      const sourceProfile = source
                        ? buildLabelSourceProfile(source.record)
                        : null;
                      const hasSourceProfileDetails = sourceProfile
                        ? hasLabelSourceProfileDetails(sourceProfile)
                        : false;
                      const brandName = primaryValue(
                        source?.record.brand_names
                      );
                      const manufacturerName = primaryValue(
                        source?.record.manufacturer_names
                      );
                      const hasProductMetadata = hasOpenFdaProductMetadata(
                        source?.record
                      );
                      const isSelected =
                        Boolean(sourceKey) && sourceKey === selectedSourceKey;
                      const evidenceClasses = isSelected
                        ? sourceSelectionClasses
                        : source?.isSelectedNodeOnly
                          ? nodeSpecificClasses
                          : "border-slate-200 bg-slate-50 hover:border-slate-300 hover:bg-white";
                      const isExpanded = expandedEvidenceKeys.has(entry.key);
                      const canExpand = entry.text.length > 420;
                      return (
                        <article
                          key={entry.key}
                          ref={(element) =>
                            setEvidenceCardRef(sourceKey ?? null, entry.key, element)
                          }
                          role="button"
                          tabIndex={0}
                          onClick={() => onSelectSource(sourceKey)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              onSelectSource(sourceKey);
                            }
                          }}
                          className={cn(
                            "w-full cursor-pointer rounded-md border p-3 text-left transition",
                            evidenceClasses
                          )}
                        >
                          <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                            {source ? (
                              <span
                                className={cn(
                                  "inline-flex items-center rounded-md border px-2 py-0.5 font-medium",
                                  sourceNumberBadgeClasses
                                )}
                              >
                                Label {source.sourceNumber}
                              </span>
                            ) : (
                              <Badge>Label unknown</Badge>
                            )}
                            {brandName ? (
                              <span>{displayBrandName(brandName)}</span>
                            ) : source && !hasProductMetadata ? (
                              <span>{unidentifiedDrugLabel}</span>
                            ) : null}
                            {manufacturerName ? (
                              <span>· {manufacturerName}</span>
                            ) : source && !hasProductMetadata ? (
                              <span>· {metadataUnavailableLabel}</span>
                            ) : null}
                          </div>
                          <p
                            className={cn(
                              "whitespace-pre-wrap text-sm leading-6 text-slate-800",
                              canExpand && !isExpanded
                                ? "max-h-24 overflow-hidden"
                                : ""
                            )}
                          >
                            {entry.text}
                          </p>
                          {canExpand || (source && hasSourceProfileDetails) ? (
                            <div className="mt-3 flex flex-wrap items-center gap-5">
                              {canExpand ? (
                                <button
                                  type="button"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    toggleEvidenceExpansion(entry.key);
                                  }}
                                  className="font-medium uppercase tracking-wide text-slate-500 underline underline-offset-2 hover:text-cyan-700"
                                  style={{
                                    fontSize: "12px",
                                    lineHeight: "14px",
                                  }}
                                >
                                  {isExpanded ? "Show less" : "Show more"}
                                </button>
                              ) : null}
                              {source && hasSourceProfileDetails ? (
                                <button
                                  type="button"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    toggleSourceProfileFromSection(sourceKey);
                                  }}
                                  className="font-medium uppercase tracking-wide text-slate-500 underline underline-offset-2 hover:text-slate-900"
                                  style={{
                                    fontSize: "12px",
                                    lineHeight: "14px",
                                  }}
                                >
                                  Label details
                                </button>
                              ) : null}
                            </div>
                          ) : null}
                        </article>
                      );
                    })
                    )}
                  </div>
                </div>
              )}
            </section>
          </div>
        </div>
      </section>
    </div>
  );
}

function ProductContextCards({
  records,
  selectedSourceKey,
  setEvidenceCardRef,
  onSelectSource,
}: {
  records: DisplaySourceRecord[];
  selectedSourceKey: string | null;
  setEvidenceCardRef: (
    sourceKey: string | null,
    entryKey: string,
    element: HTMLElement | null
  ) => void;
  onSelectSource: (sourceKey?: string | null) => void;
}) {
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());
  const [expandedFields, setExpandedFields] = useState<Set<string>>(new Set());
  const contextRecords = records.filter((source) =>
    hasProductContext(source.record)
  );

  if (contextRecords.length === 0) {
    return null;
  }

  function toggleCard(key: string) {
    setExpandedCards((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  function toggleField(key: string) {
    setExpandedFields((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  return (
    <>
      {contextRecords.map((source) => {
        const context = productContextForRecord(source.record);
        const sourceKey = source.key;
        const cardKey = productContextCardKey(sourceKey);
        const isSelected = sourceKey === selectedSourceKey;
        const isExpanded = expandedCards.has(cardKey);
        const brandName = primaryValue(source.record.brand_names);
        const manufacturerName = primaryValue(source.record.manufacturer_names);
        const hasProductMetadata = hasOpenFdaProductMetadata(source.record);
        const canExpand = (context.description?.length ?? 0) > 420;
        const visibleDescription = context.description;
        return (
          <article
            key={cardKey}
            ref={(element) =>
              setEvidenceCardRef(sourceKey, cardKey, element)
            }
            role="button"
            tabIndex={0}
            onClick={() => onSelectSource(sourceKey)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelectSource(sourceKey);
              }
            }}
            className={cn(
              "w-full cursor-pointer rounded-md border p-3 text-left transition",
              isSelected
                ? sourceSelectionClasses
                : "border-slate-200 bg-slate-50 hover:border-slate-300 hover:bg-white"
            )}
          >
            <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span
                className={cn(
                  "inline-flex items-center rounded-md border px-2 py-0.5 font-medium",
                  sourceNumberBadgeClasses
                )}
              >
                Label {source.sourceNumber}
              </span>
              {brandName ? (
                <span>{displayBrandName(brandName)}</span>
              ) : !hasProductMetadata ? (
                <span>{unidentifiedDrugLabel}</span>
              ) : null}
              {manufacturerName ? (
                <span>· {manufacturerName}</span>
              ) : !hasProductMetadata ? (
                <span>· {metadataUnavailableLabel}</span>
              ) : null}
            </div>
            {context.productName ? (
              <div
                className="mb-2 truncate text-sm font-semibold leading-6 text-slate-900"
                title={context.productNameTitle ?? context.productName}
              >
                {context.productName}
              </div>
            ) : null}
            {visibleDescription ? (
              <p
                className={cn(
                  "whitespace-pre-wrap text-sm leading-6 text-slate-800",
                  canExpand && !isExpanded ? "max-h-24 overflow-hidden" : ""
                )}
              >
                {visibleDescription}
              </p>
            ) : null}
            {canExpand ? (
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  toggleCard(cardKey);
                }}
                className="mt-3 font-medium uppercase tracking-wide text-slate-500 underline underline-offset-2 hover:text-cyan-700"
                style={{
                  fontSize: "12px",
                  lineHeight: "14px",
                }}
              >
                {isExpanded ? "Show less" : "Show more"}
              </button>
            ) : null}
            <div className="mt-3 space-y-2">
              {context.fields.map((field) => {
                const fieldKey = productContextFieldKey(cardKey, field.label);
                const isFieldExpanded = expandedFields.has(fieldKey);
                return (
                  <section
                    key={field.label}
                    className="rounded-md border border-slate-200 bg-white/80"
                  >
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        toggleField(fieldKey);
                      }}
                      className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left"
                    >
                      <span className="text-xs font-medium uppercase text-slate-500">
                        {field.label}
                      </span>
                      <span className="flex items-center gap-2 text-xs text-slate-500">
                        {isFieldExpanded ? (
                          <ChevronDown className="size-3.5" />
                        ) : (
                          <ChevronRight className="size-3.5" />
                        )}
                      </span>
                    </button>
                    {isFieldExpanded ? (
                      <div className="border-t border-slate-200 px-3 py-2">
                        <ul className="space-y-2">
                          {field.values.map((value, index) => (
                            <li
                              key={`${field.label}-${index}`}
                              className="whitespace-pre-wrap text-sm leading-6 text-slate-800"
                            >
                              {value}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                  </section>
                );
              })}
            </div>
          </article>
        );
      })}
    </>
  );
}

function productContextCardKey(sourceKey: string) {
  return `product-context-${sourceKey}`;
}

function productContextFieldKey(cardKey: string, label: string) {
  return `${cardKey}-${label}`;
}

function hasProductContext(record: OpenFDALabelRecord) {
  return Boolean(
    record.descriptions.length ||
      record.package_label_principal_display_panels.length ||
      record.active_ingredients.length ||
      record.inactive_ingredients.length ||
      record.purposes.length ||
      record.dosages.length
  );
}

function productContextForRecord(record: OpenFDALabelRecord) {
  const packageDisplayPanel = primaryValue(
    record.package_label_principal_display_panels
  );
  const cleanedPackageDisplayPanel = cleanPackageLabelDisplayPanel(
    packageDisplayPanel
  );
  const productName =
    cleanedPackageDisplayPanel ??
    primaryValue(record.brand_names)?.toUpperCase() ??
    (primaryValue(record.generic_names)
      ? displayGenericName(primaryValue(record.generic_names) ?? "")
      : null);
  const descriptions = uniqueTextValues(
    (record.descriptions ?? []).map(cleanProductContextText)
  );
  const purpose = uniqueTextValues(
    (record.purposes ?? []).map(cleanProductContextText)
  );
  const dosage = uniqueTextValues(
    (record.dosages ?? []).map(cleanProductContextText)
  );
  const activeIngredient = uniqueTextValues(
    (record.active_ingredients?.length
      ? record.active_ingredients
      : record.substance_names) ?? []
  ).map(sentenceForLabel);
  const inactiveIngredient = uniqueTextValues(
    record.inactive_ingredients ?? []
  ).map(sentenceForLabel);

  return {
    productName,
    productNameTitle: cleanedPackageDisplayPanel,
    description: descriptions[0] ?? null,
    fields: [
      { label: "Purpose", values: purpose },
      { label: "Dosage", values: dosage },
      { label: "Active ingredient", values: activeIngredient },
      { label: "Inactive ingredient", values: inactiveIngredient },
    ].filter((field) => field.values.length > 0),
  };
}

function cleanPackageLabelDisplayPanel(value?: string | null) {
  if (!value) {
    return null;
  }
  const cleaned = value
    .replace(/\s+/g, " ")
    .replace(
      /^(package\s*\/?\s*label\s*(?:display panel|[-.\s]*principal display panel)?|principal display panel)\s*[-.:–—]?\s*/i,
      ""
    )
    .replace(/\bNDC\s*[\w-]+/gi, "")
    .replace(/^[^A-Za-z0-9]+/, "")
    .trim();
  if (!cleaned) {
    return null;
  }
  return cleaned;
}

function uniqueTextValues(values: string[]) {
  return Array.from(
    new Set(values.map((value) => value.trim()).filter(Boolean))
  );
}

function sentenceForLabel(value: string) {
  return value.length > 80 ? value : displayGenericName(value);
}

function cleanProductContextText(value: string) {
  return value
    .replace(/\s+/g, " ")
    .replace(
      /^(description|purpose|dosage and administration|active ingredients?|inactive ingredients?)\s*/i,
      ""
    )
    .trim();
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
        Select a node in the drug network above to check whether public labels
        are available for that specific concept.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm leading-6 text-slate-700">
        <Loader2 className="size-4 animate-spin text-slate-500" />
        Looking up labels for{" "}
        <span className="font-bold text-slate-950">
          {displayGraphNodeName(node.name)}
        </span>
        .
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
        <span className="font-bold text-slate-950">
          {displayGraphNodeName(node.name)}
        </span>
        . No specific public labels were found, so the evidence below remains
        tied to the original search.
      </div>
    );
  }

  if (displayEvidence.selectedNodeOnlyCount > 0) {
    const previewLimitReached =
      nodeLabelEvidence?.label_limit !== null &&
      nodeLabelEvidence?.label_limit !== undefined &&
      nodeLabelEvidence.labels_found >= nodeLabelEvidence.label_limit;
    return (
      <GraphSelectionContextLayout
        node={node}
        action={<OpenDossierForNodeButton node={node} />}
      >
        <span>
          Displaying {displayEvidence.selectedNodeOnlyCount} node-specific
          source{displayEvidence.selectedNodeOnlyCount === 1 ? "" : "s"} pinned
          first.
          {previewLimitReached
            ? " This is a compact preview; open the Drug Dossier to retrieve further label evidence."
            : ""}
        </span>
      </GraphSelectionContextLayout>
    );
  }

  if (displayEvidence.selectedNodeMatchCount > 0) {
    return (
      <GraphSelectionContextLayout
        node={node}
        action={
          nodeLabelEvidence && nodeLabelEvidence.labels_found > 0 ? (
            <OpenDossierForNodeButton node={node} />
          ) : null
        }
      >
        <span>
          Its labels match source
          {displayEvidence.selectedNodeMatchCount === 1 ? "" : "s"} already
          returned for the original search.
        </span>
      </GraphSelectionContextLayout>
    );
  }

  return (
    <div className="text-sm leading-6 text-slate-700">
      Selected graph node:{" "}
      <span className="font-bold text-slate-950">
        {displayGraphNodeName(node.name)}
      </span>
      .
    </div>
  );
}

function GraphSelectionContextLayout({
  action,
  children,
  node,
}: {
  action?: React.ReactNode;
  children: React.ReactNode;
  node: RxNormConcept;
}) {
  return (
    <div className="flex flex-col gap-2 text-sm leading-6 text-slate-700 sm:flex-row sm:items-center sm:justify-between">
      <div>
        Selected graph node:{" "}
        <span className="font-bold text-slate-950">
          {displayGraphNodeName(node.name)}
        </span>
        . {children}
      </div>
      {action}
    </div>
  );
}

function OpenDossierForNodeButton({ node }: { node: RxNormConcept }) {
  function handleClick() {
    const params = new URLSearchParams({
      drug: node.name,
      auto: "1",
    });
    window.open(`/dossier?${params.toString()}`, "_blank", "noopener,noreferrer");
  }

  return (
    <Button
      type="button"
      variant="secondary"
      className="w-fit shrink-0 gap-1.5 border-slate-300 bg-white text-xs uppercase tracking-normal text-slate-700 hover:bg-slate-50"
      onClick={handleClick}
    >
      <ExternalLink className="size-3.5" />
      Open Drug Dossier
    </Button>
  );
}
