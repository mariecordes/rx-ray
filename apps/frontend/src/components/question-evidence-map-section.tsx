"use client";

import { Info } from "lucide-react";

import { EvidenceMapD3 } from "@/components/question-evidence-map-d3";
import {
  EvidenceMapNavigationTarget,
  EvidenceMapReactFlow,
} from "@/components/question-evidence-map-react-flow";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EvidenceCitation, QuestionEvidenceMap } from "@/lib/types";

type EvidenceMapSectionProps = {
  map: QuestionEvidenceMap;
  onCitationClick: (citation: EvidenceCitation) => void;
  onRxcuiClick: (target: EvidenceMapNavigationTarget) => void;
};

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

export function EvidenceMapSection({
  map,
  onCitationClick,
  onRxcuiClick,
}: EvidenceMapSectionProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <CardTitle>Evidence Map</CardTitle>
          <InfoTooltip text="This map connects extracted question concepts, RxNorm medication resolution, public FDA label evidence, and RxNorm terminology context. Label-text edges show what was retrieved or mentioned in labels; they are not clinical interaction claims." />
        </div>
        <p className="mt-1 text-sm leading-6 text-slate-500">
          Two visual experiments for the same question-level evidence graph. Use
          these side by side to compare whether React Flow or a Drug
          Network-style D3 view communicates the evidence structure better.
        </p>
      </CardHeader>
      <CardContent className="space-y-6">
        <section>
          <div className="mb-2 text-xs font-medium uppercase text-slate-500">
            Alternative A · D3 force evidence map
          </div>
          <EvidenceMapD3
            map={map}
            onCitationClick={onCitationClick}
            onRxcuiClick={onRxcuiClick}
          />
        </section>
        <section>
          <div className="mb-2 text-xs font-medium uppercase text-slate-500">
            Alternative B · React Flow evidence map
          </div>
          <EvidenceMapReactFlow
            map={map}
            onCitationClick={onCitationClick}
            onRxcuiClick={onRxcuiClick}
          />
        </section>
      </CardContent>
    </Card>
  );
}
