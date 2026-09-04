import { useEffect, useState } from "react";
import { RefreshCw, Zap } from "lucide-react";
import Topbar from "../components/Topbar";
import Badge from "../components/Badge";
import EmptyState from "../components/EmptyState";
import ApiErrorBanner from "../components/ApiErrorBanner";
import { api, ApiError, SyncRun } from "../lib/api";

const STATUS_TONE = { succeeded: "success", failed: "critical", running: "warning", queued: "neutral" } as const;

export default function OpenG2PSync() {
  const [runs, setRuns] = useState<SyncRun[]>([]);
  const [schedule, setSchedule] = useState<{ mode: string; cron: string; target: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [triggering, setTriggering] = useState(false);

  const load = () => {
    api.get<SyncRun[]>("/api/openg2p-sync/sync/runs").then(setRuns).catch((e: ApiError) => setError(e.message));
    api
      .get<{ mode: string; cron: string; target: string }>("/api/openg2p-sync/sync/schedule")
      .then(setSchedule)
      .catch((e: ApiError) => setError(e.message));
  };

  useEffect(load, []);

  async function triggerSync() {
    setTriggering(true);
    try {
      await api.post("/api/openg2p-sync/sync/trigger", { beneficiaries: [], triggered_by: "console-operator" });
      load();
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setTriggering(false);
    }
  }

  return (
    <div>
      <Topbar
        title="OpenG2P Sync"
        description="Manually-triggered or scheduled push of confirmed-eligible beneficiaries into OpenG2P."
        action={
          <button className="btn-accent" onClick={triggerSync} disabled={triggering}>
            <Zap size={16} /> {triggering ? "Syncing…" : "Trigger sync now"}
          </button>
        }
      />
      <div className="space-y-6 p-8">
        {error && <ApiErrorBanner message={error} />}

        {schedule && (
          <div className="card grid grid-cols-1 gap-4 p-5 sm:grid-cols-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Mode</p>
              <p className="mt-1 text-sm font-medium text-ink-900">{schedule.mode}</p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Schedule (cron)</p>
              <p className="mt-1 font-mono text-sm text-ink-900">{schedule.cron}</p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Target</p>
              <p className="mt-1 text-sm text-ink-900">{schedule.target}</p>
            </div>
          </div>
        )}

        {runs.length === 0 ? (
          <EmptyState icon={RefreshCw} title="No sync runs yet" description="Trigger a sync to push confirmed-eligible beneficiaries to OpenG2P." />
        ) : (
          <div className="card overflow-hidden">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-zinc-200 bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="px-5 py-3 font-medium">Triggered by</th>
                  <th className="px-5 py-3 font-medium">Submitted</th>
                  <th className="px-5 py-3 font-medium">Synced</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Started</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {runs.map((r) => (
                  <tr key={r.id}>
                    <td className="px-5 py-3 text-zinc-700">{r.triggered_by}</td>
                    <td className="px-5 py-3 text-zinc-600">{r.beneficiaries_submitted}</td>
                    <td className="px-5 py-3 text-zinc-600">{r.beneficiaries_synced}</td>
                    <td className="px-5 py-3">
                      <Badge label={r.status} tone={STATUS_TONE[r.status]} />
                    </td>
                    <td className="px-5 py-3 text-zinc-600">{new Date(r.started_at).toLocaleString()}</td>
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
