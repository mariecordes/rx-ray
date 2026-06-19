"use client";

import {
  FormEvent,
  type ReactNode,
  type RefObject,
  useMemo,
  useState,
} from "react";
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  FileText,
  Loader2,
  Search,
  TriangleAlert,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { citationDisplayLabel } from "@/components/dossier/display";
import { EvidenceCoverageTarget } from "@/components/dossier/evidence-model";
import {
  EvidenceAnswer,
  EvidenceCitation,
  EvidenceCoverageItem,
  EvidenceCoverageReport,
  EvidenceCoverageStatus,
  OpenFDALabelRecord,
  QueryAnswerResponse,
  QueryUnderstandingResponse,
  SecondaryDrugEvidence,
} from "@/lib/types";
import { displayGraphNodeName, displayStateLabel } from "@/lib/format";
import { frontendParameters } from "@/lib/parameters";
import { cn } from "@/lib/utils";

const frontendLimits = frontendParameters.limits;

export function QueryUnderstandingPanel({
  answerResponse,
  askRef,
  error,
  generatedResponseRef,
  isDemoMode,
  isAnswerLoading,
  isUnderstandingLoading,
  onQuestionChange,
  onAnswerCitationClick,
  onCoverageTargetClick,
  onDemoModeChange,
  onSubmit,
  question,
  result,
}: {
  answerResponse: QueryAnswerResponse | null;
  askRef: RefObject<HTMLDivElement | null>;
  error: string | null;
  generatedResponseRef: RefObject<HTMLDivElement | null>;
  isDemoMode: boolean;
  isAnswerLoading: boolean;
  isUnderstandingLoading: boolean;
  onQuestionChange: (value: string) => void;
  onAnswerCitationClick: (citation: EvidenceCitation) => void;
  onCoverageTargetClick: (target: EvidenceCoverageTarget) => void;
  onDemoModeChange: (enabled: boolean) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  question: string;
  result: QueryUnderstandingResponse | null;
}) {
  const hasResultContent = Boolean(
    isUnderstandingLoading || isAnswerLoading || error || result || answerResponse
  );
  const canGenerateAnswer = Boolean(result?.primary_dossier);

  return (
    <div className="space-y-5">
      <div ref={askRef} className="scroll-mt-6">
        <Card>
          <CardContent className="pb-7 pt-6">
            <div className="flex items-center justify-center gap-2">
              <CardTitle>Ask a Question</CardTitle>
              <InfoTooltip text="This extracts a structured medication state from your question, resolves drug mentions through RxNorm, and loads the primary drug into the explorer below. It does not generate medical advice." />
            </div>
            <p className="mx-auto mt-1 max-w-1xl text-center text-sm leading-6 text-slate-500">
              What can we help you explore? Ask in plain language, then inspect
              the generated response and its evidence.
            </p>
            <form
              onSubmit={onSubmit}
              className="mx-auto mt-5 flex max-w-4xl items-stretch gap-2"
            >
              <textarea
                value={question}
                onChange={(event) => onQuestionChange(event.target.value)}
                placeholder="Can I take ibuprofen for my migraine if I'm allergic to aspirin?"
                rows={1}
                maxLength={frontendLimits.maxUserQueryCharacters}
                aria-label="Question"
                className="min-h-11 flex-1 resize-y rounded-md border border-[#C7B4EF] bg-white px-3 py-2 text-slate-950 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-[#371E8F] focus:ring-2 focus:ring-[#E8DDF9]"
                style={{ fontSize: "15px", lineHeight: "27px" }}
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
            <div className="mx-auto mt-3 flex max-w-4xl flex-wrap items-center justify-between gap-2 text-sm text-slate-500">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={isDemoMode}
                  onChange={(event) => onDemoModeChange(event.target.checked)}
                  className="size-4 rounded border-slate-300 text-[#371E8F] focus:ring-[#371E8F]"
                />
                Demo mode
              </label>
              <span className="text-xs leading-5">
                Uses a local fixture for the cetirizine, ibuprofen, and aspirin
                query. No LLM or live API calls.
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {hasResultContent ? (
        <div ref={generatedResponseRef} className="scroll-mt-6">
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
              {isAnswerLoading && canGenerateAnswer ? (
                <AnswerSynthesisLoadingState />
              ) : null}
              {!isUnderstandingLoading && !isAnswerLoading && answerResponse ? (
                <EvidenceAnswerResult
                  response={answerResponse}
                  onCitationClick={onAnswerCitationClick}
                  onCoverageTargetClick={onCoverageTargetClick}
                />
              ) : null}
            </CardContent>
          </Card>
        </div>
      ) : null}
    </div>
  );
}

function EvidenceAnswerResult({
  onCitationClick,
  onCoverageTargetClick,
  response,
}: {
  onCitationClick: (citation: EvidenceCitation) => void;
  onCoverageTargetClick: (target: EvidenceCoverageTarget) => void;
  response: QueryAnswerResponse;
}) {
  const { answer, understanding } = response;
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
      coverage={response.coverage ?? { items: [], summary_counts: {} }}
      onCitationClick={onCitationClick}
      onCoverageTargetClick={onCoverageTargetClick}
      secondaryEvidence={response.secondary_evidence ?? []}
      understanding={understanding}
    />
  );
}

function EvidenceAnswerCard({
  answer,
  coverage,
  onCitationClick,
  onCoverageTargetClick,
  secondaryEvidence,
  understanding,
}: {
  answer: EvidenceAnswer;
  coverage: EvidenceCoverageReport;
  onCitationClick: (citation: EvidenceCitation) => void;
  onCoverageTargetClick: (target: EvidenceCoverageTarget) => void;
  secondaryEvidence: SecondaryDrugEvidence[];
  understanding: QueryUnderstandingResponse;
}) {
  const sourceById = useMemo(() => {
    const records = [
      ...(understanding.primary_dossier?.label_evidence?.label_records ?? []),
      ...secondaryEvidence.flatMap(
        (item) => item.label_evidence?.label_records ?? []
      ),
    ];
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
  }, [secondaryEvidence, understanding.primary_dossier]);
  const hasVisibleCoverage = coverage.items.some(
    (item) => !isLowSignalCoverageItem(item)
  );
  const visibleCoverageStatusCounts = useMemo(
    () => coverageStatusCounts(coverage),
    [coverage]
  );
  const directResponse = (answer.response || answer.summary || "").trim();
  const evidenceSummary = (answer.evidence_summary || "").trim();
  const shouldShowEvidenceSummary =
    evidenceSummary.length > 0 && evidenceSummary !== directResponse;

  return (
    <div className="space-y-3">
      {hasVisibleCoverage ? (
        <AnswerSection
          title="Find out what evidence was retrieved"
          infoText="This is a deterministic, pre-answer check: did we retrieve label text that would normally cover what was extracted from your question and what intent it was tagged with? It does not assess whether the generated answer below actually used or correctly interpreted that evidence — it only confirms whether matching evidence exists in what was retrieved. Hover over a reason when available to inspect the matching evidence snippet."
          tone="audit"
          headerExtra={<CoverageStatusChips counts={visibleCoverageStatusCounts} />}
        >
          <EvidenceCoverageList
            coverage={coverage}
            onCitationClick={onCitationClick}
            onCoverageTargetClick={onCoverageTargetClick}
          />
        </AnswerSection>
      ) : null}

      <div className="rounded-md border border-[#C7B4EF] bg-[#FBF9FE] px-4 py-4 shadow-sm">
        <section>
          <h3
            className="mb-2 font-semibold text-slate-800"
            style={{ fontSize: "15px", lineHeight: "24px" }}
          >
            Evidence-based answer
          </h3>

          <p
            className="text-slate-700"
            style={{ fontSize: "15px", lineHeight: "26px" }}
          >
            <InlineBoldMarkdown text={directResponse} />
          </p>
        </section>

        {shouldShowEvidenceSummary ? (
          <section className="mt-4 border-t border-slate-200 pt-4">
            <h3
              className="mb-2 font-semibold text-slate-800"
              style={{ fontSize: "15px", lineHeight: "24px" }}
            >
              Evidence summary
            </h3>

            <p
              className="text-slate-700"
              style={{ fontSize: "15px", lineHeight: "26px" }}
            >
              <InlineBoldMarkdown text={evidenceSummary} />
            </p>
          </section>
        ) : null}
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
                  <InlineBoldMarkdown text={bullet.text} />
                </p>
              </button>
            ))}
          </div>
        </AnswerSection>
      ) : null}

      {answer.limitations.length ? (
        <AnswerSection
          title="Caveats & limitations"
          badgeCount={answer.limitations.length}
        >
          <div className="space-y-2">
            {answer.limitations.map((limitation) => (
              <div
                key={limitation}
                className="flex items-start gap-2 rounded-md border border-[#D7C8F4] bg-white px-3 py-2 leading-6 text-slate-800"
                style={{ fontSize: "14px" }}
              >
                <TriangleAlert className="mt-1 size-4 shrink-0 text-slate-700" />
                <span>
                  <InlineBoldMarkdown text={limitation} />
                </span>
              </div>
            ))}
          </div>
        </AnswerSection>
      ) : null}

      <p className="text-center text-xs leading-5 text-slate-500">
        {answer.safety_note}
      </p>
    </div>
  );
}

function InlineBoldMarkdown({ text }: { text: string }) {
  const segments = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {segments.map((segment, index) => {
        const isBold = segment.startsWith("**") && segment.endsWith("**");
        const value = isBold ? segment.slice(2, -2) : segment;
        return isBold ? <strong key={index}>{value}</strong> : value;
      })}
    </>
  );
}

function EvidenceCoverageList({
  coverage,
  onCitationClick,
  onCoverageTargetClick,
}: {
  coverage: EvidenceCoverageReport;
  onCitationClick: (citation: EvidenceCitation) => void;
  onCoverageTargetClick: (target: EvidenceCoverageTarget) => void;
}) {
  const bucketedGroups = useMemo(() => {
    const categoryGroups = new Map<string, EvidenceCoverageItem[]>();
    for (const item of coverage.items) {
      if (isLowSignalCoverageItem(item)) {
        continue;
      }
      const current = categoryGroups.get(item.category) ?? [];
      current.push(item);
      categoryGroups.set(item.category, current);
    }

    const buckets = new Map<CoverageBucket, Array<[string, EvidenceCoverageItem[]]>>();
    for (const [category, items] of categoryGroups) {
      const bucket = coverageBucket(category);
      const current = buckets.get(bucket) ?? [];
      current.push([category, items]);
      buckets.set(bucket, current);
    }

    return coverageBucketOrder
      .map((bucket) => [bucket, buckets.get(bucket) ?? []] as const)
      .filter(([, groups]) => groups.length > 0);
  }, [coverage.items]);

  return (
    <div className="space-y-4">
      {bucketedGroups.map(([bucket, categoryGroups]) => (
        <div key={bucket} className="space-y-2">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            {coverageBucketLabels[bucket]}
          </div>
          <div className="space-y-2">
            {categoryGroups.map(([category, items]) => (
              <div
                key={category}
                className="rounded-md border border-slate-200 bg-white px-3 py-3"
              >
                {bucket !== "intent" ? (
                  <div className="mb-2 text-xs font-medium uppercase text-slate-500">
                    {displayCoverageCategory(category)}
                  </div>
                ) : null}
                <div className="space-y-2">
                  {items.map((item) => (
                    <div
                      key={`${item.category}-${item.label}-${item.status}`}
                      className="grid gap-2 sm:grid-cols-[minmax(120px,0.32fr)_auto_minmax(0,1fr)] sm:items-start"
                    >
                      <span className="rounded-md bg-slate-50 px-2 py-1 text-sm font-medium leading-5 text-slate-800">
                        {displayCoverageItemLabel(item)}
                      </span>
                      <span
                        className={cn(
                          "w-fit rounded-md border px-2 py-1 text-xs font-medium",
                          coverageStatusClasses[item.status]
                        )}
                      >
                        {coverageStatusLabels[item.status]}
                      </span>
                      <div className="text-sm leading-5 text-slate-600">
                        <CoverageReason
                          item={item}
                          onCitationClick={onCitationClick}
                          onCoverageTargetClick={onCoverageTargetClick}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function CoverageReason({
  item,
  onCitationClick,
  onCoverageTargetClick,
}: {
  item: EvidenceCoverageItem;
  onCitationClick: (citation: EvidenceCitation) => void;
  onCoverageTargetClick: (target: EvidenceCoverageTarget) => void;
}) {
  if (!item.matched_evidence && item.target_rxcui) {
    return (
      <p>
        <button
          type="button"
          onClick={() => onCoverageTargetClick({ rxcui: item.target_rxcui! })}
          className="inline border-b border-dotted border-slate-400 text-left hover:text-[#371E8F]"
        >
          {item.reason}
        </button>
      </p>
    );
  }

  if (!item.matched_evidence) {
    return <p>{item.reason}</p>;
  }
  const citation =
    item.source_id && item.section
      ? {
          source_id: item.source_id,
          section: item.section,
          snippet: item.matched_evidence,
        }
      : null;
  const reasonClasses = cn(
    "group relative inline border-b border-dotted border-slate-400 text-left",
    citation ? "cursor-pointer hover:text-[#371E8F]" : ""
  );

  return (
    <p>
      <button
        type="button"
        onClick={() => {
          if (citation) {
            onCitationClick(citation);
          }
        }}
        className={reasonClasses}
      >
        {item.reason}
        <span className="pointer-events-none absolute left-0 top-full z-30 mt-2 hidden w-80 max-w-[75vw] rounded-md border border-slate-200 bg-white px-3 py-2 text-xs normal-case leading-5 text-slate-700 shadow-lg group-hover:block">
          <HighlightedMatchedEvidence
            label={item.label}
            text={item.matched_evidence}
          />
        </span>
      </button>
    </p>
  );
}

function HighlightedMatchedEvidence({
  label,
  text,
}: {
  label: string;
  text: string;
}) {
  if (!label.trim()) {
    return text;
  }

  const pattern = new RegExp(`(${escapeRegExp(label)})`, "ig");
  const parts = text.split(pattern);
  if (parts.length === 1) {
    return text;
  }

  return (
    <>
      {parts.map((part, index) =>
        part.toLowerCase() === label.toLowerCase() ? (
          <mark
            key={`${part}-${index}`}
            className="rounded-sm bg-amber-100 px-0.5 text-slate-800"
          >
            {part}
          </mark>
        ) : (
          <span key={`${part}-${index}`}>{part}</span>
        )
      )}
    </>
  );
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function AnswerSection({
  badgeCount,
  children,
  headerExtra,
  icon,
  infoText,
  title,
  tone = "synthesis",
}: {
  badgeCount?: number;
  children: ReactNode;
  headerExtra?: ReactNode;
  icon?: ReactNode;
  infoText?: string;
  title: string;
  tone?: "synthesis" | "audit";
}) {
  const [isOpen, setIsOpen] = useState(false);
  const borderClass = tone === "audit" ? "border-slate-200" : "border-[#D7C8F4]";
  const backgroundClass = tone === "audit" ? "bg-slate-50" : "bg-[#FBF9FE]";

  return (
    <div className={cn("rounded-md border", borderClass, backgroundClass)}>
      <button
        type="button"
        onClick={() => setIsOpen((current) => !current)}
        className="flex w-full flex-wrap items-center gap-2 px-3 py-3 text-left text-slate-500"
      >
        {isOpen ? (
          <ChevronDown className="size-4 shrink-0" />
        ) : (
          <ChevronRight className="size-4 shrink-0" />
        )}
        {icon ? <span className="shrink-0">{icon}</span> : null}
        <span className="text-xs font-medium uppercase">{title}</span>
        {badgeCount ? (
          <span className="rounded-full bg-slate-200 px-1.5 py-0.5 text-[10px] font-semibold text-slate-700">
            {badgeCount}
          </span>
        ) : null}
        {headerExtra ? (
          <span className="flex flex-wrap items-center gap-1.5">
            {headerExtra}
          </span>
        ) : null}
        {infoText ? <InfoTooltip text={infoText} /> : null}
      </button>
      {isOpen ? (
        <div className={cn("border-t px-3 py-3", borderClass)}>{children}</div>
      ) : null}
    </div>
  );
}

function coverageStatusCounts(coverage: EvidenceCoverageReport) {
  const counts: Partial<Record<EvidenceCoverageStatus, number>> = {};
  for (const item of coverage.items) {
    if (isLowSignalCoverageItem(item)) {
      continue;
    }
    counts[item.status] = (counts[item.status] ?? 0) + 1;
  }
  return counts;
}

function CoverageStatusChips({
  counts,
}: {
  counts: Partial<Record<EvidenceCoverageStatus, number>>;
}) {
  return (
    <>
      {coverageStatusOrder.map((status) => {
        const count = counts[status] ?? 0;
        if (count === 0) {
          return null;
        }
        return (
          <span
            key={status}
            className={cn(
              "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium",
              coverageStatusClasses[status]
            )}
          >
            {coverageStatusLabels[status]} {count}
          </span>
        );
      })}
    </>
  );
}

const coverageStatusOrder: EvidenceCoverageStatus[] = [
  "addressed",
  "not_found_in_evidence",
  "not_retrieved",
  "out_of_scope",
];

const coverageStatusLabels: Record<EvidenceCoverageStatus, string> = {
  addressed: "Addressed",
  not_found_in_evidence: "Not found",
  not_retrieved: "Not retrieved",
  out_of_scope: "Out of scope",
};

const coverageStatusClasses: Record<EvidenceCoverageStatus, string> = {
  addressed: "border-emerald-200 bg-emerald-50 text-emerald-800",
  not_found_in_evidence: "border-amber-200 bg-amber-50 text-amber-900",
  not_retrieved: "border-slate-200 bg-slate-50 text-slate-700",
  out_of_scope: "border-slate-200 bg-slate-50 text-slate-700",
};

function isLowSignalCoverageItem(item: EvidenceCoverageItem) {
  // "out_of_scope" only ever comes from intents the system has no
  // deterministic evidence check for (e.g. an LLM-invented intent label) —
  // showing it would just be noise rather than a real signal.
  return item.category === "intent" && item.status === "out_of_scope";
}

function displayCoverageItemLabel(item: EvidenceCoverageItem) {
  if (item.category === "intent") {
    return displayStateLabel(item.label);
  }
  return item.label;
}

const coverageCategoryLabels: Record<string, string> = {
  primary_drug: "Primary medication",
  mentioned_drug: "Mentioned medications",
  current_medication: "Current medications",
  allergy: "Allergies",
  condition: "Conditions",
  patient_context: "Patient context",
};

function displayCoverageCategory(category: string) {
  return coverageCategoryLabels[category] ?? category.replaceAll("_", " ");
}

type CoverageBucket = "medication_concepts" | "patient_context" | "intent" | "other";

const coverageBucketOrder: CoverageBucket[] = [
  "medication_concepts",
  "patient_context",
  "intent",
  "other",
];

const coverageBucketLabels: Record<CoverageBucket, string> = {
  medication_concepts: "Medication concepts",
  patient_context: "Patient context",
  intent: "Intent coverage",
  other: "Other",
};

function coverageBucket(category: string): CoverageBucket {
  if (
    category === "primary_drug" ||
    category === "mentioned_drug" ||
    category === "current_medication"
  ) {
    return "medication_concepts";
  }
  if (
    category === "allergy" ||
    category === "condition" ||
    category === "patient_context"
  ) {
    return "patient_context";
  }
  if (category === "intent") {
    return "intent";
  }
  return "other";
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
      <Loader2 className="size-4 animate-spin text-[#371E8F]" />
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
          </div>
        </div>
      </button>

      <QueryUnderstandingStatus result={result} />

      {isExpanded ? (
        <div className="space-y-3 border-t border-slate-200 p-3">
          <ParameterGroup title="Medication concepts">
            <ParameterRow
              label="Primary medication"
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
                (result.state.intents?.length
                  ? result.state.intents
                  : result.state.intent
                    ? [result.state.intent]
                    : []
                ).map(displayStateLabel)
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
  // Technical warnings/errors are intentionally not surfaced in the UI (they
  // remain in the API response and server logs). Only the essential "we could
  // not build a dossier" explanation is shown, so the page isn't left blank.
  if (result.primary_dossier) {
    return null;
  }

  return (
    <div className="space-y-2 border-t border-slate-200 p-3">
      <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm leading-5 text-amber-900">
        <p>
          We could not link the primary medication to the current medication
          terminology database, so no generated answer or supporting evidence
          dossier was created for this query.
        </p>
      </div>
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
