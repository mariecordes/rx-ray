"use client";

import { ChevronDown, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useState, type ReactNode } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface CollapsibleSectionProps {
  title: string;
  children: ReactNode;
  isOpen: boolean;
  onToggle: () => void;
}

function CollapsibleSection({
  title,
  children,
  isOpen,
  onToggle,
}: CollapsibleSectionProps) {
  return (
    <div className="border-b border-slate-200 last:border-b-0">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={isOpen}
        className="flex w-full items-center justify-between rounded-sm px-2 py-3 text-left transition hover:bg-slate-50"
      >
        <span className="font-semibold text-slate-900">{title}</span>
        {isOpen ? (
          <ChevronDown className="size-4 shrink-0 text-slate-500" />
        ) : (
          <ChevronRight className="size-4 shrink-0 text-slate-500" />
        )}
      </button>
      <div
        className={`overflow-hidden transition-all duration-300 ease-in-out ${
          isOpen ? "max-h-[80rem] opacity-100" : "max-h-0 opacity-0"
        }`}
      >
        <div className="px-2 pb-5 text-sm leading-relaxed text-slate-700">
          {children}
        </div>
      </div>
    </div>
  );
}

function RxRay() {
  return (
    <span className="inline-block rounded border border-[#D7C8F4] bg-[#EEE7FA] px-1.5 py-0.5 align-baseline text-xs font-semibold leading-none text-[#3B2478]">
      rx-ray
    </span>
  );
}

const link =
  "font-medium text-violet-700 underline underline-offset-2 hover:text-violet-900";

export function AboutPage() {
  const [openSection, setOpenSection] = useState<string>("What you can do here");

  const handleToggle = (section: string) => {
    setOpenSection(openSection === section ? "" : section);
  };

  const isOpen = (section: string) => openSection === section;

  return (
    <div className="w-full">
      <Card>
        <CardHeader>
          <CardTitle>About rx-ray</CardTitle>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            A neuro-symbolic medication-evidence explorer: where a symbolic
            layer grounds, constrains, and audits an LLM so it can summarize
            public drug information without overclaiming.
          </p>
        </CardHeader>
        <CardContent>
          <div className="space-y-0">
            <CollapsibleSection
              title="Welcome"
              isOpen={isOpen("Welcome")}
              onToggle={() => handleToggle("Welcome")}
            >
              <p className="mb-4">
                Hi! I&apos;m Marie, a data scientist based in Berlin with a deep
                interest in AI safety and in systems that stay honest about what
                they actually know.
              </p>
              <p className="mb-4">
                Medication questions are a perfect stress test for that idea. The
                stakes are real, the data is messy and incomplete, and a
                confident-sounding wrong answer is worse than no answer at all.
                It&apos;s the kind of place where a language model on its
                own is risky - and where pairing it with structured, inspectable
                evidence becomes truly useful.
              </p>
              <p className="font-medium">
                That&apos;s the question <RxRay /> explores: <strong>can the symbolic
                layer keep the neural layer honest?</strong>
              </p>
            </CollapsibleSection>

            <CollapsibleSection
              title="What you can do here"
              isOpen={isOpen("What you can do here")}
              onToggle={() => handleToggle("What you can do here")}
            >
              <p className="mb-3">
                <RxRay /> has three entry points into the same underlying
                evidence layer:
              </p><br />
              <p className="mb-3">
                💬 <strong>Ask a Question</strong> 
              </p>
              <p className="mb-3">
                Ask a natural-language medication question and get a grounded answer,
                plus a compact view of what the system understood, what evidence
                it used, how faithfully each cited source is reflected, and where
                it falls short.
              </p>
              <p className="mb-3">
                Behind every answer you can open the full evidence packet:
              </p>
              <ul className="mb-3 ml-6 list-disc space-y-2">
                <li>
                  <strong>Evidence Map</strong>: an interactive graph linking the
                  concepts extracted from your question to the resolved
                  medications, label sources, and label sections that were used.
                  This represents a map of the symbolic layer the LLM receives to 
                  inform its response generation.
                </li>
                <li>
                  <strong>Supporting Evidence</strong>: the underlying RxNorm
                  drug network and the specific FDA label text, with source
                  provenance for every claim.
                </li>
              </ul><br />
              <p className="mb-3">
                ⚖️ <strong>Compare</strong> 
              </p>
              <p>
                A handful of curated questions run through three
                modes side by side: an unconstrained LLM call (neural only), the symbolic
                layer alone based on purely deterministic rules with no generation, 
                and the full neuro-symbolic pipeline grounding and auditing the model. 
                To avoid LLM cost and reduce page load, this page uses precomputed 
                real pipeline outputs.
              </p><br />
              <p className="mb-3">
                🔎 <strong>Drug Dossier</strong> 
              </p>
              <p className="mb-3">
                Search a single medication and inspect its raw evidence directly: 
                the RxNorm concept network and its public FDA label sections to explore
                the drug and its labels and relationships to other medications yourself.
              </p>
            </CollapsibleSection>

            <CollapsibleSection
              title="How it works"
              isOpen={isOpen("How it works")}
              onToggle={() => handleToggle("How it works")}
            >
              <p className="mb-3">
                <RxRay /> runs a neuro-symbolic pipeline where each step is
                inspectable and the symbolic layer sets the boundaries for the
                neural one:
              </p>
              <p className="mb-3">
                💭 <strong>Query understanding:</strong> deterministic rules
                extract a structured state from your question: primary drug,
                other mentioned and current medications, allergies, conditions,
                patient context, and intent. An LLM can optionally refine that
                state, but the structure stays explicit and reviewable.
              </p>
              <p className="mb-3">
                🔍 <strong>Symbolic retrieval:</strong> resolved medications are
                looked up in RxNorm to build a local concept network, and public
                FDA label text is retrieved from OpenFDA, while being targeted at the
                sections that match the question&apos;s intent.
              </p>
              <p className="mb-3">
                ✅ <strong>Coverage audit:</strong> before any answer is written,
                a deterministic check compares every extracted detail against the
                retrieved evidence and labels it <em>addressed</em>,{" "}
                <em>not found in evidence</em>, <em>not retrieved</em>, or{" "}
                <em>out of scope</em>. Even before an answer is generated, the system hereby says out loud what it could
                and couldn&apos;t support.
              </p>
              <p className="mb-3">
                📋 <strong>Answer contract:</strong> that coverage report is
                compiled into an explicit contract the answer has to satisfy:
                which topics it <em>must address</em> (because evidence exists)
                and which caveats it <em>must include</em>. Expectations are set
                symbolically, before the model writes a word, so &quot;did the
                model behave&quot; becomes a checklist the system can enforce
                rather than hope for.
              </p>
              <p className="mb-3">
                💬 <strong>Grounded synthesis:</strong> the LLM writes the summary
                against that contract, but it can only cite evidence from a
                whitelist built out of the retrieved label sections. Citations
                outside that whitelist are dropped, and an empty-citation answer
                triggers a bounded retry.
              </p>
              <p className="mb-3">
                🛡️ <strong>Deterministic enforcement:</strong> once the answer is
                written, a symbolic validation pass checks it against the
                contract. It may re-append any required caveat the model dropped,
                flag personal &quot;safe / unsafe&quot; framing, and
                relocate any claim that lacks a citation out of the sources list
                and into the stated limitations.
              </p>
              <p className="mb-3">
                🔬 <strong>Faithfulness critic:</strong> finally, a second LLM
                pass audits each citation on its own, comparing the claim against
                the exact label text it cites <em>and</em> against the final
                answer. It scores, per source, whether the claim faithfully
                represents what the label actually says and whether the answer
                reflects, omits, or contradicts it. You see that verdict as a
                badge on every source, and a serious mismatch triggers a single,
                bounded regeneration of the answer.
              </p>
            </CollapsibleSection>

            <CollapsibleSection
              title="How it's evaluated"
              isOpen={isOpen("How it's evaluated")}
              onToggle={() => handleToggle("How it's evaluated")}
            >
              <p className="mb-3">
                Guardrails you can&apos;t measure are just promises. So a good
                part of the work behind <RxRay /> went into evaluation, in two
                complementary ways:
              </p>
              <p className="mb-3">
                🔁 <strong>A repeatable evaluation harness:</strong> 42 curated
                questions, including <em>trap questions</em>{" "}
                where the only
                correct behavior is to refuse, like asking about a drug that
                doesn&apos;t exist, with structured, behavioral expectations:
                what must resolve, what the coverage audit must say, which
                guardrails must fire. The harness runs the pipeline in isolated
                modes (deterministic-only, extraction-LLM-only, full pipeline),
                so each layer&apos;s contribution is measured rather than
                assumed.
              </p>
              <p className="mb-3">
                🧪 <strong>One-off experiments:</strong> designed studies
                against a frozen system state. The largest so far: the
                faithfulness critic is an LLM judging an LLM, so I hand-labeled
                its verdicts blind and scored the judge itself. Flag precision
                0.76, flag recall 0.96 against my labels, with an error
                analysis that turned the disagreements into concrete follow-up
                work on the roadmap.
              </p>
              <p className="mb-3">
                Full methodology, metrics, and results:{" "}
                <a
                  href="https://github.com/mariecordes/rx-ray/blob/main/docs/EVALUATION.md"
                  target="_blank"
                  rel="noopener noreferrer"
                  className={link}
                >
                  docs/EVALUATION.md
                </a>
                .
              </p>
              <p>
                For a hands-on version of that same ablation, the{" "}
                <Link href="/compare" className={link}>
                  Compare
                </Link>{" "}
                page runs curated questions through the isolated modes side by
                side, so you can see what each layer contributes on a specific
                example rather than just in the aggregate numbers.
              </p>
            </CollapsibleSection>

            <CollapsibleSection
              title="Goal & impact"
              isOpen={isOpen("Goal & impact")}
              onToggle={() => handleToggle("Goal & impact")}
            >
              <p className="mb-3">
                The goal of <RxRay /> isn&apos;t to be a medication chatbot -
                ask a question, get an answer, done. It&apos;s to demonstrate a
                pattern I care about: a{" "}
                <strong>
                  symbolic layer that grounds, constrains, and audits a language
                  model
                </strong>{" "}
                instead of letting it answer freely. The interesting part
                isn&apos;t the answer but the provenance and the
                guardrails around it.
              </p>
              <p className="mb-3">
                That&apos;s also why everything is open to explore. Rather than
                trusting a generated answer on faith, you can dig into the
                actual evidence: browse the real FDA labels the summary
                was drawn from, navigate the RxNorm drug network, and see
                exactly which sources were retrieved and which details the system
                couldn&apos;t find coverage for. Having all of that in one place
                lets you develop a more grounded sense of what the data actually
                says and how much the LLM is doing for you compared to
                hunting through raw label text yourself.
              </p>
              <p className="mb-3">
                That matters most exactly where LLMs are riskiest: high-stakes,
                trust-sensitive domains where overclaiming does harm.{" "}
                <RxRay /> treats &quot;I don&apos;t have evidence for
                that&quot; as a first-class, deterministic output rather than
                something the model is left to remember to say.
              </p>
              <p className="mb-3">
                To be clear about the limits: RxNorm is terminology data and FDA
                label text is incomplete for things like true drug-interaction
                discovery. <RxRay /> is an{" "}
                <strong>educational prototype</strong>, not a clinical tool. While it
                summarizes and visualizes public information, it does not
                give medical advice, diagnoses, or treatment recommendations.
                For medical questions, please talk to a qualified clinician or
                pharmacist.
              </p>
              <p>
                Within those limits, it&apos;s a small, honest study in
                computational trust: what does it take for an AI system to be
                useful <em>and</em> stay within what the evidence actually
                supports?
              </p>
            </CollapsibleSection>

            <CollapsibleSection
              title="Tech stack"
              isOpen={isOpen("Tech stack")}
              onToggle={() => handleToggle("Tech stack")}
            >
              <p className="mb-3">
                <strong>Frontend:</strong> Next.js, React, TypeScript, Tailwind
                CSS, with D3 force layouts for the network and evidence-map
                visualizations.
              </p>
              <p className="mb-3">
                <strong>Backend:</strong> Python FastAPI, with OpenAI API
                integration for query refinement, grounded synthesis, and a
                second-pass faithfulness critic that audits the answer against its
                own sources.
              </p>
              <p className="mb-3">
                <strong>Data:</strong> RxNorm{" "}
                <a
                  href="https://www.nlm.nih.gov/research/umls/rxnorm/docs/prescribe.html"
                  target="_blank"
                  rel="noopener noreferrer"
                  className={link}
                >
                  Current Prescribable Content
                </a>{" "}
                (April 2026 release, exported to parquet for fast local
                retrieval) and public drug labels from the{" "}
                <a
                  href="https://open.fda.gov/apis/drug/label/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className={link}
                >
                  OpenFDA
                </a>{" "}
                API. I chose the prescribable subset deliberately: it&apos;s
                license-free and drawn from the same FDA label data as OpenFDA,
                so the terminology and the evidence line up.
              </p>
              <p className="mb-3">
                <strong>Safety design:</strong> deterministic state extraction
                and coverage checks, a coverage-driven answer contract, a citation
                whitelist, deterministic enforcement of required caveats, and a
                second-pass LLM faithfulness critic with bounded regeneration.
                Every LLM call falls back to deterministic behavior when no API
                key is configured. With the critic off, the answer simply carries
                no faithfulness badges rather than guessing.
              </p>
              <p className="mb-3">
                <strong>Deployment:</strong> Railway (backend) and Vercel
                (frontend).
              </p>
              <p>
                <strong>Code:</strong> for a more in-depth look you can check out the full repo here:{" "}
                <a
                  href="https://github.com/mariecordes/rx-ray"
                  target="_blank"
                  rel="noopener noreferrer"
                  className={link}
                >
                  rx-ray
                </a>
                .
              </p>
            </CollapsibleSection>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
