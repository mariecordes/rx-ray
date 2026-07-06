"use client";

import { Check, Minus, X } from "lucide-react";
import { useState } from "react";

import fixturesJson from "@/data/compare-fixtures.json";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

import {
  CombinedColumn,
  NeuralColumn,
  SymbolicColumn,
} from "./mode-columns";
import type {
  CompareFixtures,
  CompareMode,
  CompareQuestion,
  Scorecard,
} from "./compare-types";

// Double assertion: the inferred JSON literal type unions the per-question
// source_label keys, which is not directly comparable to Record<string,string>.
const fixtures = fixturesJson as unknown as CompareFixtures;

const categoryLabels: Record<string, string> = {
  trap: "Trap",
  interaction_2: "Interaction",
  allergy: "Allergy",
  pregnancy_lactation: "Pregnancy",
  expected_gap: "Evidence gap",
  complex: "Complex",
};

const MODES: CompareMode[] = ["neural", "symbolic", "combined"];

const MODE_HEADINGS: Record<CompareMode, string> = {
  neural: "LLM only",
  symbolic: "Symbolic only",
  combined: "rx-ray",
};

interface ScorecardRowConfig {
  key: keyof Pick<
    Scorecard,
    | "cited_sources"
    | "advice_language_hits"
    | "trap_handled"
    | "stated_limitations"
    | "safety_note"
  >;
  label: string;
  kind: "count" | "flag-count" | "good-bool";
}

const SCORECARD_ROWS: ScorecardRowConfig[] = [
  { key: "cited_sources", label: "Cited label sources", kind: "count" },
  {
    key: "advice_language_hits",
    label: "Personal-advice / definitive phrases",
    kind: "flag-count",
  },
  {
    key: "trap_handled",
    label: "Handles the unknown drug correctly",
    kind: "good-bool",
  },
  {
    key: "stated_limitations",
    label: "Structured, machine-checkable limitations",
    kind: "count",
  },
  {
    key: "safety_note",
    label: "Points the reader to a clinician",
    kind: "good-bool",
  },
];

export function ComparePage() {
  const [selectedId, setSelectedId] = useState(fixtures.questions[0]?.id);
  const selected =
    fixtures.questions.find((question) => question.id === selectedId) ??
    fixtures.questions[0];

  if (!selected) {
    return null;
  }

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-4">
        <h1 className="text-lg font-semibold text-slate-900">
          Neural vs symbolic vs neuro-symbolic
        </h1>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
          The same question, three ways: an unconstrained LLM, rx-ray&apos;s
          deterministic layer alone, and the full neuro-symbolic pipeline
          where the symbolic layer grounds and audits the model. Every output
          below is a precomputed run of the real system — pick a question and
          compare what each approach can and cannot back up.
        </p>
      </Card>

      <div className="flex flex-wrap gap-2">
        {fixtures.questions.map((question) => (
          <QuestionButton
            key={question.id}
            question={question}
            selected={question.id === selected.id}
            onSelect={() => setSelectedId(question.id)}
          />
        ))}
      </div>

      <p className="text-sm leading-5 text-slate-600">
        <span className="font-medium text-slate-800">
          &ldquo;{selected.question}&rdquo;
        </span>
        {selected.hint ? <span> — {selected.hint}</span> : null}
      </p>

      <div className="grid gap-4 lg:grid-cols-3">
        <NeuralColumn neural={selected.neural} />
        <SymbolicColumn symbolic={selected.symbolic} />
        <CombinedColumn combined={selected.combined} />
      </div>

      <ScorecardCard scorecard={selected.scorecard} />

      <p className="text-xs leading-5 text-slate-500">
        Precomputed outputs of the real pipeline, generated{" "}
        {fixtures.generated_at.slice(0, 10)}
        {fixtures.synthesis_model
          ? ` with ${fixtures.synthesis_model}`
          : ""}{" "}
        — see the About page for how rx-ray works. Educational demonstration
        only; none of the columns are medical advice.
      </p>
    </div>
  );
}

function QuestionButton({
  question,
  selected,
  onSelect,
}: {
  question: CompareQuestion;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "flex items-center gap-2 rounded-md border px-3 py-1.5 text-left text-sm transition",
        selected
          ? "border-[#3B2478] bg-[#EEE7FA] text-[#3B2478] shadow-sm"
          : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50"
      )}
    >
      <span
        className={cn(
          "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
          selected
            ? "bg-[#3B2478]/10 text-[#3B2478]"
            : "bg-slate-100 text-slate-500"
        )}
      >
        {categoryLabels[question.category] ?? question.category}
      </span>
      <span className="max-w-64 truncate">{question.question}</span>
    </button>
  );
}

function ScorecardCard({ scorecard }: { scorecard: Scorecard }) {
  return (
    <Card>
      <div className="border-b border-slate-100 p-4">
        <h2 className="text-sm font-semibold text-slate-900">
          Property scorecard
        </h2>
        <p className="mt-0.5 text-xs leading-4 text-slate-500">
          Every cell is computed deterministically from the outputs above
          (framing-rule regexes and structured pipeline data) — no judgment
          calls. &ldquo;—&rdquo; means the property does not apply to that
          mode.
        </p>
      </div>
      <div className="overflow-x-auto p-4">
        <table className="w-full min-w-[28rem] text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="pb-2 pr-4 font-medium">Property</th>
              {MODES.map((mode) => (
                <th key={mode} className="pb-2 pr-4 font-medium">
                  {MODE_HEADINGS[mode]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {SCORECARD_ROWS.map((row) => (
              <tr key={row.key} className="border-t border-slate-100">
                <td className="py-2 pr-4 text-slate-700">{row.label}</td>
                {MODES.map((mode) => (
                  <td key={mode} className="py-2 pr-4">
                    <ScorecardCell
                      kind={row.kind}
                      value={scorecard[row.key][mode]}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function ScorecardCell({
  kind,
  value,
}: {
  kind: ScorecardRowConfig["kind"];
  value: number | boolean | null;
}) {
  if (value === null || value === undefined) {
    return (
      <span className="inline-flex items-center gap-1 text-slate-400">
        <Minus className="size-3.5" /> —
      </span>
    );
  }
  if (kind === "good-bool") {
    return value ? (
      <span className="inline-flex items-center gap-1 font-medium text-emerald-700">
        <Check className="size-4" /> yes
      </span>
    ) : (
      <span className="inline-flex items-center gap-1 font-medium text-red-700">
        <X className="size-4" /> no
      </span>
    );
  }
  const count = Number(value);
  const isBad =
    (kind === "flag-count" && count > 0) || (kind === "count" && count === 0);
  return (
    <span
      className={cn(
        "font-medium tabular-nums",
        isBad ? "text-red-700" : "text-slate-800",
        kind === "count" && count > 0 ? "text-emerald-700" : undefined
      )}
    >
      {count}
    </span>
  );
}
