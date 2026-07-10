"use client";

import { Check, ChevronDown, Minus, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import fixturesJson from "@/data/compare-fixtures.json";
import { Card, CardContent } from "@/components/ui/card";
import { InfoTooltip } from "@/components/ui/info-tooltip";
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

// Column / scorecard order: raw LLM on the left, rx-ray highlighted in the
// middle (it combines the two), deterministic layer on the right.
const MODE_ORDER: CompareMode[] = ["neural", "combined", "symbolic"];

const MODE_HEADINGS: Record<CompareMode, string> = {
  neural: "Neural only",
  symbolic: "Symbolic only",
  combined: "rx-ray (neuro-symbolic)",
};

// Hidden per user feedback: the scorecard sits far down the page and its
// current rows don't clearly tell the "raw LLM looks reckless" story. Code
// kept intact to revisit later rather than deleted.
const SHOW_SCORECARD = false;

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
    <div className="flex flex-col gap-5">
      <Card>
        <CardContent className="pb-7 pt-6">
          <div className="flex items-center justify-center gap-2">
            <h1 className="text-sm font-semibold uppercase tracking-wide text-slate-600">
              Ask a Question
            </h1>
            <InfoTooltip text="The same question run three ways: an unconstrained LLM API call, rx-ray's deterministic layer alone, and the full neuro-symbolic pipeline where the symbolic layer grounds and audits the model." />
          </div>
          <p className="mx-auto mt-1 text-center text-sm leading-6 text-slate-500">
            Every output below is a precomputed run of the real system. Pick a
            question and compare what each approach can and cannot back up.
          </p>
          <QuestionPicker
            questions={fixtures.questions}
            selectedId={selected.id}
            onSelect={setSelectedId}
          />
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <NeuralColumn neural={selected.neural} />
        <CombinedColumn
          combined={selected.combined}
          question={selected.question}
          highlighted
        />
        <SymbolicColumn symbolic={selected.symbolic} />
      </div>

      {SHOW_SCORECARD ? (
        <ScorecardCard scorecard={selected.scorecard} />
      ) : null}

      <p className="text-xs leading-5 text-slate-500">
        Precomputed outputs of the real pipeline, generated{" "}
        {fixtures.generated_at.slice(0, 10)}
        {fixtures.synthesis_model
          ? ` with ${fixtures.synthesis_model}`
          : ""}
        {". "}
        See the About page for how rx-ray works. Educational demonstration only;
        none of the columns are medical advice.
      </p>
    </div>
  );
}

function QuestionPicker({
  questions,
  selectedId,
  onSelect,
}: {
  questions: CompareQuestion[];
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const selected =
    questions.find((question) => question.id === selectedId) ?? questions[0];

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    function handlePointerDown(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  return (
    <div ref={containerRef} className="relative mx-auto mt-5 max-w-4xl">
      <button
        type="button"
        onClick={() => setIsOpen((current) => !current)}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        className="flex min-h-11 w-full items-center gap-2 rounded-md border border-[#C7B4EF] bg-white px-3 py-2 text-left shadow-sm outline-none transition focus:border-[#371E8F] focus:ring-2 focus:ring-[#E8DDF9]"
      >
        {selected ? (
          <>
            <CategoryChip category={selected.category} />
            <span
              className="flex-1 truncate text-slate-950"
              style={{ fontSize: "15px" }}
            >
              {selected.question}
            </span>
          </>
        ) : null}
        <ChevronDown
          className={cn(
            "size-4 shrink-0 text-slate-500 transition-transform",
            isOpen && "rotate-180"
          )}
        />
      </button>

      {isOpen ? (
        <div
          role="listbox"
          className="absolute z-20 mt-1 max-h-96 w-full overflow-y-auto rounded-md border border-slate-200 bg-white p-1 shadow-lg"
        >
          <div className="cursor-not-allowed px-3 py-2 text-sm italic text-slate-400">
            Type your own question… (coming soon)
          </div>
          {questions.map((question) => (
            <button
              key={question.id}
              type="button"
              role="option"
              aria-selected={question.id === selectedId}
              onClick={() => {
                onSelect(question.id);
                setIsOpen(false);
              }}
              className={cn(
                "flex w-full items-start gap-2 rounded-md px-3 py-2 text-left transition",
                question.id === selectedId
                  ? "bg-[#F1ECFB]"
                  : "hover:bg-slate-50"
              )}
            >
              <CategoryChip category={question.category} />
              <span className="text-sm leading-5 text-slate-800">
                {question.question}
              </span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function CategoryChip({ category }: { category: string }) {
  return (
    <span className="mt-0.5 shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
      {categoryLabels[category] ?? category}
    </span>
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
          (framing-rule regexes and structured pipeline data). &ldquo;—&rdquo;
          means the property does not apply to that mode.
        </p>
      </div>
      <div className="overflow-x-auto p-4">
        <table className="w-full min-w-[28rem] text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="pb-2 pr-4 font-medium">Property</th>
              {MODE_ORDER.map((mode) => (
                <th
                  key={mode}
                  className={cn(
                    "pb-2 pr-4 font-medium",
                    mode === "combined" &&
                      "rounded-t-md border-x border-t border-[#D7C8F4] bg-[#FBF9FE] px-3 pt-2 text-[#3B2478]"
                  )}
                >
                  {MODE_HEADINGS[mode]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {SCORECARD_ROWS.map((row, rowIndex) => (
              <tr key={row.key} className="border-t border-slate-100">
                <td className="py-2 pr-4 text-slate-700">{row.label}</td>
                {MODE_ORDER.map((mode) => (
                  <td
                    key={mode}
                    className={cn(
                      "py-2 pr-4",
                      mode === "combined" &&
                        "border-x border-[#D7C8F4] bg-[#FBF9FE] px-3",
                      mode === "combined" &&
                        rowIndex === SCORECARD_ROWS.length - 1 &&
                        "rounded-b-md border-b"
                    )}
                  >
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
