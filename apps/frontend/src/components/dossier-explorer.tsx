"use client";

import {
  FormEvent,
  type RefObject,
  type ReactNode,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Database,
  FileText,
  Info,
  Loader2,
  Search,
  TriangleAlert,
} from "lucide-react";

import { RxNormKnowledgeGraph } from "@/components/rxnorm-knowledge-graph";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  DrugDossier,
  EvidenceAnswer,
  EvidenceCitation,
  LabelSection,
  OpenFDALabelEvidence,
  OpenFDALabelRecord,
  QueryAnswerResponse,
  QueryUnderstandingResponse,
  RxNormConcept,
} from "@/lib/types";
import { cn } from "@/lib/utils";

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

function primaryValue(values?: string[] | null) {
  if (!values || values.length === 0) {
    return null;
  }
  return values[0];
}

const sourceSelectionClasses =
  "border-[#C7B4EF] bg-[#E8DDF9] shadow-sm hover:border-[#C7B4EF]";
const nodeSpecificClasses =
  "border-[#EACB96] bg-[#FAE8CD] hover:border-[#DDBB7E]";
const searchSourceClasses =
  "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50";
const nodeSpecificBadgeClasses =
  "border-slate-300 bg-slate-100 text-slate-700";
const searchSpecificBadgeClasses =
  "border-slate-300 bg-slate-100 text-slate-700";
const sourceNumberBadgeClasses =
  "border-slate-200 bg-white text-slate-800";

function displayGraphNodeName(name: string) {
  return name.toUpperCase();
}

function displayBrandName(name: string) {
  return name.toUpperCase();
}

function displayGenericName(name: string) {
  return sentenceCase(name);
}

function sentenceCase(value: string) {
  return value
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

const rxNormTypeLabels: Record<string, string> = {
  BN: "Brand",
  BPCK: "Brand Name Pack",
  DF: "Dose Form",
  DFG: "Dose Form Group",
  GPCK: "Generic Pack",
  IN: "Ingredient",
  MIN: "Multiple Ingredients",
  PIN: "Precise Ingredient",
  PSN: "Prescribable Name",
  SBD: "Semantic Branded Drug",
  SBDC: "Semantic Branded Drug Component",
  SBDF: "Semantic Branded Drug Form",
  SBDFP: "Semantic Branded Drug Form Precise",
  SBDG: "Semantic Branded Drug Group",
  SCD: "Semantic Clinical Drug",
  SCDC: "Semantic Clinical Drug Component",
  SCDF: "Semantic Clinical Drug Form",
  SCDFP: "Semantic Clinical Drug Form Precise",
  SCDG: "Semantic Clinical Drug Group",
  SCDGP: "Semantic Clinical Drug Form Group Precise",
  SY: "Synonym",
  TMSY: "Tall Man Lettering Synonym",
};

function displayRxNormType(tty?: string | null) {
  if (!tty) {
    return "Type unknown";
  }
  return rxNormTypeLabels[tty.toUpperCase()] ?? sentenceCase(tty);
}

function displayStateLabel(value: string) {
  return value.replaceAll("_", " ");
}

function citationDisplayLabel(
  citation: EvidenceCitation,
  sourceById: Map<string, OpenFDALabelRecord>
) {
  const source = sourceById.get(citation.source_id);
  const brandName = primaryValue(source?.brand_names);
  const genericName = primaryValue(source?.generic_names);
  const manufacturerName = primaryValue(source?.manufacturer_names);
  const productName = brandName
    ? displayBrandName(brandName)
    : genericName
      ? displayGenericName(genericName)
      : "Label source";
  return [productName, manufacturerName, displaySectionName(citation.section)]
    .filter(Boolean)
    .join(" · ");
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

type DisplayLabelSection = LabelSection & {
  displaySourceKey?: string;
  isSelectedNodeEvidence: boolean;
};

type DisplaySourceRecord = {
  key: string;
  record: OpenFDALabelRecord;
  sourceNumber: number;
  isSelectedNodeMatch: boolean;
  isSelectedNodeOnly: boolean;
};

type DisplayEvidenceModel = {
  records: DisplaySourceRecord[];
  sections: Record<string, DisplayLabelSection[]>;
  sourceByKey: Map<string, DisplaySourceRecord>;
  selectedNodeSourceKeys: Set<string>;
  selectedNodeOnlyCount: number;
  selectedNodeMatchCount: number;
};

type GroupedLabelSection = {
  key: string;
  sourceKey?: string;
  source?: DisplaySourceRecord;
  text: string;
  chunkCount: number;
  isSelectedNodeEvidence: boolean;
};

function recordKey(
  record: OpenFDALabelRecord,
  index: number,
  prefix: "baseline" | "selected"
) {
  return [
    prefix,
    record.source_id,
    record.id,
    record.set_id,
    record.spl_ids[0],
    record.spl_set_ids[0],
    index,
  ]
    .filter(Boolean)
    .join(":");
}

function hasSharedValue(left: string[], right: string[]) {
  if (left.length === 0 || right.length === 0) {
    return false;
  }
  const rightValues = new Set(right);
  return left.some((value) => rightValues.has(value));
}

function recordsMatch(
  baseline: OpenFDALabelRecord,
  selected: OpenFDALabelRecord
) {
  if (baseline.source_id && baseline.source_id === selected.source_id) {
    return true;
  }
  if (baseline.id && baseline.id === selected.id) {
    return true;
  }
  if (baseline.set_id && baseline.set_id === selected.set_id) {
    return true;
  }
  if (hasSharedValue(baseline.spl_ids, selected.spl_ids)) {
    return true;
  }
  return hasSharedValue(baseline.spl_set_ids, selected.spl_set_ids);
}

function buildDisplayEvidenceModel(
  baselineEvidence: OpenFDALabelEvidence | null,
  selectedEvidence: OpenFDALabelEvidence | null
): DisplayEvidenceModel {
  const baselineRecords = baselineEvidence?.label_records ?? [];
  const selectedRecords = selectedEvidence?.label_records ?? [];
  const baselineItems = baselineRecords.map((record, index) => ({
    key: recordKey(record, index, "baseline"),
    record,
    sourceNumber: index + 1,
    isSelectedNodeMatch: false,
    isSelectedNodeOnly: false,
  }));
  const baselineSectionKeyBySourceId = new Map<string, string>();
  for (const item of baselineItems) {
    if (item.record.source_id) {
      baselineSectionKeyBySourceId.set(item.record.source_id, item.key);
    }
  }

  const matchedBaselineKeys = new Set<string>();
  const selectedOnlyItems: DisplaySourceRecord[] = [];
  const selectedSectionKeyBySourceId = new Map<string, string>();

  selectedRecords.forEach((selectedRecord, selectedIndex) => {
    const match = baselineItems.find((item) =>
      recordsMatch(item.record, selectedRecord)
    );
    if (match) {
      matchedBaselineKeys.add(match.key);
      if (selectedRecord.source_id) {
        selectedSectionKeyBySourceId.set(selectedRecord.source_id, match.key);
      }
      return;
    }

    const selectedOnlyItem: DisplaySourceRecord = {
      key: recordKey(selectedRecord, selectedIndex, "selected"),
      record: selectedRecord,
      sourceNumber: 0,
      isSelectedNodeMatch: false,
      isSelectedNodeOnly: true,
    };
    selectedOnlyItems.push(selectedOnlyItem);
    if (selectedRecord.source_id) {
      selectedSectionKeyBySourceId.set(selectedRecord.source_id, selectedOnlyItem.key);
    }
  });

  const records = [
    ...selectedOnlyItems,
    ...baselineItems.map((item) => ({
      ...item,
      isSelectedNodeMatch: matchedBaselineKeys.has(item.key),
    })),
  ].map((item, index) => ({
    ...item,
    sourceNumber: index + 1,
  }));

  const selectedNodeSourceKeys = new Set<string>([
    ...matchedBaselineKeys,
    ...selectedOnlyItems.map((item) => item.key),
  ]);
  const sections: Record<string, DisplayLabelSection[]> = {};

  for (const [section, entries] of Object.entries(
    baselineEvidence?.sections ?? {}
  )) {
    sections[section] = entries.map((entry) => ({
      ...entry,
      displaySourceKey: entry.source_id
        ? baselineSectionKeyBySourceId.get(entry.source_id)
        : undefined,
      isSelectedNodeEvidence: false,
    }));
  }

  for (const [section, entries] of Object.entries(
    selectedEvidence?.sections ?? {}
  )) {
    const selectedOnlyEntries = entries
      .map((entry) => ({
        ...entry,
        displaySourceKey: entry.source_id
          ? selectedSectionKeyBySourceId.get(entry.source_id)
          : undefined,
        isSelectedNodeEvidence: true,
      }))
      .filter(
        (entry) =>
          entry.displaySourceKey &&
          selectedOnlyItems.some((item) => item.key === entry.displaySourceKey)
      );

    if (selectedOnlyEntries.length > 0) {
      sections[section] = [...selectedOnlyEntries, ...(sections[section] ?? [])];
    }
  }

  return {
    records,
    sections,
    sourceByKey: new Map(records.map((item) => [item.key, item])),
    selectedNodeSourceKeys,
    selectedNodeOnlyCount: selectedOnlyItems.length,
    selectedNodeMatchCount: matchedBaselineKeys.size,
  };
}

function groupLabelSectionsBySource(
  section: string | null,
  entries: DisplayLabelSection[],
  displayEvidence: DisplayEvidenceModel
) {
  const groups = new Map<string, GroupedLabelSection>();

  entries.forEach((entry, index) => {
    const sourceKey =
      entry.displaySourceKey ?? `${entry.source_id ?? "unknown"}-${index}`;
    const groupKey = `${section ?? "section"}-${sourceKey}`;
    const existing = groups.get(groupKey);

    if (existing) {
      existing.text = `${existing.text}\n\n${entry.text}`;
      existing.chunkCount += 1;
      existing.isSelectedNodeEvidence =
        existing.isSelectedNodeEvidence || entry.isSelectedNodeEvidence;
      return;
    }

    groups.set(groupKey, {
      key: groupKey,
      sourceKey: entry.displaySourceKey,
      source: entry.displaySourceKey
        ? displayEvidence.sourceByKey.get(entry.displaySourceKey)
        : undefined,
      text: entry.text,
      chunkCount: 1,
      isSelectedNodeEvidence: entry.isSelectedNodeEvidence,
    });
  });

  return Array.from(groups.values());
}

export function DossierExplorer() {
  return <AskQuestionExperience />;
}

export function AskQuestionExperience() {
  const [question, setQuestion] = useState(
    "I take ibuprofen for migraine and want to use tretinoin for acne. I am pregnant."
  );
  const [queryUnderstanding, setQueryUnderstanding] =
    useState<QueryUnderstandingResponse | null>(null);
  const [queryAnswer, setQueryAnswer] = useState<QueryAnswerResponse | null>(null);
  const [isUnderstandingLoading, setIsUnderstandingLoading] = useState(false);
  const [isAnswerLoading, setIsAnswerLoading] = useState(false);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [dossier, setDossier] = useState<DrugDossier | null>(null);
  const [isEvidenceOpen, setIsEvidenceOpen] = useState(false);
  const [highlightCitation, setHighlightCitation] =
    useState<EvidenceCitation | null>(null);
  const supportingEvidenceRef = useRef<HTMLDivElement>(null);

  function handleAnswerCitationClick(citation: EvidenceCitation) {
    setHighlightCitation(citation);
    setIsEvidenceOpen(true);
    window.requestAnimationFrame(() => {
      supportingEvidenceRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  }

  async function handleQuestionSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsUnderstandingLoading(true);
    setIsAnswerLoading(false);
    setQueryError(null);
    setQueryUnderstanding(null);
    setQueryAnswer(null);

    try {
      const understandingResponse = await fetch("/api/query-understanding", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: question,
        }),
      });
      const understandingPayload = await understandingResponse.json();

      if (!understandingResponse.ok) {
        throw new Error(
          understandingPayload.detail ?? "Failed to understand query"
        );
      }

      const understanding = understandingPayload as QueryUnderstandingResponse;
      setQueryUnderstanding(understanding);
      if (understanding.primary_dossier) {
        setDossier(understanding.primary_dossier);
        setIsEvidenceOpen(false);
        setHighlightCitation(null);
      }

      setIsUnderstandingLoading(false);
      setIsAnswerLoading(true);

      const answerResponse = await fetch("/api/query-answer", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: question,
        }),
      });
      const answerPayload = await answerResponse.json();

      if (!answerResponse.ok) {
        throw new Error(answerPayload.detail ?? "Failed to generate response");
      }

      const queryAnswerResponse = answerPayload as QueryAnswerResponse;
      setQueryAnswer(queryAnswerResponse);
      setQueryUnderstanding(queryAnswerResponse.understanding);
      if (queryAnswerResponse.understanding.primary_dossier) {
        setDossier(queryAnswerResponse.understanding.primary_dossier);
      }
    } catch (err) {
      setQueryError(
        err instanceof Error ? err.message : "Failed to understand query"
      );
    } finally {
      setIsUnderstandingLoading(false);
      setIsAnswerLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
        <QueryUnderstandingPanel
          answerResponse={queryAnswer}
          error={queryError}
          isAnswerLoading={isAnswerLoading}
          isUnderstandingLoading={isUnderstandingLoading}
          onQuestionChange={setQuestion}
        onSubmit={handleQuestionSubmit}
        question={question}
        result={queryUnderstanding}
        onAnswerCitationClick={handleAnswerCitationClick}
      />

      {dossier && queryAnswer && !isAnswerLoading && !isUnderstandingLoading ? (
        <SupportingEvidence
          dossier={dossier}
          evidenceRef={supportingEvidenceRef}
          highlightCitation={highlightCitation}
          isOpen={isEvidenceOpen}
          onOpenChange={setIsEvidenceOpen}
          onCitationHandled={() => setHighlightCitation(null)}
        />
      ) : null}
    </div>
  );
}

export function DrugDossierExperience() {
  const [drug, setDrug] = useState("aspirin");
  const [openfdaLimit, setOpenfdaLimit] = useState(5);
  const [dossier, setDossier] = useState<DrugDossier | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
          depth: 2,
          max_edges: 400,
          openfda_limit: openfdaLimit,
          include_openfda: true,
        }),
      });
      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload.detail ?? "Failed to build dossier");
      }

      setDossier(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to build dossier");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <Card>
        <CardHeader>
          <CardTitle>Drug Dossier</CardTitle>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            Search for a drug to explore related medication concepts and public
            label information.
          </p>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={handleSubmit}
            className="grid gap-3 md:grid-cols-[1fr_140px_auto]"
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
              <span className="flex items-center gap-1.5">
                Label limit
                <InfoTooltip text="Controls how many FDA drug-label records are retrieved for the searched drug. Higher limits may show more sources, but can make the page denser." />
              </span>
              <Input
                min={1}
                max={25}
                type="number"
                value={openfdaLimit}
                onChange={(event) => setOpenfdaLimit(Number(event.target.value))}
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
        </CardContent>
      </Card>

      {error ? (
        <div className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          <AlertTriangle className="size-4" />
          {error}
        </div>
      ) : null}

      {!dossier ? <EmptyState /> : <DossierResults dossier={dossier} />}
    </div>
  );
}

function SupportingEvidence({
  dossier,
  evidenceRef,
  highlightCitation,
  isOpen,
  onCitationHandled,
  onOpenChange,
}: {
  dossier: DrugDossier;
  evidenceRef: RefObject<HTMLDivElement | null>;
  highlightCitation: EvidenceCitation | null;
  isOpen: boolean;
  onCitationHandled: () => void;
  onOpenChange: (isOpen: boolean) => void;
}) {
  return (
    <div ref={evidenceRef} className="scroll-mt-6">
      {!isOpen ? (
        <div className="relative flex items-center py-4">
          <div className="flex-1 border-t border-[#D7C8F4]" />
          <Button
            type="button"
            className="mx-4 rounded-full px-5"
            onClick={() => onOpenChange(true)}
          >
            Explore supporting evidence
            <ChevronRight className="size-4" />
          </Button>
          <div className="flex-1 border-t border-[#D7C8F4]" />
        </div>
      ) : (
        <Card className="border-[#C7B4EF] shadow-md">
          <CardHeader className="flex flex-row items-start justify-between gap-3">
            <div>
              <CardTitle>Supporting Evidence</CardTitle>
              <p className="mt-1 text-sm leading-6 text-slate-500">
                Inspect the retrieved dossier behind the generated response.
              </p>
            </div>
            <Button
              type="button"
              variant="ghost"
              className="h-auto px-0 py-0 font-semibold uppercase tracking-wide text-slate-600 hover:bg-transparent hover:text-slate-900"
              style={{ fontSize: "14px", lineHeight: "20px" }}
              onClick={() => onOpenChange(false)}
            >
              <ChevronDown className="size-4" />
              Collapse
            </Button>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="flex items-end">
              <button
                type="button"
                className="rounded-t-md bg-[#371E96] px-4 py-2 text-sm font-semibold text-white shadow-sm"
              >
                {dossier.resolved_drug
                  ? displayGraphNodeName(dossier.resolved_drug.name)
                  : "Matched drug"}
              </button>
            </div>
            <div className="-mt-5 rounded-b-md rounded-tr-md border border-slate-200 bg-white p-4 shadow-sm">
              <DossierResults
                dossier={dossier}
                highlightCitation={highlightCitation}
                variant="embedded"
                onCitationHandled={onCitationHandled}
              />
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function DossierResults({
  dossier,
  highlightCitation = null,
  onCitationHandled,
  variant = "cards",
}: {
  dossier: DrugDossier;
  highlightCitation?: EvidenceCitation | null;
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
  const sectionEntries = useMemo(() => {
    return Object.entries(displayEvidence.sections);
  }, [displayEvidence]);
  const activeSection =
    selectedSection && displayEvidence.sections[selectedSection]
      ? selectedSection
      : sectionEntries[0]?.[0] ?? null;
  const activeTexts: DisplayLabelSection[] = activeSection
    ? displayEvidence.sections[activeSection] ?? []
    : [];

  useEffect(() => {
    const firstSection = Object.keys(dossier.label_evidence?.sections ?? {})[0];
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
      const response = await fetch("/api/label-evidence", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          rxcui: node.rxcui,
          name: node.name,
          limit: 3,
        }),
      });
      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload.detail ?? "Failed to fetch label evidence");
      }

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
        variant={variant}
        onJumpToLabels={() => scrollToSection(labelEvidencePanelRef)}
        onJumpToNetwork={() => scrollToSection(drugNetworkPanelRef)}
      />
      <div ref={drugNetworkPanelRef}>
        <RxNormKnowledgeGraph
          key={dossier.resolved_drug?.rxcui ?? dossier.query}
          dossier={dossier}
          variant={variant === "embedded" ? "embedded" : "card"}
          onSelectedNodeChange={handleSelectedGraphNodeChange}
        />
      </div>
      <LabelEvidencePanel
        ref={labelEvidencePanelRef}
        activeSection={activeSection}
        activeTexts={activeTexts}
        displayEvidence={displayEvidence}
        labelEvidence={labelEvidence}
        nodeEvidenceError={nodeEvidenceError}
        nodeLabelEvidence={nodeLabelEvidence}
        isNodeEvidenceLoading={isNodeEvidenceLoading}
        sectionEntries={sectionEntries}
        selectedGraphNode={selectedGraphNode}
        selectedSourceKey={selectedSourceKey}
        variant={variant}
        onSelectSection={setSelectedSection}
        onSelectSource={toggleSourceSelection}
        onSelectSourceFromStrip={selectSourceFromStrip}
      />
    </div>
  );
}

function QueryUnderstandingPanel({
  answerResponse,
  error,
  isAnswerLoading,
  isUnderstandingLoading,
  onQuestionChange,
  onAnswerCitationClick,
  onSubmit,
  question,
  result,
}: {
  answerResponse: QueryAnswerResponse | null;
  error: string | null;
  isAnswerLoading: boolean;
  isUnderstandingLoading: boolean;
  onQuestionChange: (value: string) => void;
  onAnswerCitationClick: (citation: EvidenceCitation) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  question: string;
  result: QueryUnderstandingResponse | null;
}) {
  const hasResultContent = Boolean(
    isUnderstandingLoading || isAnswerLoading || error || result || answerResponse
  );

  return (
    <div className="space-y-5">
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-center gap-2">
            <CardTitle>Ask a Question</CardTitle>
            <InfoTooltip text="This extracts a structured medication state from your question, resolves drug mentions through RxNorm, and loads the primary drug into the explorer below. It does not generate medical advice." />
          </div>
          <p className="mx-auto mt-1 max-w-2xl text-sm leading-6 text-slate-500">
            What can we help you explore? Ask in plain language, then inspect
            what the system understood.
          </p>
          <form
            onSubmit={onSubmit}
            className="mx-auto mt-5 flex max-w-4xl items-stretch gap-2"
          >
            <textarea
              value={question}
              onChange={(event) => onQuestionChange(event.target.value)}
              placeholder="Can I use tretinoin if I am pregnant and already take ibuprofen?"
              rows={1}
              aria-label="Question"
              className="min-h-11 flex-1 resize-y rounded-md border border-[#C7B4EF] bg-white px-3 py-2 text-slate-950 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-[#371E96] focus:ring-2 focus:ring-[#E8DDF9]"
              style={{ fontSize: "16px", lineHeight: "27px" }}
            />
            <Button
              type="submit"
              aria-label="Explore"
              className="h-11 w-11 shrink-0 px-0"
              disabled={
                isUnderstandingLoading || isAnswerLoading || !question.trim()
              }
            >
              {isUnderstandingLoading || isAnswerLoading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Search className="size-4" />
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

      {hasResultContent ? (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <CardTitle>Generated response</CardTitle>
              <InfoTooltip text="This response is generated by an LLM from the extracted query state and retrieved public evidence. It is intended for exploration only and does not provide medical advice." />
            </div>
            <p className="mt-1 text-sm leading-6 text-slate-500">
              Educational summary grounded in the retrieved public evidence for
              the mentioned drugs.
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            {error ? (
              <div className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
                <AlertTriangle className="size-4" />
                {error}
              </div>
            ) : null}

            {isUnderstandingLoading ? <QueryUnderstandingLoadingState /> : null}
            {!isUnderstandingLoading && result ? (
              <QueryUnderstandingResult result={result} />
            ) : null}
            {isAnswerLoading ? <AnswerSynthesisLoadingState /> : null}
            {!isUnderstandingLoading && !isAnswerLoading && answerResponse ? (
              <EvidenceAnswerResult
                response={answerResponse}
                onCitationClick={onAnswerCitationClick}
              />
            ) : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function EvidenceAnswerResult({
  onCitationClick,
  response,
}: {
  onCitationClick: (citation: EvidenceCitation) => void;
  response: QueryAnswerResponse;
}) {
  const { answer, understanding } = response;
  const synthesisWarnings = response.warnings.filter(
    (warning) => !understanding.warnings.includes(warning)
  );
  const synthesisErrors = response.errors.filter(
    (error) => !understanding.errors.includes(error)
  );

  if (!answer) {
    if (!understanding.primary_dossier) {
      return null;
    }
    return (
      <div className="rounded-md border border-slate-200 bg-slate-50">
        <div className="px-3 py-3">
          <div className="text-xs font-medium uppercase text-slate-500">
            Generated response
          </div>
          <p className="mt-2 text-sm leading-5 text-slate-600">
            {synthesisErrors.length
              ? "The generated response could not be created, but the retrieved evidence is available below."
              : "Generated responses are not configured in this environment, but the retrieved evidence is available below."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <EvidenceAnswerCard
      answer={answer}
      errors={synthesisErrors}
      onCitationClick={onCitationClick}
      understanding={understanding}
      warnings={synthesisWarnings}
    />
  );
}

function EvidenceAnswerCard({
  answer,
  errors,
  onCitationClick,
  understanding,
  warnings,
}: {
  answer: EvidenceAnswer;
  errors: string[];
  onCitationClick: (citation: EvidenceCitation) => void;
  understanding: QueryUnderstandingResponse;
  warnings: string[];
}) {
  const sourceById = useMemo(() => {
    const records =
      understanding.primary_dossier?.label_evidence?.label_records ?? [];
    return new Map(
      records
        .map((record) =>
          record.source_id ? ([record.source_id, record] as const) : null
        )
        .filter(
          (entry): entry is readonly [string, OpenFDALabelRecord] =>
            entry !== null
        )
    );
  }, [understanding.primary_dossier]);

  return (
    <div className="space-y-3">
      <div className="rounded-md border border-[#C7B4EF] bg-[#FBF9FE] px-4 py-4 shadow-sm">
        <p
          className="text-slate-800"
          style={{ fontSize: "16px", lineHeight: "27px" }}
        >
          {answer.summary}
        </p>
      </div>

      {answer.bullets.length ? (
        <AnswerSection title="Sources">
          <div className="space-y-2">
            {answer.bullets.map((bullet, index) => (
              <button
                key={`${bullet.text}-${index}`}
                type="button"
                onClick={() => {
                  const firstCitation = bullet.citations[0];
                  if (firstCitation) {
                    onCitationClick(firstCitation);
                  }
                }}
                className={cn(
                  "w-full rounded-md border border-[#D7C8F4] bg-white px-3 py-3 text-left transition",
                  bullet.citations.length
                    ? "hover:border-[#C7B4EF] hover:bg-[#F8F4FC]"
                    : ""
                )}
              >
                {bullet.citations.length ? (
                  <div className="mb-1.5 flex flex-col gap-1">
                    {bullet.citations.map((citation, citationIndex) => (
                      <div
                        key={`${citation.source_id}-${citation.section}-${citationIndex}`}
                        className="flex items-start gap-2 font-semibold leading-5 text-slate-800"
                        style={{ fontSize: "14px" }}
                      >
                        <FileText className="mt-0.5 size-4 shrink-0 text-slate-700" />
                        <span>{citationDisplayLabel(citation, sourceById)}</span>
                      </div>
                    ))}
                  </div>
                ) : null}
                <p
                  className={cn(
                    "leading-6 text-slate-800",
                    bullet.citations.length ? "pl-6" : ""
                  )}
                  style={{ fontSize: "14px" }}
                >
                  {bullet.text}
                </p>
              </button>
            ))}
          </div>
        </AnswerSection>
      ) : null}

      {answer.limitations.length ? (
        <AnswerSection title="Limitations">
          <div className="space-y-2">
            {answer.limitations.map((limitation) => (
              <div
                key={limitation}
                className="flex items-start gap-2 rounded-md border border-[#D7C8F4] bg-white px-3 py-2 leading-6 text-slate-800"
                style={{ fontSize: "14px" }}
              >
                <TriangleAlert className="mt-1 size-4 shrink-0 text-slate-700" />
                <span>{limitation}</span>
              </div>
            ))}
          </div>
        </AnswerSection>
      ) : null}

      <p className="text-center text-xs leading-5 text-slate-500">
        {answer.safety_note}
      </p>

      {warnings.length || errors.length ? (
        <div className="space-y-1 rounded-md border border-[#D7C8F4] bg-[#FBF9FE] px-3 py-3 text-xs leading-5 text-slate-500">
          {warnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
          {errors.map((error) => (
            <p key={error} className="text-red-700">
              {error}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function AnswerSection({
  children,
  icon,
  title,
}: {
  children: ReactNode;
  icon?: ReactNode;
  title: string;
}) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="rounded-md border border-[#D7C8F4] bg-[#FBF9FE]">
      <button
        type="button"
        onClick={() => setIsOpen((current) => !current)}
        className="flex w-full items-center gap-2 px-3 py-3 text-left text-slate-500"
      >
        {isOpen ? (
          <ChevronDown className="size-4 shrink-0" />
        ) : (
          <ChevronRight className="size-4 shrink-0" />
        )}
        {icon ? <span className="shrink-0">{icon}</span> : null}
        <span className="text-xs font-medium uppercase">{title}</span>
      </button>
      {isOpen ? (
        <div className="border-t border-[#D7C8F4] px-3 py-3">{children}</div>
      ) : null}
    </div>
  );
}

function QueryUnderstandingLoadingState() {
  return (
    <div className="flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-600">
      <Loader2 className="size-4 animate-spin text-slate-500" />
      Understanding your query and extracting relevant information...
    </div>
  );
}

function AnswerSynthesisLoadingState() {
  return (
    <div className="flex items-center gap-2 rounded-md border border-[#D7C8F4] bg-[#FBF9FE] px-3 py-3 text-sm leading-6 text-slate-700">
      <Loader2 className="size-4 animate-spin text-[#371E96]" />
      Incorporating what the system understood with retrieved public evidence to
      generate a response...
    </div>
  );
}

function QueryUnderstandingResult({
  result,
}: {
  result: QueryUnderstandingResponse;
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="rounded-md border border-slate-200 bg-slate-50">
      <button
        type="button"
        onClick={() => setIsExpanded((current) => !current)}
        className="flex w-full items-center justify-between gap-3 px-3 py-3 text-left"
      >
        <div className="flex min-w-0 items-center gap-2">
          {isExpanded ? (
            <ChevronDown className="size-4 shrink-0 text-slate-500" />
          ) : (
            <ChevronRight className="size-4 shrink-0 text-slate-500" />
          )}
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <div className="text-xs font-medium uppercase text-slate-500">
                Find out what the system understood
              </div>
              <InfoTooltip text="The app first extracts medication concepts and context with deterministic rules, then asks an LLM to revise the extracted parameters before using it to retrieve evidence." />
            </div>
            {/* {!isExpanded ? (
              <p className="mt-1 text-sm text-slate-600">
                Extracted medication, patient context, and intent parameters.
              </p>
            ) : null} */}
          </div>
        </div>
      </button>

      <QueryUnderstandingStatus result={result} />

      {isExpanded ? (
        <div className="space-y-3 border-t border-slate-200 p-3">
          {/* <div className="text-xs font-medium uppercase text-slate-500">
            Parameters
          </div> */}

          <ParameterGroup title="Medication concepts">
            <ParameterRow
              // emphasize
              label="Primary drug"
              values={result.state.primary_drug ? [result.state.primary_drug] : []}
            />
            <ParameterRow
              label="Current medications"
              values={result.state.current_medications}
            />
            <ParameterRow
              label="All drugs mentioned"
              values={result.state.all_drugs_mentioned}
            />
          </ParameterGroup>

          <ParameterGroup title="Patient context">
            <ParameterRow label="Allergies" values={result.state.allergies} />
            <ParameterRow label="Conditions" values={result.state.conditions} />
            <ParameterRow
              label="Patient details"
              values={result.state.patient_context}
            />
          </ParameterGroup>

          <ParameterGroup title="Intent">
            <ParameterRow
              label="User intent"
              values={
                result.state.intent ? [displayStateLabel(result.state.intent)] : []
              }
            />
          </ParameterGroup>
        </div>
      ) : null}

    </div>
  );
}

function QueryUnderstandingStatus({
  result,
}: {
  result: QueryUnderstandingResponse;
}) {
  const hasNoPrimaryDossier = !result.primary_dossier;
  const visibleWarnings = result.warnings.filter(
    (warning) => !warning.startsWith("No primary drug could be resolved")
  );

  if (!hasNoPrimaryDossier && visibleWarnings.length === 0 && result.errors.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2 border-t border-slate-200 p-3">
      {hasNoPrimaryDossier || visibleWarnings.length ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm leading-5 text-amber-900">
          {hasNoPrimaryDossier ? (
            <p>
              No primary medication could be linked to RxNorm, so the dossier
              below was not updated.
            </p>
          ) : null}
          {visibleWarnings.length ? (
            <div className={cn("space-y-1", hasNoPrimaryDossier ? "mt-2" : "")}>
              {visibleWarnings.map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      {result.errors.length ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm leading-5 text-red-800">
          <ul className="list-disc space-y-1 pl-4">
            {result.errors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function ParameterGroup({
  children,
  defaultOpen = false,
  title,
}: {
  children: ReactNode;
  defaultOpen?: boolean;
  title: string;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="rounded-md border border-slate-200 bg-white">
      <button
        type="button"
        onClick={() => setIsOpen((current) => !current)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left"
      >
        {isOpen ? (
          <ChevronDown className="size-4 shrink-0 text-slate-500" />
        ) : (
          <ChevronRight className="size-4 shrink-0 text-slate-500" />
        )}
        <span className="text-xs font-medium uppercase text-slate-500">
          {title}
        </span>
      </button>
      {isOpen ? (
        <div className="space-y-3 border-t border-slate-100 px-3 py-3">
          {children}
        </div>
      ) : null}
    </div>
  );
}

function ParameterRow({
  emphasize = false,
  label,
  values,
}: {
  emphasize?: boolean;
  label: string;
  values: string[];
}) {
  return (
    <div className="grid gap-2 sm:grid-cols-[160px_minmax(0,1fr)]">
      <div className="text-sm font-medium text-slate-600">{label}</div>
      {values.length ? (
        <div className="flex flex-wrap gap-1.5">
          {values.map((value) => (
            <Badge
              key={value}
              className="border-slate-200 bg-slate-50 text-slate-800"
            >
              {emphasize ? displayGraphNodeName(value) : value}
            </Badge>
          ))}
        </div>
      ) : (
        <div className="text-sm text-slate-400 italic">Not detected</div>
      )}
    </div>
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

function Overview({
  dossier,
  onJumpToLabels,
  onJumpToNetwork,
  variant = "cards",
}: {
  dossier: DrugDossier;
  onJumpToLabels: () => void;
  onJumpToNetwork: () => void;
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
              </div>
            </div>
          ) : (
            <div className="mt-2 text-sm text-slate-600">
              No matching drug concept was found for this search.
            </div>
          )}
        </div>
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
      className="rounded-md border border-slate-200 bg-slate-50 p-3 text-left transition hover:border-slate-300 hover:bg-white"
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

function LabelEvidencePanel({
  ref,
  activeSection,
  activeTexts,
  displayEvidence,
  labelEvidence,
  nodeEvidenceError,
  nodeLabelEvidence,
  isNodeEvidenceLoading,
  sectionEntries,
  selectedGraphNode,
  selectedSourceKey,
  variant = "cards",
  onSelectSection,
  onSelectSource,
  onSelectSourceFromStrip,
}: {
  ref: RefObject<HTMLDivElement | null>;
  activeSection: string | null;
  activeTexts: DisplayLabelSection[];
  displayEvidence: DisplayEvidenceModel;
  labelEvidence: OpenFDALabelEvidence | null;
  nodeEvidenceError: string | null;
  nodeLabelEvidence: OpenFDALabelEvidence | null;
  isNodeEvidenceLoading: boolean;
  sectionEntries: [string, DisplayLabelSection[]][];
  selectedGraphNode: RxNormConcept | null;
  selectedSourceKey: string | null;
  variant?: "cards" | "embedded";
  onSelectSection: (section: string) => void;
  onSelectSource: (sourceKey?: string | null) => void;
  onSelectSourceFromStrip: (sourceKey?: string | null) => void;
}) {
  const records = displayEvidence.records;
  const evidenceCardsRef = useRef<HTMLDivElement>(null);
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
        count: groupLabelSectionsBySource(section, texts, displayEvidence).length,
      })),
    [displayEvidence, sectionEntries]
  );

  function handleSourceStripClick(sourceKey: string) {
    onSelectSourceFromStrip(sourceKey);
    window.requestAnimationFrame(() => {
      evidenceCardsRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    });
  }

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

  return (
    <div ref={ref}>
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
              Public drug-label text retrieved for the searched drug, with graph
              selections used to highlight or add more specific label records.
            </p>
          </div>
        </div>
        <div
          className={cn(
            "space-y-5",
            variant === "cards" ? "p-4 pt-5" : "p-0 pt-4"
          )}
        >
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
                      name, manufacturer name, route of administration, 
                      and product type in that order.
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
              ) : (
                <div className="space-y-2">
                  {records.map((source) => {
                    const brandName = primaryValue(source.record.brand_names);
                    const genericName = primaryValue(source.record.generic_names);
                    const manufacturerName = primaryValue(
                      source.record.manufacturer_names
                    );
                    const route = primaryValue(source.record.routes);
                    const productType = primaryValue(source.record.product_types);
                    const isSelected = source.key === selectedSourceKey;
                    const sourceClasses = isSelected
                      ? sourceSelectionClasses
                      : source.isSelectedNodeOnly
                        ? nodeSpecificClasses
                        : searchSourceClasses;
                    return (
                      <button
                        key={source.key}
                        type="button"
                        onClick={() => handleSourceStripClick(source.key)}
                        className={cn(
                          "w-full rounded-md border p-2 text-left transition",
                          sourceClasses
                        )}
                        style={{ fontSize: "14px", lineHeight: "20px" }}
                      >
                        <div className="mb-1 flex flex-wrap items-center gap-1.5">
                          <Badge className={sourceNumberBadgeClasses}>
                            Source {source.sourceNumber}
                          </Badge>
                          {!source.isSelectedNodeOnly ? (
                            <Badge className={searchSpecificBadgeClasses}>
                              Search-specific
                            </Badge>
                          ) : null}
                          {source.isSelectedNodeOnly ||
                          source.isSelectedNodeMatch ? (
                            <Badge className={nodeSpecificBadgeClasses}>
                              Node-specific
                            </Badge>
                          ) : null}
                        </div>
                        <div className="mt-1.5 truncate font-medium text-slate-900">
                          {brandName
                            ? displayBrandName(brandName)
                            : "Brand unavailable"}
                        </div>
                        <div className="mt-0.5 truncate text-slate-600">
                          {genericName
                            ? displayGenericName(genericName)
                            : "Generic unavailable"}
                        </div>
                        <div className="mt-0.5 truncate text-slate-500">
                          {manufacturerName ?? "Manufacturer unavailable"}
                        </div>
                        {route || productType ? (
                          <div className="mt-1.5 text-slate-500">
                            {route ? (
                              <span>{sentenceCase(route)}</span>
                            ) : null}
                            {route && productType ? <span> · </span> : null}
                            {productType ? (
                              <span>{sentenceCase(productType)}</span>
                            ) : null}
                          </div>
                        ) : null}
                      </button>
                    );
                  })}
                </div>
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
                    {sectionTabEntries.map(({ section, count }) => (
                      <Button
                        key={section}
                        type="button"
                        variant={
                          activeSection === section ? "primary" : "secondary"
                        }
                        onClick={() => onSelectSection(section)}
                      >
                        {displaySectionName(section)}
                        <span className="text-xs opacity-75">
                          {count}
                        </span>
                      </Button>
                    ))}
                  </div>

                  <div ref={evidenceCardsRef} className="space-y-3">
                    {groupedActiveTexts.map((entry) => {
                      const sourceKey = entry.sourceKey;
                      const source = entry.source;
                      const brandName = primaryValue(
                        source?.record.brand_names
                      );
                      const manufacturerName = primaryValue(
                        source?.record.manufacturer_names
                      );
                      const isSelected =
                        Boolean(sourceKey) && sourceKey === selectedSourceKey;
                      const evidenceClasses = isSelected
                        ? sourceSelectionClasses
                        : source?.isSelectedNodeOnly
                          ? nodeSpecificClasses
                          : "border-slate-200 bg-slate-50 hover:border-slate-300 hover:bg-white";
                      const isExpanded = expandedEvidenceKeys.has(entry.key);
                      const canExpand = entry.text.length > 900;
                      return (
                        <article
                          key={entry.key}
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
                                Source {source.sourceNumber}
                              </span>
                            ) : (
                              <Badge>Source unknown</Badge>
                            )}
                            {brandName ? (
                              <span>{displayBrandName(brandName)}</span>
                            ) : null}
                            {manufacturerName ? (
                              <span>· {manufacturerName}</span>
                            ) : null}
                          </div>
                          <p
                            className={cn(
                              "whitespace-pre-wrap text-sm leading-6 text-slate-800",
                              canExpand && !isExpanded
                                ? "max-h-56 overflow-hidden"
                                : ""
                            )}
                          >
                            {entry.text}
                          </p>
                          {canExpand ? (
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                toggleEvidenceExpansion(entry.key);
                              }}
                              className="mt-3 font-medium uppercase tracking-wide text-slate-500 underline-offset-2 hover:text-cyan-700 hover:underline"
                              style={{ fontSize: "12px", lineHeight: "14px" }}
                            >
                              {isExpanded ? "Show less" : "Show more"}
                            </button>
                          ) : null}
                        </article>
                      );
                    })}
                  </div>
                </div>
              )}
            </section>
          </div>
          {labelEvidence?.errors.length ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              {labelEvidence.errors.join(" ")}
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
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
      <div className="text-sm leading-6 text-slate-700">
        Selected graph node:{" "}
        <span className="font-bold text-slate-950">
          {displayGraphNodeName(node.name)}
        </span>
        . Displaying {displayEvidence.selectedNodeOnlyCount} node-specific
        source{displayEvidence.selectedNodeOnlyCount === 1 ? "" : "s"} pinned
        first.
        {previewLimitReached
          ? " This is a compact preview; search this drug directly to retrieve further label evidence."
          : ""}
      </div>
    );
  }

  if (displayEvidence.selectedNodeMatchCount > 0) {
    return (
      <div className="text-sm leading-6 text-slate-700">
        Selected graph node:{" "}
        <span className="font-bold text-slate-950">
          {displayGraphNodeName(node.name)}
        </span>
        . Its labels match source
        {displayEvidence.selectedNodeMatchCount === 1 ? "" : "s"} already
        returned for the original search.
      </div>
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
