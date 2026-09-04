import { useEffect, useState } from "react";
import { ShieldQuestion, CheckCircle2 } from "lucide-react";
import Topbar from "../components/Topbar";
import Badge from "../components/Badge";
import EmptyState from "../components/EmptyState";
import ApiErrorBanner from "../components/ApiErrorBanner";
import { api, ApiError, DoubtRecord } from "../lib/api";

export default function DoubtRegistry() {
  const [records, setRecords] = useState<DoubtRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [reviewer, setReviewer] = useState("");

  const load = () =>
    api
      .get<DoubtRecord[]>("/api/registry/doubt-records")
      .then(setRecords)
      .catch((e: ApiError) => setError(e.message));

  useEffect(() => {
    load();
  }, []);

  async function resolve(id: string, targetGoldenId?: string) {
    if (!reviewer.trim()) {
      setError("Enter your reviewer name before resolving a record.");
      return;
    }
    try {
      await api.post(`/api/registry/doubt-records/${id}/resolve`, {
        resolved_by: reviewer,
        action: targetGoldenId ? "merge_into_golden" : "promote_to_new_golden",
        target_golden_record_id: targetGoldenId,
      });
      load();
    } catch (err) {
      setError((err as ApiError).message);
    }
  }

  const openRecords = records.filter((r) => r.status === "open");

  return (
    <div>
      <Topbar
        title="Doubt Registry"
        description="Unresolved identity records. Every resolution here is a human decision — nothing is auto-merged."
      />
      <div className="space-y-6 p-8">
        {error && <ApiErrorBanner message={error} />}

        <div className="card flex items-center gap-3 p-4">
          <label className="text-xs font-medium text-zinc-600">Reviewing as</label>
          <input
            className="input max-w-xs"
            placeholder="reviewer@department.gov"
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
          />
        </div>

        {openRecords.length === 0 ? (
          <EmptyState
            icon={ShieldQuestion}
            title="No open doubt records"
            description="Records land here when a new source can't be matched uniquely or completely — they'll wait for review."
          />
        ) : (
          <div className="space-y-4">
            {openRecords.map((r) => (
              <div key={r.id} className="card p-5">
                <div className="mb-3 flex items-start justify-between">
                  <div>
                    <p className="font-medium text-ink-900">{r.attributes.name ?? r.id.slice(0, 8)}</p>
                    <p className="text-xs text-zinc-500">Sources: {r.contributing_sources.join(", ")}</p>
                  </div>
                  <Badge label={r.classification.split("_").slice(1).join(" ")} tone="warning" />
                </div>

                <div className="mb-4 grid grid-cols-2 gap-2 rounded-lg bg-zinc-50 p-3 text-xs sm:grid-cols-4">
                  {Object.entries(r.attributes).map(([k, v]) => (
                    <div key={k}>
                      <p className="text-zinc-400">{k}</p>
                      <p className="font-medium text-zinc-700">{v}</p>
                    </div>
                  ))}
                </div>

                {r.candidate_matches.length > 0 && (
                  <div className="mb-4">
                    <p className="mb-2 text-xs font-medium text-zinc-500">Candidate matches</p>
                    <ul className="space-y-2">
                      {r.candidate_matches.map((m, i) => (
                        <li key={i} className="flex items-center justify-between rounded-lg border border-zinc-200 px-3 py-2 text-sm">
                          <span className="text-zinc-600">
                            {m.evidence} · score {m.score.toFixed(2)}
                          </span>
                          {m.golden_record_id && (
                            <button className="btn-ghost" onClick={() => resolve(r.id, m.golden_record_id)}>
                              <CheckCircle2 size={14} /> Merge into this record
                            </button>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="flex justify-end">
                  <button className="btn-primary" onClick={() => resolve(r.id)}>
                    Promote as new golden record
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
