"use client";

import Link from "next/link";
import { AlertTriangle, ArrowUpRight, FileText } from "lucide-react";
import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import {
  AnswerSection,
  CaveatsList,
  CitationSupportBadges,
  CoverageStatusChips,
  EvidenceAnswerBox,
  EvidenceCoverageList,
  InlineBoldMarkdown,
  UnderstoodPanel,
  coverageStatusCounts,
} from "@/components/dossier/generated-response";
import { sectionLabels } from "@/lib/format";
import type { CitationSupportStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

import { toCoverageReport, toQueryState } from "./compare-adapters";
import type {
  CombinedView,
  CompareBullet,
  NeuralView,
  SymbolicView,
} from "./compare-types";

// Marks the middle (rx-ray) column: a colored top accent bar plus a
// noticeably stronger, tinted shadow, distinct from the light violet used
// throughout the answer panels so it doesn't just blend into the page.
// The `!` forces the shadow to win over Card's own `shadow-sm` — same CSS
// property, and cn() here is a plain clsx with no conflict resolution.
const HIGHLIGHT_ACCENT =
  "border-t-4 border-t-[#4F46E5] shadow-[0_22px_45px_-15px_rgba(67,56,202,0.45)]!";

const noop = () => {};

function sectionLabel(section: string): string {
  return sectionLabels[section] ?? section.replaceAll("_", " ");
}

/** Minimal **bold** renderer with red highlighting of detected advice phrases,
 *  used only for the raw-LLM column. */
function HighlightedProse({
  text,
  phrases,
}: {
  text: string;
  phrases: string[];
}) {
  if (phrases.length === 0) {
    return <InlineBoldMarkdown text={text} />;
  }
  const nodes: ReactNode[] = [];
  let remaining = text;
  let key = 0;
  while (remaining.length > 0) {
    let earliest = -1;
    let matchLength = 0;
    const lowered = remaining.toLowerCase();
    for (const phrase of phrases) {
      const index = lowered.indexOf(phrase.toLowerCase());
      if (index !== -1 && (earliest === -1 || index < earliest)) {
        earliest = index;
        matchLength = phrase.length;
      }
    }
    if (earliest === -1) {
      nodes.push(<InlineBoldMarkdown key={key++} text={remaining} />);
      break;
    }
    if (earliest > 0) {
      nodes.push(
        <InlineBoldMarkdown key={key++} text={remaining.slice(0, earliest)} />
      );
    }
    nodes.push(
      <mark
        key={key++}
        className="rounded bg-red-100 px-0.5 text-red-900"
        title="Flagged by rx-ray's framing rules"
      >
        {remaining.slice(earliest, earliest + matchLength)}
      </mark>
    );
    remaining = remaining.slice(earliest + matchLength);
  }
  return <>{nodes}</>;
}

function ColumnTitle({
  title,
  subtitle,
  highlighted = false,
}: {
  title: string;
  subtitle: string;
  highlighted?: boolean;
}) {
  return (
    <Card
      className={cn(
        "flex min-h-[5.5rem] flex-col justify-center p-4",
        highlighted && HIGHLIGHT_ACCENT
      )}
    >
      <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      <p className="mt-1 text-xs leading-4 text-slate-500">{subtitle}</p>
    </Card>
  );
}

function ColumnContent({
  highlighted = false,
  children,
}: {
  highlighted?: boolean;
  children: ReactNode;
}) {
  return (
    <Card
      className={cn(
        "flex flex-1 flex-col gap-3 p-4",
        highlighted && HIGHLIGHT_ACCENT
      )}
    >
      {children}
    </Card>
  );
}

export function NeuralColumn({
  neural,
  highlighted,
}: {
  neural: NeuralView;
  highlighted?: boolean;
}) {
  return (
    <div className="flex h-full flex-col gap-3">
      <ColumnTitle
        title="Neural only"
        subtitle="One unconstrained LLM API call. Nothing retrieved, nothing checked."
        highlighted={highlighted}
      />
      <ColumnContent highlighted={highlighted}>
        {/* This banner is part of the column by construction: never render
            unconstrained model output without this framing. */}
        <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
          <span>
            Unconstrained model output without retrieval, citations, and
            guardrails. Shown to demonstrate what rx-ray prevents; not medical
            information.
          </span>
        </div>
        <EvidenceAnswerBox title="Generated answer">
          <div className="whitespace-pre-line">
            <HighlightedProse
              text={neural.text}
              phrases={neural.advice_phrases}
            />
          </div>
        </EvidenceAnswerBox>
        {neural.advice_phrases.length > 0 ? (
          <p className="text-xs leading-5 text-red-800">
            {neural.advice_phrases.length} phrase
            {neural.advice_phrases.length === 1 ? "" : "s"} highlighted above
            would be blocked or caveated by rx-ray&apos;s framing rules.
          </p>
        ) : null}
      </ColumnContent>
    </div>
  );
}

export function SymbolicColumn({
  symbolic,
  highlighted,
}: {
  symbolic: SymbolicView;
  highlighted?: boolean;
}) {
  const coverageReport = toCoverageReport(symbolic.coverage);
  return (
    <div className="flex h-full flex-col gap-3">
      <ColumnTitle
        title="Symbolic only"
        subtitle="What the deterministic layer alone knows, before any text is generated."
        highlighted={highlighted}
      />
      <ColumnContent highlighted={highlighted}>
        <UnderstoodPanel
          state={toQueryState(symbolic.state)}
          infoText="The deterministic extraction only — rules plus RxNorm resolution, with no LLM revision. This is what the symbolic layer alone commits to."
        />
        {symbolic.coverage.length > 0 ? (
          <AnswerSection
            title="Find out what the retrieved evidence covers"
            tone="audit"
            headerExtra={
              <CoverageStatusChips
                counts={coverageStatusCounts(coverageReport)}
              />
            }
          >
            <EvidenceCoverageList
              coverage={coverageReport}
              onCitationClick={noop}
              onCoverageTargetClick={noop}
            />
          </AnswerSection>
        ) : null}
        <DossierLinks resolved={symbolic.resolved} />
      </ColumnContent>
    </div>
  );
}

function DossierLinks({
  resolved,
}: {
  resolved: SymbolicView["resolved"];
}) {
  const drugs = resolved.filter((item) => (item.name ?? item.text)?.trim());
  if (drugs.length === 0) {
    return null;
  }
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-3">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
        Review the retrieved evidence
      </p>
      <p className="mt-1 text-xs leading-5 text-slate-600">
        The symbolic layer resolved these concepts and retrieved their public
        labels. Open the full label evidence in the Drug Dossier:
      </p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {drugs.map((item) => {
          const name = item.name ?? item.text;
          return (
            <Link
              key={`${item.text}-${item.rxcui ?? "none"}`}
              href={`/dossier?drug=${encodeURIComponent(name)}&auto=1`}
              className="inline-flex items-center gap-1 rounded-full border border-[#D7C8F4] bg-white px-2.5 py-1 text-xs font-medium text-[#3B2478] transition hover:border-[#C7B4EF] hover:bg-[#F8F4FC]"
            >
              {name}
              <ArrowUpRight className="size-3.5" />
            </Link>
          );
        })}
      </div>
    </div>
  );
}

export function CombinedColumn({
  combined,
  question,
  highlighted,
}: {
  combined: CombinedView;
  question: string;
  highlighted?: boolean;
}) {
  const understanding = combined.understanding;
  const coverage = combined.coverage;
  const coverageReport =
    coverage && coverage.length > 0 ? toCoverageReport(coverage) : null;
  const citedBullets = combined.bullets.filter(
    (bullet) => bullet.citations.length > 0
  );

  return (
    <div className="flex h-full flex-col gap-3">
      <ColumnTitle
        title="rx-ray (neuro-symbolic)"
        subtitle="The full pipeline: neural drafting grounded and audited by the symbolic layer."
        highlighted={highlighted}
      />
      <ColumnContent highlighted={highlighted}>
        {understanding ? (
          <UnderstoodPanel
            state={toQueryState(understanding.state)}
            infoText="The deterministic extraction after the LLM revises it — what the full pipeline commits to, and it can differ from the symbolic-only column."
          />
        ) : null}
        {coverageReport ? (
          <AnswerSection
            title="Find out what the retrieved evidence covers"
            tone="audit"
            headerExtra={
              <CoverageStatusChips
                counts={coverageStatusCounts(coverageReport)}
              />
            }
          >
            <EvidenceCoverageList
              coverage={coverageReport}
              onCitationClick={noop}
              onCoverageTargetClick={noop}
            />
          </AnswerSection>
        ) : null}
        {combined.response ? (
          <EvidenceAnswerBox title="Evidence-based answer">
            <InlineBoldMarkdown text={combined.response} />
          </EvidenceAnswerBox>
        ) : null}
        {citedBullets.length > 0 ? (
          <AnswerSection title="Sources" badgeCount={citedBullets.length}>
            <CompareSources
              bullets={citedBullets}
              sourceLabels={combined.source_labels ?? {}}
            />
          </AnswerSection>
        ) : null}
        {combined.limitations.length > 0 ? (
          <AnswerSection
            title="Caveats & limitations"
            badgeCount={combined.limitations.length}
          >
            <CaveatsList limitations={combined.limitations} />
          </AnswerSection>
        ) : null}
        <div className="mt-auto flex flex-col gap-2 pt-1">
          {combined.safety_note ? (
            <p className="text-center text-xs leading-5 text-slate-500">
              {combined.safety_note}
            </p>
          ) : null}
          <RunLiveLink question={question} />
        </div>
      </ColumnContent>
    </div>
  );
}

function CompareSources({
  bullets,
  sourceLabels,
}: {
  bullets: CompareBullet[];
  sourceLabels: Record<string, string>;
}) {
  return (
    <div className="space-y-2">
      {bullets.map((bullet, index) => (
        <div
          key={`${bullet.text}-${index}`}
          className="rounded-md border border-[#D7C8F4] bg-white px-3 py-3"
        >
          <div className="mb-1.5 flex flex-col gap-1">
            {bullet.citations.map((citation, citationIndex) => (
              <div
                key={`${citation.source_id}-${citation.section}-${citationIndex}`}
                className="flex items-start gap-2 font-semibold leading-5 text-slate-800"
                style={{ fontSize: "14px" }}
              >
                <FileText className="mt-0.5 size-4 shrink-0 text-slate-700" />
                <span>
                  {sourceLabels[citation.source_id] ?? "Label"} ·{" "}
                  {sectionLabel(citation.section)}
                </span>
                <CitationSupportBadges
                  status={citation.support_status as CitationSupportStatus | null}
                />
              </div>
            ))}
          </div>
          <p
            className="pl-6 leading-6 text-slate-800"
            style={{ fontSize: "14px" }}
          >
            <InlineBoldMarkdown text={bullet.text} />
          </p>
        </div>
      ))}
    </div>
  );
}

function RunLiveLink({ question }: { question: string }) {
  return (
    <Link
      href={`/?q=${encodeURIComponent(question)}`}
      className="mt-1 inline-flex items-center justify-center gap-1.5 rounded-md border border-[#C7B4EF] bg-[#FBF9FE] px-3 py-2 text-center text-xs font-medium text-[#3B2478] transition hover:bg-[#F1ECFB]"
    >
      Run this question live to explore the full evidence
      <ArrowUpRight className="size-3.5 shrink-0" />
    </Link>
  );
}
