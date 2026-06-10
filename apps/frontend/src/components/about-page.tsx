import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function AboutPage() {
  return (
    <div className="w-full">
      <Card>
        <CardHeader>
          <CardTitle>About rx-ray</CardTitle>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            A small portfolio prototype for exploring how symbolic medication
            data and LLM-generated summaries can sit side by side.
          </p>
        </CardHeader>
        <CardContent className="space-y-3 text-sm leading-6 text-slate-700">
          <p>
            rx-ray uses public RxNorm terminology and public FDA drug-label text
            to build an inspectable evidence layer for medication questions.
          </p>
          <p>
            The Drug Dossier is the symbolic layer: it resolves medication
            concepts, retrieves local RxNorm relationships, and organizes public
            label records without generating an answer. The Ask a Question flow
            uses that evidence in a neuro-symbolic pipeline: deterministic query
            parsing is revised by an LLM into a structured state, an LLM
            generates a grounded response from the retrieved evidence, and a
            deterministic coverage check shows which extracted details were or
            were not supported by the evidence.
          </p>
          <p>
            The project is educational only. It does not provide medical advice,
            diagnosis, treatment recommendations, or clinical decision support.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
