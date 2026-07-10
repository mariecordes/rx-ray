"use client";

import {
  FormEvent,
  type RefObject,
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Loader2,
  Search,
} from "lucide-react";
import { useSearchParams } from "next/navigation";

import { EvidenceMapD3 } from "@/components/question-evidence-map-d3";
import {
  DEMO_QUERY,
  demoQueryAnswer,
} from "@/components/demo-query-answer-fixture";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { EvidenceCoverageTarget } from "@/components/dossier/evidence-model";
import { labelSourceProfilesFromEvidence } from "@/components/dossier/label-source-profile";
import { QueryUnderstandingPanel } from "@/components/dossier/generated-response";
import {
  DossierResults,
  EmptyState,
  SupportingEvidence,
} from "@/components/dossier/supporting-evidence";
import {
  DrugDossier,
  EvidenceCitation,
  QueryAnswerResponse,
  QueryUnderstandingResponse,
} from "@/lib/types";
import { requestJsonWithRetry } from "@/lib/api-client";
import { frontendParameters } from "@/lib/parameters";
import { cn } from "@/lib/utils";

const frontendLimits = frontendParameters.limits;

export function DossierExplorer() {
  return <AskQuestionExperience />;
}

type PageNavSection = {
  id: string;
  label: string;
  ref: RefObject<HTMLDivElement | null>;
  isVisible: boolean;
  indent?: boolean;
};

function useActivePageSection(sections: PageNavSection[]) {
  const [activeId, setActiveId] = useState(sections[0]?.id ?? "");
  const clickedSectionLockUntilRef = useRef(0);

  const updateActiveSection = useCallback(() => {
    if (Date.now() < clickedSectionLockUntilRef.current) {
      return;
    }
    const visibleSections = sections.filter(
      (section) => section.isVisible && section.ref.current
    );
    if (!visibleSections.length) {
      return;
    }

    const topOffset = 96;
    const sectionPositions = visibleSections
      .map((section) => ({
        section,
        rect: section.ref.current?.getBoundingClientRect(),
      }))
      .filter(
        (
          entry
        ): entry is {
          section: PageNavSection;
          rect: DOMRect;
        } => Boolean(entry.rect)
      )
      .filter(
        ({ rect }) => rect.bottom > topOffset && rect.top < window.innerHeight
      )
      .sort((left, right) => left.rect.top - right.rect.top);

    const activeSection =
      [...sectionPositions]
        .reverse()
        .find(({ rect }) => rect.top <= topOffset)?.section ??
      sectionPositions[0]?.section;

    if (activeSection) {
      setActiveId(activeSection.id);
    }
  }, [sections]);

  useEffect(() => {
    let animationFrame = 0;
    function requestUpdate() {
      window.cancelAnimationFrame(animationFrame);
      animationFrame = window.requestAnimationFrame(updateActiveSection);
    }

    requestUpdate();
    window.addEventListener("scroll", requestUpdate, { passive: true });
    window.addEventListener("resize", requestUpdate);

    return () => {
      window.cancelAnimationFrame(animationFrame);
      window.removeEventListener("scroll", requestUpdate);
      window.removeEventListener("resize", requestUpdate);
    };
  }, [updateActiveSection]);

  const activateSection = useCallback((sectionId: string) => {
    clickedSectionLockUntilRef.current = Date.now() + 1200;
    setActiveId(sectionId);
    window.setTimeout(() => {
      if (Date.now() >= clickedSectionLockUntilRef.current) {
        clickedSectionLockUntilRef.current = 0;
      }
    }, 1250);
  }, []);

  useEffect(() => {
    if (!sections.some((section) => section.isVisible && section.id === activeId)) {
      setActiveId(sections.find((section) => section.isVisible)?.id ?? "");
    }
  }, [activeId, sections]);

  return [activeId, activateSection] as const;
}

function AskPageNavigation({
  activeId,
  onActivate,
  sections,
}: {
  activeId: string;
  onActivate: (sectionId: string) => void;
  sections: PageNavSection[];
}) {
  const visibleSections = sections.filter((section) => section.isVisible);

  function scrollToSection(section: PageNavSection) {
    onActivate(section.id);
    section.ref.current?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }

  return (
    <aside className="hidden md:block">
      <nav className="sticky top-6 space-y-1">
        <p className="px-2 pb-2 text-[14px] font-semibold uppercase tracking-wide text-slate-500">
          On this page
        </p>
        {visibleSections.map((section) => (
          <button
            key={section.id}
            type="button"
            onClick={() => scrollToSection(section)}
            className={cn(
              "flex w-full items-center rounded-md px-2 py-1.5 text-left font-semibold uppercase tracking-wide transition",
              section.indent && "pl-5 font-medium italic",
              activeId === section.id
                ? "bg-[#F1ECFB] text-[#371E8F]"
                : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"
            )}
            style={{
              fontSize: "14px",
              fontStyle: section.indent ? "italic" : "normal",
              lineHeight: "16px",
            }}
          >
            <span>{section.label}</span>
          </button>
        ))}
      </nav>
    </aside>
  );
}

export function AskQuestionExperience({
  autoDemo = false,
}: {
  autoDemo?: boolean;
} = {}) {
  const searchParams = useSearchParams();
  const initialQuestion = autoDemo
    ? DEMO_QUERY
    : searchParams.get("q")?.trim() ||
      "Can I take ibuprofen for my migraine if I'm allergic to aspirin?";
  const [question, setQuestion] = useState(initialQuestion);
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
  const [highlightEvidenceRxcui, setHighlightEvidenceRxcui] =
    useState<string | null>(null);
  const askQuestionRef = useRef<HTMLDivElement>(null);
  const generatedResponseRef = useRef<HTMLDivElement>(null);
  const evidenceMapRef = useRef<HTMLDivElement>(null);
  const supportingEvidenceRef = useRef<HTMLDivElement>(null);
  const supportingEvidenceContentRef = useRef<HTMLDivElement>(null);
  const supportingEvidencePanelRef = useRef<HTMLDivElement>(null);
  const drugNetworkNavRef = useRef<HTMLDivElement>(null);
  const drugLabelsNavRef = useRef<HTMLDivElement>(null);
  const queryRequestRef = useRef(0);
  const didAutoRunRef = useRef(false);
  const evidenceMapSourceProfilesById = useMemo(
    () => labelSourceProfilesFromEvidence(dossier, queryAnswer),
    [dossier, queryAnswer]
  );
  const hasGeneratedResponseContent = Boolean(
    isUnderstandingLoading ||
      isAnswerLoading ||
      queryError ||
      queryUnderstanding ||
      queryAnswer
  );
  const hasSupportingEvidence = Boolean(
    dossier && queryAnswer && !isAnswerLoading && !isUnderstandingLoading
  );
  const navigationSections = useMemo(
    () =>
      [
        {
          id: "ask",
          label: "Ask a question",
          ref: askQuestionRef,
          isVisible: true,
        },
        {
          id: "response",
          label: "Generated response",
          ref: generatedResponseRef,
          isVisible: hasGeneratedResponseContent,
        },
        {
          id: "map",
          label: "Evidence map",
          ref: evidenceMapRef,
          isVisible: hasSupportingEvidence && isEvidenceOpen,
        },
        {
          id: "evidence",
          label: "Supporting evidence",
          ref: supportingEvidencePanelRef,
          isVisible: hasSupportingEvidence && isEvidenceOpen,
        },
        {
          id: "network",
          label: "Drug network",
          ref: drugNetworkNavRef,
          isVisible: hasSupportingEvidence && isEvidenceOpen,
          indent: true,
        },
        {
          id: "labels",
          label: "Drug labels",
          ref: drugLabelsNavRef,
          isVisible: hasSupportingEvidence && isEvidenceOpen,
          indent: true,
        },
      ] satisfies PageNavSection[],
    [hasGeneratedResponseContent, hasSupportingEvidence, isEvidenceOpen]
  );
  const [activeNavSection, activateNavSection] =
    useActivePageSection(navigationSections);

  function handleAnswerCitationClick(citation: EvidenceCitation) {
    setHighlightCitation(citation);
    setHighlightEvidenceRxcui(null);
    setIsEvidenceOpen(true);
    window.requestAnimationFrame(() => {
      supportingEvidenceRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  }

  function handleCoverageTargetClick(target: EvidenceCoverageTarget) {
    setHighlightEvidenceRxcui(target.rxcui);
    setHighlightCitation(null);
    setIsEvidenceOpen(true);
    window.requestAnimationFrame(() => {
      supportingEvidenceRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  }

  function handleQuestionSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void runQuery(question);
  }

  async function runQuery(queryText: string, useDemo = false) {
    const requestId = queryRequestRef.current + 1;
    queryRequestRef.current = requestId;
    setIsUnderstandingLoading(true);
    setIsAnswerLoading(false);
    setQueryError(null);
    setQueryUnderstanding(null);
    setQueryAnswer(null);
    setDossier(null);
    setIsEvidenceOpen(false);
    setHighlightCitation(null);
    setHighlightEvidenceRxcui(null);

    if (useDemo) {
      setQuestion(DEMO_QUERY);
      window.setTimeout(() => {
        if (queryRequestRef.current !== requestId) {
          return;
        }
        setQueryUnderstanding(demoQueryAnswer.understanding);
        setQueryAnswer(demoQueryAnswer);
        setDossier(demoQueryAnswer.understanding.primary_dossier ?? null);
        setIsUnderstandingLoading(false);
        setIsAnswerLoading(false);
      }, 250);
      return;
    }

    try {
      const understanding = await requestJsonWithRetry<QueryUnderstandingResponse>(
        "/api/query-understanding",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            query: queryText,
          }),
        },
        {
          userMessage:
            "The app could not reliably understand the question after several retries.",
        }
      );

      if (queryRequestRef.current !== requestId) {
        return;
      }
      setQueryUnderstanding(understanding);
      if (understanding.primary_dossier) {
        setDossier(understanding.primary_dossier);
        setIsEvidenceOpen(false);
        setHighlightCitation(null);
        setHighlightEvidenceRxcui(null);
      } else {
        setIsUnderstandingLoading(false);
        setIsAnswerLoading(false);
        return;
      }

      setIsUnderstandingLoading(false);
      setIsAnswerLoading(true);

      const queryAnswerResponse =
        await requestJsonWithRetry<QueryAnswerResponse>(
          "/api/query-answer",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              query: question,
            }),
          },
          {
            userMessage:
              "The app could not reliably generate a response after several retries.",
          }
        );

      if (queryRequestRef.current !== requestId) {
        return;
      }

      setQueryAnswer(queryAnswerResponse);
      setQueryUnderstanding(queryAnswerResponse.understanding);
      if (queryAnswerResponse.understanding.primary_dossier) {
        setDossier(queryAnswerResponse.understanding.primary_dossier);
      } else {
        setDossier(null);
        setIsEvidenceOpen(false);
        setHighlightCitation(null);
        setHighlightEvidenceRxcui(null);
      }
    } catch (err) {
      if (queryRequestRef.current !== requestId) {
        return;
      }
      setQueryError(
        err instanceof Error ? err.message : "Failed to understand query"
      );
    } finally {
      if (queryRequestRef.current === requestId) {
        setIsUnderstandingLoading(false);
        setIsAnswerLoading(false);
      }
    }
  }

  useEffect(() => {
    if (didAutoRunRef.current) {
      return;
    }
    if (autoDemo) {
      // /demo: run the local fixture once on mount, no live API call.
      didAutoRunRef.current = true;
      void runQuery(DEMO_QUERY, true);
      return;
    }
    const initial = searchParams.get("q")?.trim();
    if (!initial) {
      return;
    }
    // Deep link from /compare's "run this question live" link: prefill and run
    // the real pipeline once on mount.
    didAutoRunRef.current = true;
    void runQuery(initial);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, autoDemo]);

  return (
    <div>
      <div className="grid gap-6 md:grid-cols-[clamp(7.5rem,14vw,10rem)_minmax(0,1fr)]">
        <AskPageNavigation
          activeId={activeNavSection}
          onActivate={activateNavSection}
          sections={navigationSections}
        />
        <div className="flex min-w-0 flex-col gap-6">
        <QueryUnderstandingPanel
          answerResponse={queryAnswer}
          askRef={askQuestionRef}
          error={queryError}
          generatedResponseRef={generatedResponseRef}
          isAnswerLoading={isAnswerLoading}
          isUnderstandingLoading={isUnderstandingLoading}
          onQuestionChange={setQuestion}
          onSubmit={handleQuestionSubmit}
          question={question}
          result={queryUnderstanding}
          onAnswerCitationClick={handleAnswerCitationClick}
          onCoverageTargetClick={handleCoverageTargetClick}
        />

        {dossier && queryAnswer && !isAnswerLoading && !isUnderstandingLoading ? (
          <EvidenceReveal
            contentRef={supportingEvidenceContentRef}
            evidenceRef={supportingEvidenceRef}
            isOpen={isEvidenceOpen}
            onOpenChange={setIsEvidenceOpen}
          >
            {queryAnswer.question_evidence_map?.nodes.length ? (
              <div ref={evidenceMapRef} className="scroll-mt-6">
                <EvidenceMapD3
                  map={queryAnswer.question_evidence_map}
                  sourceProfilesBySourceId={evidenceMapSourceProfilesById}
                  onCitationClick={handleAnswerCitationClick}
                  onRxcuiClick={handleCoverageTargetClick}
                />
              </div>
            ) : null}
            <SupportingEvidence
              dossier={dossier}
              drugLabelsNavRef={drugLabelsNavRef}
              drugNetworkNavRef={drugNetworkNavRef}
              evidenceNavRef={supportingEvidencePanelRef}
              highlightCitation={highlightCitation}
              highlightRxcui={highlightEvidenceRxcui}
              questionRxNormNetwork={queryAnswer.question_rxnorm_network}
              secondaryEvidence={queryAnswer.secondary_evidence ?? []}
              onCitationHandled={() => setHighlightCitation(null)}
              onRxcuiHandled={() => setHighlightEvidenceRxcui(null)}
            />
          </EvidenceReveal>
        ) : null}
        </div>
      </div>
    </div>
  );
}

export function DrugDossierExperience() {
  const searchParams = useSearchParams();
  const initialDrug = searchParams.get("drug")?.trim() || "aspirin";
  const shouldAutoSearch = searchParams.get("auto") === "1";
  const [drug, setDrug] = useState(initialDrug);
  const [openfdaLimit, setOpenfdaLimit] = useState(5);
  const [dossier, setDossier] = useState<DrugDossier | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const didAutoSearchRef = useRef(false);

  const buildDossier = useCallback(async (searchDrug = drug) => {
    const trimmedDrug = searchDrug.trim();
    if (!trimmedDrug) {
      return;
    }
    setIsLoading(true);
    setError(null);

    try {
      const payload = await requestJsonWithRetry<DrugDossier>(
        "/api/dossier",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            drug: trimmedDrug,
            depth: 2,
            max_edges: 400,
            openfda_limit: openfdaLimit,
            include_openfda: true,
          }),
        },
        {
          userMessage:
            "The app could not reliably load the drug dossier after several retries.",
        }
      );

      setDossier(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to build dossier");
    } finally {
      setIsLoading(false);
    }
  }, [drug, openfdaLimit]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await buildDossier();
  }

  useEffect(() => {
    if (!shouldAutoSearch || didAutoSearchRef.current || !initialDrug) {
      return;
    }
    didAutoSearchRef.current = true;
    setDrug(initialDrug);
    void buildDossier(initialDrug);
  }, [buildDossier, initialDrug, shouldAutoSearch]);

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
                max={frontendLimits.maxLabelSearchLimit}
                type="number"
                value={openfdaLimit}
                onChange={(event) =>
                  setOpenfdaLimit(
                    Math.max(
                      1,
                      Math.min(
                        Number(event.target.value),
                        frontendLimits.maxLabelSearchLimit
                      )
                    )
                  )
                }
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

function EvidenceReveal({
  children,
  contentRef,
  evidenceRef,
  isOpen,
  onOpenChange,
}: {
  children: ReactNode;
  contentRef: RefObject<HTMLDivElement | null>;
  evidenceRef: RefObject<HTMLDivElement | null>;
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
}) {
  return (
    <div ref={evidenceRef} className="scroll-mt-6">
      <div className="relative flex items-center py-4">
        <div className="flex-1 border-t border-[#D7C8F4]" />
        <Button
          type="button"
          className="mx-4 rounded-full px-5"
          onClick={() => onOpenChange(!isOpen)}
        >
          {isOpen ? "Collapse evidence" : "Explore evidence"}
          {isOpen ? (
            <ChevronDown className="size-4" />
          ) : (
            <ChevronRight className="size-4" />
          )}
        </Button>
        <div className="flex-1 border-t border-[#D7C8F4]" />
      </div>
      {isOpen ? (
        <div ref={contentRef} className="space-y-6 scroll-mt-6">
          {children}
        </div>
      ) : null}
    </div>
  );
}
