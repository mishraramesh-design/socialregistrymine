import { Fragment, useEffect, useState } from "react";
import { Plug, Plus, PlayCircle, ChevronDown, ChevronUp } from "lucide-react";
import Topbar from "../components/Topbar";
import Badge from "../components/Badge";
import EmptyState from "../components/EmptyState";
import ApiErrorBanner from "../components/ApiErrorBanner";
import { api, ApiError, Connector, IngestionRun } from "../lib/api";

const STATUS_TONE = { active: "success", paused: "warning", draft: "neutral" } as const;
const RUN_STATUS_TONE = { completed: "success", failed: "critical", running: "warning", queued: "neutral" } as const;

const CANONICAL_FIELDS = [
  { key: "name", label: "Name" },
  { key: "date_of_birth", label: "Date of birth" },
  { key: "address", label: "Address" },
  { key: "aadhaar", label: "Aadhaar" },
  { key: "national_id", label: "National / State ID" },
  { key: "ration_id", label: "Ration ID" },
];

const emptyMapping = Object.fromEntries(CANONICAL_FIELDS.map((f) => [f.key, ""]));

export default function Connectors() {
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [lastRuns, setLastRuns] = useState<Record<string, IngestionRun>>({});
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: "",
    department: "",
    source_type: "flat_file",
    refresh_mode: "one_time_bulk",
    consent_purpose_code: "",
    api_url: "",
  });
  const [mapping, setMapping] = useState<Record<string, string>>(emptyMapping);
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);
  const [pasteText, setPasteText] = useState("");
  const [running, setRunning] = useState(false);

  const load = () =>
    api
      .get<Connector[]>("/api/connectors/connectors")
      .then((cs) => {
        setConnectors(cs);
        cs.forEach((c) =>
          api
            .get<IngestionRun[]>(`/api/connectors/connectors/${c.id}/runs`)
            .then((runs) => runs[0] && setLastRuns((prev) => ({ ...prev, [c.id]: runs[0] })))
            .catch(() => {}),
        );
      })
      .catch((e: ApiError) => setError(e.message));

  useEffect(() => {
    load();
  }, []);

  // Polls while any run is still in flight, so status/counts update without a manual refresh.
  useEffect(() => {
    const hasInFlight = Object.values(lastRuns).some((r) => r.status === "queued" || r.status === "running");
    if (!hasInFlight) return;
    const interval = setInterval(load, 1500);
    return () => clearInterval(interval);
  }, [lastRuns]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const schema_mapping = Object.fromEntries(Object.entries(mapping).filter(([, v]) => v.trim() !== ""));
    if (Object.keys(schema_mapping).length === 0) {
      setError("Map at least one field, or nothing will reach the registry.");
      return;
    }
    if (form.source_type === "api" && !form.api_url.trim()) {
      setError("API connectors need a URL to fetch records from.");
      return;
    }
    try {
      await api.post("/api/connectors/connectors", {
        name: form.name,
        department: form.department,
        source_type: form.source_type,
        refresh_mode: form.refresh_mode,
        consent_purpose_code: form.consent_purpose_code,
        connection_config: form.source_type === "api" ? { url: form.api_url } : {},
        schema_mapping,
      });
      setShowForm(false);
      setForm({ name: "", department: "", source_type: "flat_file", refresh_mode: "one_time_bulk", consent_purpose_code: "", api_url: "" });
      setMapping(emptyMapping);
      load();
    } catch (err) {
      setError((err as ApiError).message);
    }
  }

  async function triggerRun(connector: Connector, records?: Record<string, string>[]) {
    setRunning(true);
    try {
      await api.post(
        `/api/connectors/connectors/${connector.id}/trigger-run?triggered_by=console-operator`,
        records ? { records } : undefined,
      );
      setExpandedRunId(null);
      setPasteText("");
      load();
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setRunning(false);
    }
  }

  function handleRunClick(connector: Connector) {
    if (connector.source_type === "api") {
      triggerRun(connector);
    } else {
      setExpandedRunId(expandedRunId === connector.id ? null : connector.id);
      setPasteText("");
    }
  }

  function submitPastedRecords(connector: Connector) {
    let records: Record<string, string>[];
    try {
      records = JSON.parse(pasteText);
      if (!Array.isArray(records)) throw new Error();
    } catch {
      setError("Paste a JSON array of records, e.g. [{\"ration_holder_name\": \"Anita Devi\", \"dob\": \"1990-01-01\"}]");
      return;
    }
    triggerRun(connector, records);
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
          <form onSubmit={handleCreate} className="card space-y-5 p-5">
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
                  <option value="flat_file">Flat file (paste records to run)</option>
                  <option value="database">Database (paste records to run — no live driver yet)</option>
                  <option value="api">API (fetches live)</option>
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
              {form.source_type === "api" && (
                <div className="sm:col-span-2">
                  <label className="mb-1 block text-xs font-medium text-zinc-600">API URL</label>
                  <input
                    required
                    className="input"
                    placeholder="https://example.gov.in/api/ration-records"
                    value={form.api_url}
                    onChange={(e) => setForm({ ...form, api_url: e.target.value })}
                  />
                  <p className="mt-1 text-xs text-zinc-500">Must return a JSON array of records when run is triggered.</p>
                </div>
              )}
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

            <div>
              <p className="mb-1 text-xs font-medium text-zinc-600">
                Field mapping — what does this source call each canonical field?
              </p>
              <p className="mb-3 text-xs text-zinc-400">Leave blank any field this source doesn't have.</p>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                {CANONICAL_FIELDS.map((f) => (
                  <div key={f.key}>
                    <label className="mb-1 block text-xs text-zinc-500">{f.label}</label>
                    <input
                      className="input"
                      placeholder={f.key}
                      value={mapping[f.key]}
                      onChange={(e) => setMapping({ ...mapping, [f.key]: e.target.value })}
                    />
                  </div>
                ))}
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
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Last run</th>
                  <th className="px-5 py-3 font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {connectors.map((c) => {
                  const run = lastRuns[c.id];
                  return (
                    <Fragment key={c.id}>
                      <tr>
                        <td className="px-5 py-3 font-medium text-ink-900">{c.name}</td>
                        <td className="px-5 py-3 text-zinc-600">{c.department}</td>
                        <td className="px-5 py-3 text-zinc-600">{c.source_type}</td>
                        <td className="px-5 py-3">
                          <Badge label={c.status} tone={STATUS_TONE[c.status]} />
                        </td>
                        <td className="px-5 py-3">
                          {run ? (
                            <div className="flex items-center gap-2">
                              <Badge label={run.status} tone={RUN_STATUS_TONE[run.status]} />
                              {run.status === "completed" && (
                                <span className="text-xs text-zinc-500">
                                  {run.golden_count} golden · {run.doubt_count} doubt
                                  {run.failed_count > 0 && ` · ${run.failed_count} failed`}
                                </span>
                              )}
                              {run.status === "failed" && run.error && (
                                <span className="max-w-xs truncate text-xs text-red-600" title={run.error}>
                                  {run.error}
                                </span>
                              )}
                            </div>
                          ) : (
                            <span className="text-xs text-zinc-400">Never run</span>
                          )}
                        </td>
                        <td className="px-5 py-3 text-right">
                          <button className="btn-ghost" onClick={() => handleRunClick(c)} disabled={running}>
                            <PlayCircle size={14} /> Run
                            {c.source_type !== "api" &&
                              (expandedRunId === c.id ? <ChevronUp size={14} /> : <ChevronDown size={14} />)}
                          </button>
                        </td>
                      </tr>
                      {expandedRunId === c.id && (
                        <tr>
                          <td colSpan={6} className="bg-zinc-50 px-5 py-4">
                            <p className="mb-2 text-xs font-medium text-zinc-600">
                              Paste a JSON array of source-side records — field names should match this
                              connector's mapping ({Object.entries(c.schema_mapping).map(([src, canon]) => `${src}→${canon}`).join(", ")}).
                            </p>
                            <textarea
                              className="input mb-2 font-mono text-xs"
                              rows={5}
                              placeholder='[{"ration_holder_name": "Anita Devi", "dob": "1990-01-01"}]'
                              value={pasteText}
                              onChange={(e) => setPasteText(e.target.value)}
                            />
                            <div className="flex justify-end gap-2">
                              <button className="btn-ghost" onClick={() => setExpandedRunId(null)}>
                                Cancel
                              </button>
                              <button className="btn-primary" onClick={() => submitPastedRecords(c)} disabled={running}>
                                {running ? "Running…" : "Run with these records"}
                              </button>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
