// "Built with" page (rulebook §8): every model, API, dataset and library with its licence, from GET /built-with,
// plus the backend's provider and dataset status from GET /health.
import { useEffect, useState } from "react";
import { ExternalLink } from "lucide-react";
import { api, errorMessage } from "../lib/api";
import { titleCase } from "../lib/format";
import type { BuiltWithItem, Health } from "../types/api";

const KIND_ORDER = ["model", "api", "dataset", "library"];

export default function BuiltWith() {
  const [items, setItems] = useState<BuiltWithItem[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.builtWith().then(setItems).catch((err) => setError(errorMessage(err)));
    api.health().then(setHealth).catch(() => undefined);
  }, []);

  const kinds = [...new Set(items.map((i) => i.kind))].sort(
    (a, b) => (KIND_ORDER.indexOf(a) + 1 || 99) - (KIND_ORDER.indexOf(b) + 1 || 99),
  );

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <h1 className="text-2xl font-bold tracking-tight">Built with</h1>
      <p className="mt-1 text-slate-600">
        Every model, API, dataset and library CareerLens uses, with its licence. Role profiles derive from the ESCO
        and O*NET taxonomies; job listings are public postings with source URLs or labelled synthetic; the demo
        persona is fictional.
      </p>

      {health && (
        <div className="card mt-5 flex flex-wrap gap-x-6 gap-y-2 p-4 text-sm">
          <span>
            LLM provider: <strong>{health.llm_provider}</strong>
          </span>
          <span>
            Embeddings: <strong>{health.embed_provider}</strong>
          </span>
          <span>
            Datasets: {health.data.roles ?? "–"} roles · {health.data.jobs ?? "–"} jobs · {health.data.resources ?? "–"} skills with resources
          </span>
        </div>
      )}

      {error && <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}

      {kinds.map((kind) => (
        <section key={kind} className="mt-6">
          <h2 className="label">{titleCase(kind)}s</h2>
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <tbody className="divide-y divide-slate-100">
                {items
                  .filter((i) => i.kind === kind)
                  .map((item) => (
                    <tr key={item.name}>
                      <td className="px-4 py-2 font-medium text-slate-800">{item.name}</td>
                      <td className="px-4 py-2 text-slate-500">{item.licence}</td>
                      <td className="px-4 py-2 text-right">
                        {item.url && (
                          <a href={item.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-brand-600 hover:underline">
                            link <ExternalLink className="h-3 w-3" aria-hidden />
                          </a>
                        )}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}

      <div className="card mt-8 p-4 text-sm text-slate-700">
        <p className="font-semibold">Fairness and privacy</p>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-600">
          <li>Matching uses skills only: no name, gender, age, university or photo reaches the model.</li>
          <li>Email, phone, address, date of birth and ID numbers are stripped from the CV before any AI call.</li>
          <li>Video is processed in the browser and discarded frame by frame; only geometric metrics are stored.</li>
          <li>No accounts, no database: "Delete my data" clears the server session and this browser.</li>
        </ul>
      </div>
    </div>
  );
}
