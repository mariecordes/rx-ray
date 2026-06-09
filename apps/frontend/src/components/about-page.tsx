import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function AboutPage() {
  return (
    <div className="mx-auto w-full max-w-4xl">
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
            The project is educational only. It does not provide medical advice,
            diagnosis, treatment recommendations, or clinical decision support.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
