import { useEffect, useState } from "react";
import { IdCard, ShieldQuestion, Plug, ScrollText, Activity } from "lucide-react";
import Topbar from "../components/Topbar";
import StatTile from "../components/StatTile";
import Badge from "../components/Badge";
import ApiErrorBanner from "../components/ApiErrorBanner";
import { api, ApiError, Connector, DoubtRecord, GoldenRecord, ConsentRecord, GatewayHealth } from "../lib/api";

export default function Dashboard() {
  const [error, setError] = useState<string | null>(null);
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [golden, setGolden] = useState<GoldenRecord[]>([]);
  const [doubt, setDoubt] = useState<DoubtRecord[]>([]);
  const [consents, setConsents] = useState<ConsentRecord[]>([]);
  const [health, setHealth] = useState<GatewayHealth | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<Connector[]>("/api/connectors/connectors").catch(() => []),
      api.get<GoldenRecord[]>("/api/registry/golden-records").catch(() => []),
      api.get<DoubtRecord[]>("/api/registry/doubt-records").catch(() => []),
      api.get<ConsentRecord[]>("/api/consent/consents").catch(() => []),
      api.get<GatewayHealth>("/health").catch(() => null),
    ])
      .then(([c, g, d, cons, h]) => {
        setConnectors(c);
        setGolden(g);
        setDoubt(d);
        setConsents(cons);
        setHealth(h);
      })
      .catch((e: ApiError) => setError(e.message));
  }, []);

  const openDoubts = doubt.filter((d) => d.status === "open").length;
  const activeConnectors = connectors.filter((c) => c.status === "active").length;
  const grantedConsents = consents.filter((c) => c.status === "granted").length;

  return (
    <div>
      <Topbar
        title="Platform overview"
        description="Live status of the registry, delivery, and consent layers for this deployment."
      />
      <div className="space-y-6 p-8">
        {error && <ApiErrorBanner message={error} />}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile label="Golden records" value={golden.length} icon={IdCard} />
          <StatTile
            label="Open doubt records"
            value={openDoubts}
            icon={ShieldQuestion}
            emphasis={openDoubts > 0}
            hint="Awaiting human review"
          />
          <StatTile label="Active connectors" value={activeConnectors} icon={Plug} hint={`${connectors.length} configured`} />
          <StatTile label="Consents granted" value={grantedConsents} icon={ScrollText} />
        </div>

        <div className="card p-5">
          <div className="mb-4 flex items-center gap-2">
            <Activity size={16} className="text-zinc-500" />
            <h2 className="text-sm font-semibold text-ink-900">Service health</h2>
          </div>
          {!health ? (
            <p className="text-sm text-zinc-500">Gateway unreachable — start the platform with `docker compose up`.</p>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              {Object.entries(health.services).map(([name, status]) => (
                <div key={name} className="flex items-center justify-between rounded-lg border border-zinc-200 px-3 py-2">
                  <span className="text-xs font-medium text-zinc-600">{name}</span>
                  <Badge label={status.status} tone={status.status === "ok" ? "success" : "critical"} />
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="card p-5">
            <h2 className="mb-3 text-sm font-semibold text-ink-900">Recent doubt records</h2>
            {doubt.length === 0 ? (
              <p className="text-sm text-zinc-500">No doubt records yet.</p>
            ) : (
              <ul className="divide-y divide-zinc-100">
                {doubt.slice(0, 5).map((d) => (
                  <li key={d.id} className="flex items-center justify-between py-2.5 text-sm">
                    <span className="text-zinc-700">{d.attributes.name ?? d.id.slice(0, 8)}</span>
                    <Badge label={d.classification.split("_").slice(1).join(" ")} tone="warning" />
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="card p-5">
            <h2 className="mb-3 text-sm font-semibold text-ink-900">Registered connectors</h2>
            {connectors.length === 0 ? (
              <p className="text-sm text-zinc-500">No source connectors registered yet.</p>
            ) : (
              <ul className="divide-y divide-zinc-100">
                {connectors.slice(0, 5).map((c) => (
                  <li key={c.id} className="flex items-center justify-between py-2.5 text-sm">
                    <span className="text-zinc-700">{c.name}</span>
                    <Badge
                      label={c.status}
                      tone={c.status === "active" ? "success" : c.status === "paused" ? "warning" : "neutral"}
                    />
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
