import { useEffect, useState } from "react";
import { Wallet } from "lucide-react";
import Topbar from "../components/Topbar";
import Badge from "../components/Badge";
import EmptyState from "../components/EmptyState";
import ApiErrorBanner from "../components/ApiErrorBanner";
import { api, ApiError, SchemeRule } from "../lib/api";

interface VerificationCase {
  id: string;
  reason: string;
  scheme_code: string;
  status: string;
  created_at: string;
}

export default function Delivery() {
  const [schemes, setSchemes] = useState<SchemeRule[]>([]);
  const [cases, setCases] = useState<VerificationCase[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<SchemeRule[]>("/api/delivery/schemes").then(setSchemes).catch((e: ApiError) => setError(e.message));
    api
      .get<VerificationCase[]>("/api/delivery/verification-cases")
      .then(setCases)
      .catch((e: ApiError) => setError(e.message));
  }, []);

  return (
    <div>
      <Topbar
        title="Delivery Rules"
        description="Scheme eligibility and exclusion conditions, and identity-verification cases opened for Doubt Registry citizens."
      />
      <div className="space-y-6 p-8">
        {error && <ApiErrorBanner message={error} />}

        {schemes.length === 0 ? (
          <EmptyState
            icon={Wallet}
            title="No schemes configured"
            description="Register a scheme's eligibility and exclusion conditions via the delivery-intelligence API to see it here."
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {schemes.map((s) => (
              <div key={s.id} className="card p-5">
                <p className="font-medium text-ink-900">{s.name}</p>
                <p className="mb-3 font-mono text-xs text-zinc-400">{s.scheme_code}</p>

                <p className="mb-1 text-xs font-medium uppercase tracking-wide text-zinc-500">Eligibility (all must pass)</p>
                <ul className="mb-3 space-y-1 text-sm text-zinc-700">
                  {s.eligibility_conditions.map((c, i) => (
                    <li key={i}>
                      {c.field} {c.op} {c.value}
                    </li>
                  ))}
                </ul>

                <p className="mb-1 text-xs font-medium uppercase tracking-wide text-zinc-500">Exclusion (any excludes)</p>
                <ul className="space-y-1 text-sm text-zinc-700">
                  {s.exclusion_conditions.map((c, i) => (
                    <li key={i}>
                      {c.field} {c.op} {c.value}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}

        <div className="card overflow-hidden">
          <div className="border-b border-zinc-200 p-5">
            <h2 className="text-sm font-semibold text-ink-900">Verification cases</h2>
            <p className="text-xs text-zinc-500">
              Opened when a Doubt Registry citizen needs field verification before an eligibility decision can be made.
            </p>
          </div>
          {cases.length === 0 ? (
            <div className="p-5 text-sm text-zinc-500">No open verification cases.</div>
          ) : (
            <ul className="divide-y divide-zinc-100">
              {cases.map((c) => (
                <li key={c.id} className="flex items-center justify-between px-5 py-3 text-sm">
                  <div>
                    <p className="font-medium text-ink-900">{c.scheme_code}</p>
                    <p className="text-zinc-500">{c.reason}</p>
                  </div>
                  <Badge label={c.status} tone="warning" />
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
