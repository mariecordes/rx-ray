"use client";

import { AlertTriangle } from "lucide-react";
import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { sectionLabels } from "@/lib/format";
import { cn } from "@/lib/utils";

import type {
  CombinedView,
  NeuralView,
  SymbolicView,
} from "./compare-types";

const coverageStatusClasses: Record<string, string> = {
  addressed: "border-emerald-200 bg-emerald-50 text-emerald-800",
  not_found_in_evidence: "border-amber-200 bg-amber-50 text-amber-800",
  not_retrieved: "border-slate-200 bg-slate-50 text-slate-600",
  out_of_scope: "border-slate-200 bg-slate-50 text-slate-500",
};

const coverageStatusLabels: Record<string, string> = {
  addressed: "Addressed",
  not_found_in_evidence: "Not found in evidence",
  not_retrieved: "Not retrieved",
  out_of_scope: "Out of scope",
};

function sectionLabel(section: string): string {
  return sectionLabels[section] ?? section.replaceAll("_", " ");
}

/** Minimal **bold** renderer, same behavior as the Ask flow's helper. */
function InlineBold({ text }: { text: string }) {
  const segments = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {segments.map((segment, index) => {
        const isBold = segment.startsWith("**") && segment.endsWith("**");
        return isBold ? (
          <strong key={index}>{segment.slice(2, -2)}</strong>
        ) : (
          segment
        );
      })}
    </>
  );
}

/** Split text on detected advice phrases (case-insensitive) and mark them. */
function HighlightedProse({
  text,
  phrases,
}: {
  text: string;
  phrases: string[];
}) {
  if (phrases.length === 0) {
    return <InlineBold text={text} />;
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
      nodes.push(<InlineBold key={key++} text={remaining} />);
      break;
    }
    if (earliest > 0) {
      nodes.push(<InlineBold key={key++} text={remaining.slice(0, earliest)} />);
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

function ColumnShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <Card className="flex h-full flex-col">
      <div className="border-b border-slate-100 p-4">
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
        <p className="mt-0.5 text-xs leading-4 text-slate-500">{subtitle}</p>
      </div>
      <div className="flex flex-1 flex-col gap-3 p-4">{children}</div>
    </Card>
  );
}

function Chip({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium",
        className ?? "border-slate-200 bg-slate-50 text-slate-700"
      )}
    >
      {children}
    </span>
  );
}

export function NeuralColumn({ neural }: { neural: NeuralView }) {
  return (
    <ColumnShell
      title="LLM only"
      subtitle="One unconstrained model call — nothing retrieved, nothing checked."
    >
      {/* This banner is part of the column by construction: never render
          unconstrained model output without this framing. */}
      <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
        <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
        <span>
          Unconstrained model output — no retrieval, no citations, no
          guardrails. Shown to demonstrate what rx-ray prevents; not medical
          information.
        </span>
      </div>
      <div className="whitespace-pre-line text-sm leading-6 text-slate-800">
        <HighlightedProse text={neural.text} phrases={neural.advice_phrases} />
      </div>
      {neural.advice_phrases.length > 0 ? (
        <p className="text-xs leading-5 text-red-800">
          {neural.advice_phrases.length} phrase
          {neural.advice_phrases.length === 1 ? "" : "s"} highlighted above
          would be blocked or caveated by rx-ray&apos;s framing rules.
        </p>
      ) : null}
    </ColumnShell>
  );
}

export function SymbolicColumn({ symbolic }: { symbolic: SymbolicView }) {
  const stateGroups: Array<[string, string[]]> = [
    ["Drugs", symbolic.state.drugs],
    ["Current medications", symbolic.state.current_medications],
    ["Allergies", symbolic.state.allergies],
    ["Conditions", symbolic.state.conditions],
    ["Patient context", symbolic.state.patient_context],
    ["Intents", symbolic.state.intents],
  ];
  const sectionEntries = Object.entries(symbolic.section_counts);
  return (
    <ColumnShell
      title="Symbolic only"
      subtitle="What the deterministic layer knows — before any text is generated."
    >
      <div className="flex flex-col gap-1.5">
        {stateGroups
          .filter(([, values]) => values.length > 0)
          .map(([label, values]) => (
            <div key={label} className="flex flex-wrap items-center gap-1">
              <span className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
                {label}
              </span>
              {values.map((value) => (
                <Chip key={value}>{value}</Chip>
              ))}
            </div>
          ))}
      </div>

      <div>
        <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-500">
          Resolved RxNorm concepts
        </p>
        <ul className="flex flex-col gap-1 text-xs leading-5 text-slate-700">
          {symbolic.resolved.map((item) => (
            <li key={`${item.text}-${item.rxcui ?? "none"}`}>
              <span className="font-medium">{item.text}</span>
              {item.rxcui ? (
                <>
                  {" "}
                  → {item.name}{" "}
                  <span className="text-slate-400">
                    (RXCUI {item.rxcui}
                    {item.tty ? ` · ${item.tty}` : ""})
                  </span>
                </>
              ) : (
                <span className="text-amber-700"> → not resolved</span>
              )}
            </li>
          ))}
          {symbolic.resolved.length === 0 ? (
            <li className="text-slate-500">No drug mentions resolved.</li>
          ) : null}
        </ul>
      </div>

      {sectionEntries.length > 0 ? (
        <div>
          <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-500">
            Retrieved label sections
          </p>
          <div className="flex flex-wrap gap-1">
            {sectionEntries.map(([section, count]) => (
              <Chip key={section}>
                {sectionLabel(section)} × {count}
              </Chip>
            ))}
          </div>
        </div>
      ) : null}

      <div>
        <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-500">
          Deterministic coverage audit
        </p>
        <ul className="flex flex-col gap-1.5">
          {symbolic.coverage.map((item, index) => (
            <li key={index} className="flex flex-wrap items-center gap-1.5">
              <Chip
                className={
                  coverageStatusClasses[item.status] ??
                  "border-slate-200 bg-slate-50 text-slate-600"
                }
              >
                {coverageStatusLabels[item.status] ?? item.status}
              </Chip>
              <span className="text-xs leading-5 text-slate-700">
                {item.label}
                <span className="text-slate-400"> · {item.category}</span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </ColumnShell>
  );
}

export function CombinedColumn({ combined }: { combined: CombinedView }) {
  return (
    <ColumnShell
      title="rx-ray (neuro-symbolic)"
      subtitle="Grounded synthesis with whitelisted citations, audits, and enforced caveats."
    >
      <p className="text-sm leading-6 text-slate-800">
        <InlineBold text={combined.response} />
      </p>

      {combined.bullets.length > 0 ? (
        <ul className="flex flex-col gap-2">
          {combined.bullets.map((bullet, index) => (
            <li
              key={index}
              className="rounded-md border border-slate-100 bg-slate-50/60 px-3 py-2"
            >
              <p className="text-xs leading-5 text-slate-800">
                <InlineBold text={bullet.text} />
              </p>
              <div className="mt-1 flex flex-wrap gap-1">
                {bullet.citations.map((citation, citationIndex) => (
                  <Chip
                    key={citationIndex}
                    className={
                      citation.support_status === "accurate"
                        ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                        : citation.support_status
                          ? "border-amber-200 bg-amber-50 text-amber-800"
                          : undefined
                    }
                  >
                    {sectionLabel(citation.section)}
                    {citation.support_status === "accurate"
                      ? " · verified"
                      : citation.support_status
                        ? " · flagged"
                        : ""}
                  </Chip>
                ))}
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      {combined.limitations.length > 0 ? (
        <div>
          <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-500">
            Stated limitations
          </p>
          <ul className="list-disc pl-4 text-xs leading-5 text-slate-600">
            {combined.limitations.map((limitation, index) => (
              <li key={index}>
                <InlineBold text={limitation} />
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {combined.safety_note ? (
        <p className="mt-auto text-[11px] leading-4 text-slate-500">
          {combined.safety_note}
        </p>
      ) : null}
    </ColumnShell>
  );
}
