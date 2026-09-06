import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ScrollText,
  Plug,
  IdCard,
  Wallet,
  ShieldCheck,
  Database,
  RefreshCw,
  History,
  Loader2,
} from "lucide-react";
import Topbar from "../components/Topbar";
import Badge from "../components/Badge";
import EmptyState from "../components/EmptyState";
import ApiErrorBanner from "../components/ApiErrorBanner";
import { api, ApiError, AuditEvent } from "../lib/api";

const SERVICE_META: Record<AuditEvent["service"], { label: string; icon: typeof ScrollText }> = {
  consent: { label: "Consent", icon: ScrollText },
  connectors: { label: "Connectors", icon: Plug },
  registry: { label: "Registry", icon: IdCard },
  delivery: { label: "Delivery", icon: Wallet },
  digit: { label: "DIGIT", icon: ShieldCheck },
  sunbird: { label: "Sunbird RC", icon: Database },
  "openg2p-sync": { label: "OpenG2P", icon: RefreshCw },
};

const ACTION_TONE: Record<string, "neutral" | "success" | "warning" | "critical" | "info"> = {
  consent_granted: "success",
  consent_revoked: "warning",
  ingestion_run: "neutral",
  golden_record_created: "success",
  doubt_record_flagged: "warning",
  doubt_record_resolved: "success",
  verification_case_opened: "warning",
  digit_routed: "info",
  sunbird_pushed: "info",
  openg2p_sync: "info",
};

const ALL_SERVICES = Object.keys(SERVICE_META) as AuditEvent["service"][];

export default function AuditTrail() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeServices, setActiveServices] = useState<Set<AuditEvent["service"]>>(new Set(ALL_SERVICES));

  const load = useCallback((showSpinner = false) => {
    if (showSpinner) setLoading(true);
    return api
      .get<AuditEvent[]>("/api/audit/timeline")
      .then((data) => {
        setEvents(data);
        setError(null);
      })
      .catch((e: ApiError) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load(true);
    const interval = setInterval(() => load(false), 20000);
    return () => clearInterval(interval);
  }, [load]);

  function toggleService(service: AuditEvent["service"]) {
    setActiveServices((prev) => {
      const next = new Set(prev);
      if (next.has(service)) next.delete(service);
      else next.add(service);
      return next;
    });
  }

  const filtered = useMemo(() => events.filter((e) => activeServices.has(e.service)), [events, activeServices]);

  return (
    <div>
      <Topbar
        title="Audit Trail"
        description="Every consent, ingestion, matching, delivery, and DPG action across the platform, in one chronological trail — the record of who did what, and when."
        action={
          <button className="btn-ghost" onClick={() => load(true)} disabled={loading}>
            {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            Refresh
          </button>
        }
      />
      <div className="space-y-6 p-8">
        {error && <ApiErrorBanner message={error} />}

        <div className="flex flex-wrap gap-2">
          {ALL_SERVICES.map((service) => {
            const { label, icon: Icon } = SERVICE_META[service];
            const active = activeServices.has(service);
            return (
              <button
                key={service}
                onClick={() => toggleService(service)}
                className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                  active
                    ? "border-ink-900 bg-ink-900 text-white"
                    : "border-zinc-200 bg-white text-zinc-500 hover:border-zinc-300"
                }`}
              >
                <Icon size={13} />
                {label}
              </button>
            );
          })}
        </div>

        {filtered.length === 0 ? (
          <EmptyState
            icon={History}
            title="No audit events yet"
            description="Actions across every service — consent grants, ingestion runs, matching decisions, delivery checks, and DPG pushes — will appear here as they happen."
          />
        ) : (
          <div className="card divide-y divide-zinc-100">
            {filtered.map((event, i) => {
              const { label, icon: Icon } = SERVICE_META[event.service];
              const tone = ACTION_TONE[event.action] ?? "neutral";
              return (
                <div key={i} className="flex items-start gap-4 px-5 py-4">
                  <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-zinc-100 text-zinc-500">
                    <Icon size={15} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex flex-wrap items-center gap-2">
                      <Badge label={label} tone={tone} />
                      {event.actor && <span className="text-xs text-zinc-400">by {event.actor}</span>}
                      <span className="text-xs text-zinc-400">
                        {new Date(event.timestamp).toLocaleString()}
                      </span>
                    </div>
                    <p className="text-sm text-zinc-700">{event.summary}</p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
