import { useEffect, useState } from "react";
import { Plug, Plus, PlayCircle } from "lucide-react";
import Topbar from "../components/Topbar";
import Badge from "../components/Badge";
import EmptyState from "../components/EmptyState";
import ApiErrorBanner from "../components/ApiErrorBanner";
import { api, ApiError, Connector } from "../lib/api";

const STATUS_TONE = { active: "success", paused: "warning", draft: "neutral" } as const;

export default function Connectors() {
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: "",
    department: "",
    source_type: "database",
    refresh_mode: "one_time_bulk",
    consent_purpose_code: "",
  });

  const load = () =>
    api
      .get<Connector[]>("/api/connectors/connectors")
      .then(setConnectors)
      .catch((e: ApiError) => setError(e.message));

  useEffect(() => {
    load();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.post("/api/connectors/connectors", {
        ...form,
        connection_config: { note: "configured via console — connection secrets set server-side" },
        schema_mapping: {},
      });
      setShowForm(false);
      setForm({ name: "", department: "", source_type: "database", refresh_mode: "one_time_bulk", consent_purpose_code: "" });
      load();
    } catch (err) {
      setError((err as ApiError).message);
    }
  }

  async function triggerRun(id: string) {
    try {
      await api.post(`/api/connectors/connectors/${id}/trigger-run?triggered_by=console-operator`);
      load();
    } catch (err) {
      setError((err as ApiError).message);
    }
  }

  return (
    <div>
      <Topbar
        title="Connectors"
        description="Register a source database, API, or file — no bespoke integration code."
        action={
          <button className="btn-accent" onClick={() => setShowForm((s) => !s)}>
            <Plus size={16} /> New connector
          </button>
        }
      />
      <div className="space-y-6 p-8">
        {error && <ApiErrorBanner message={error} />}

        {showForm && (
          <form onSubmit={handleCreate} className="card space-y-4 p-5">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-medium text-zinc-600">Name</label>
                <input
                  required
                  className="input"
                  placeholder="Delhi Food & Civil Supply — Ration DB"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-zinc-600">Department</label>
                <input
                  required
                  className="input"
                  placeholder="Food & Civil Supply"
                  value={form.department}
                  onChange={(e) => setForm({ ...form, department: e.target.value })}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-zinc-600">Source type</label>
                <select
                  className="input"
                  value={form.source_type}
                  onChange={(e) => setForm({ ...form, source_type: e.target.value })}
                >
                  <option value="database">Database</option>
                  <option value="api">API</option>
                  <option value="flat_file">Flat file</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-zinc-600">Refresh mode</label>
                <select
                  className="input"
                  value={form.refresh_mode}
                  onChange={(e) => setForm({ ...form, refresh_mode: e.target.value })}
                >
                  <option value="one_time_bulk">One-time bulk load</option>
                  <option value="scheduled_batch">Scheduled batch</option>
                  <option value="event_driven">Event-driven</option>
                </select>
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1 block text-xs font-medium text-zinc-600">Consent purpose code</label>
                <input
                  required
                  className="input"
                  placeholder="ration-to-registry-match"
                  value={form.consent_purpose_code}
                  onChange={(e) => setForm({ ...form, consent_purpose_code: e.target.value })}
                />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" className="btn-ghost" onClick={() => setShowForm(false)}>
                Cancel
              </button>
              <button type="submit" className="btn-primary">
                Register connector
              </button>
            </div>
          </form>
        )}

        {connectors.length === 0 ? (
          <EmptyState
            icon={Plug}
            title="No connectors registered"
            description="Register your first source database, API, or file to start onboarding records into the registry."
            action={
              <button className="btn-accent" onClick={() => setShowForm(true)}>
                <Plus size={16} /> New connector
              </button>
            }
          />
        ) : (
          <div className="card overflow-hidden">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-zinc-200 bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="px-5 py-3 font-medium">Name</th>
                  <th className="px-5 py-3 font-medium">Department</th>
                  <th className="px-5 py-3 font-medium">Type</th>
                  <th className="px-5 py-3 font-medium">Refresh</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {connectors.map((c) => (
                  <tr key={c.id}>
                    <td className="px-5 py-3 font-medium text-ink-900">{c.name}</td>
                    <td className="px-5 py-3 text-zinc-600">{c.department}</td>
                    <td className="px-5 py-3 text-zinc-600">{c.source_type}</td>
                    <td className="px-5 py-3 text-zinc-600">{c.refresh_mode.replace(/_/g, " ")}</td>
                    <td className="px-5 py-3">
                      <Badge label={c.status} tone={STATUS_TONE[c.status]} />
                    </td>
                    <td className="px-5 py-3 text-right">
                      <button className="btn-ghost" onClick={() => triggerRun(c.id)}>
                        <PlayCircle size={14} /> Run
                      </button>
                    </td>
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
