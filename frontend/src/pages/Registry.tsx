import { useEffect, useState } from "react";
import { IdCard } from "lucide-react";
import Topbar from "../components/Topbar";
import Badge from "../components/Badge";
import EmptyState from "../components/EmptyState";
import ApiErrorBanner from "../components/ApiErrorBanner";
import { api, ApiError, GoldenRecord } from "../lib/api";

const CLASSIFICATION_TONE: Record<string, "success" | "warning"> = {
  L1_unique_complete: "success",
  L2_unique_incomplete: "warning",
};

export default function Registry() {
  const [records, setRecords] = useState<GoldenRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<GoldenRecord[]>("/api/registry/golden-records")
      .then(setRecords)
      .catch((e: ApiError) => setError(e.message));
  }, []);

  return (
    <div>
      <Topbar title="Golden Registry" description="Confirmed, resolved citizen/household identity records." />
      <div className="space-y-6 p-8">
        {error && <ApiErrorBanner message={error} />}

        {records.length === 0 ? (
          <EmptyState
            icon={IdCard}
            title="No golden records yet"
            description="Golden records appear here once source data has been ingested and matched with high confidence."
          />
        ) : (
          <div className="card overflow-hidden">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-zinc-200 bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="px-5 py-3 font-medium">Name</th>
                  <th className="px-5 py-3 font-medium">Sources</th>
                  <th className="px-5 py-3 font-medium">Classification</th>
                  <th className="px-5 py-3 font-medium">Last updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {records.map((r) => (
                  <tr key={r.id}>
                    <td className="px-5 py-3 font-medium text-ink-900">{r.attributes.name ?? r.id.slice(0, 8)}</td>
                    <td className="px-5 py-3 text-zinc-600">{r.contributing_sources.join(", ")}</td>
                    <td className="px-5 py-3">
                      <Badge
                        label={r.classification.split("_").slice(1).join(" ")}
                        tone={CLASSIFICATION_TONE[r.classification] ?? "neutral"}
                      />
                    </td>
                    <td className="px-5 py-3 text-zinc-600">{new Date(r.updated_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
