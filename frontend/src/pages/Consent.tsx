import { useEffect, useState } from "react";
import { ScrollText, Plus } from "lucide-react";
import Topbar from "../components/Topbar";
import Badge from "../components/Badge";
import EmptyState from "../components/EmptyState";
import ApiErrorBanner from "../components/ApiErrorBanner";
import { api, ApiError, ConsentRecord } from "../lib/api";

interface Purpose {
  id: string;
  code: string;
  name: string;
  description: string;
  data_categories: string;
}

const STATUS_TONE = { granted: "success", revoked: "critical", expired: "neutral" } as const;

export default function Consent() {
  const [purposes, setPurposes] = useState<Purpose[]>([]);
  const [consents, setConsents] = useState<ConsentRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ code: "", name: "", description: "", data_categories: "" });

  const load = () => {
    api.get<Purpose[]>("/api/consent/purposes").then(setPurposes).catch((e: ApiError) => setError(e.message));
    api.get<ConsentRecord[]>("/api/consent/consents").then(setConsents).catch((e: ApiError) => setError(e.message));
  };

  useEffect(load, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.post("/api/consent/purposes", {
        ...form,
        data_categories: form.data_categories.split(",").map((s) => s.trim()).filter(Boolean),
      });
      setShowForm(false);
      setForm({ code: "", name: "", description: "", data_categories: "" });
      load();
    } catch (err) {
      setError((err as ApiError).message);
    }
  }

  return (
    <div>
      <Topbar
        title="Consent Management"
        description="DPDP-aligned purposes and consent records governing every data-sharing action."
        action={
          <button className="btn-accent" onClick={() => setShowForm((s) => !s)}>
            <Plus size={16} /> New purpose
          </button>
        }
      />
      <div className="space-y-6 p-8">
        {error && <ApiErrorBanner message={error} />}

        {showForm && (
          <form onSubmit={handleCreate} className="card space-y-4 p-5">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-medium text-zinc-600">Purpose code</label>
                <input
                  required
                  className="input"
                  placeholder="ration-to-registry-match"
                  value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value })}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-zinc-600">Name</label>
                <input
                  required
                  className="input"
                  placeholder="Ration DB to Registry Matching"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1 block text-xs font-medium text-zinc-600">Description (notice text)</label>
                <textarea
                  required
                  className="input"
                  rows={2}
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                />
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1 block text-xs font-medium text-zinc-600">Data categories (comma-separated)</label>
                <input
                  required
                  className="input"
                  placeholder="name, address, ration_id"
                  value={form.data_categories}
                  onChange={(e) => setForm({ ...form, data_categories: e.target.value })}
                />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" className="btn-ghost" onClick={() => setShowForm(false)}>
                Cancel
              </button>
              <button type="submit" className="btn-primary">
                Register purpose
              </button>
            </div>
          </form>
        )}

        <div className="card p-5">
          <h2 className="mb-3 text-sm font-semibold text-ink-900">Registered purposes</h2>
          {purposes.length === 0 ? (
            <EmptyState icon={ScrollText} title="No purposes registered" description="Register a purpose before any consent can be recorded against it." />
          ) : (
            <ul className="divide-y divide-zinc-100">
              {purposes.map((p) => (
                <li key={p.id} className="py-3">
                  <p className="text-sm font-medium text-ink-900">
                    {p.name} <span className="ml-2 font-mono text-xs text-zinc-400">{p.code}</span>
                  </p>
                  <p className="text-sm text-zinc-500">{p.description}</p>
                  <p className="mt-1 text-xs text-zinc-400">Data: {p.data_categories}</p>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="card overflow-hidden">
          <div className="border-b border-zinc-200 p-5">
            <h2 className="text-sm font-semibold text-ink-900">Consent records</h2>
          </div>
          {consents.length === 0 ? (
            <div className="p-5 text-sm text-zinc-500">No consent has been recorded yet.</div>
          ) : (
            <table className="w-full text-left text-sm">
              <thead className="border-b border-zinc-200 bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="px-5 py-3 font-medium">Data principal</th>
                  <th className="px-5 py-3 font-medium">Channel</th>
                  <th className="px-5 py-3 font-medium">Granted by</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Granted at</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {consents.map((c) => (
                  <tr key={c.id}>
                    <td className="px-5 py-3 font-medium text-ink-900">{c.data_principal_id}</td>
                    <td className="px-5 py-3 text-zinc-600">{c.collection_channel}</td>
                    <td className="px-5 py-3 text-zinc-600">{c.granted_by}</td>
                    <td className="px-5 py-3">
                      <Badge label={c.status} tone={STATUS_TONE[c.status]} />
                    </td>
                    <td className="px-5 py-3 text-zinc-600">{new Date(c.granted_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
