import { useCallback, useEffect, useState } from "react";
import {
  Database,
  Plug,
  IdCard,
  Wallet,
  ScrollText,
  ShieldCheck,
  RefreshCw,
  ChevronRight,
  Loader2,
  CircleCheck,
  CircleX,
  CircleDashed,
} from "lucide-react";
import Topbar from "../components/Topbar";
import ApiErrorBanner from "../components/ApiErrorBanner";
import { api, ApiError, GatewayHealth, DownstreamHealth } from "../lib/api";

type Status = "ok" | "unreachable" | "n/a";

function StatusDot({ status }: { status: Status }) {
  if (status === "ok") return <CircleCheck size={14} className="text-emerald-500" />;
  if (status === "unreachable") return <CircleX size={14} className="text-red-400" />;
  return <CircleDashed size={14} className="text-zinc-300" />;
}

function NodeCard({
  icon: Icon,
  name,
  subtitle,
  status,
}: {
  icon: typeof Database;
  name: string;
  subtitle?: string;
  status: Status;
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-zinc-200 bg-white px-3.5 py-2.5">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-zinc-100 text-zinc-500">
        <Icon size={15} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-ink-900">{name}</p>
        {subtitle && <p className="truncate text-xs text-zinc-400">{subtitle}</p>}
      </div>
      <StatusDot status={status} />
    </div>
  );
}

function Stage({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex w-56 shrink-0 flex-col gap-2">
      <p className="px-1 text-xs font-semibold uppercase tracking-wide text-zinc-400">{title}</p>
      <div className="flex flex-1 flex-col justify-center gap-2">{children}</div>
    </div>
  );
}

function Arrow() {
  return (
    <div className="flex shrink-0 items-center self-stretch text-zinc-300">
      <ChevronRight size={20} />
    </div>
  );
}

function statusOf(ok: boolean | undefined): Status {
  return ok === undefined ? "n/a" : ok ? "ok" : "unreachable";
}

function downstreamOk(d: DownstreamHealth | Record<string, DownstreamHealth> | undefined): boolean | undefined {
  if (!d) return undefined;
  if ("reachable" in d) return (d as DownstreamHealth).reachable;
  // inji-adapter nests two: treat "connected" as both being reachable
  const values = Object.values(d as Record<string, DownstreamHealth>);
  return values.length > 0 && values.every((v) => v.reachable);
}

export default function SystemMap() {
  const [health, setHealth] = useState<GatewayHealth | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback((showSpinner = false) => {
    if (showSpinner) setLoading(true);
    return api
      .get<GatewayHealth>("/api/health")
      .then((data) => {
        setHealth(data);
        setError(null);
      })
      .catch((e: ApiError) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load(true);
    const interval = setInterval(() => load(false), 10000);
    return () => clearInterval(interval);
  }, [load]);

  const services = health?.services ?? {};
  const svc = (key: string) => statusOf(services[key]?.status === "ok" ? true : services[key] ? false : undefined);
  const dpg = (key: string) => statusOf(downstreamOk(services[key]?.downstream));

  return (
    <div>
      <Topbar
        title="System Map"
        description="How a source record becomes a golden identity, an eligibility decision, and — where connected — a real action in a Digital Public Good. Live status, refreshed every 10s."
        action={
          <button className="btn-ghost" onClick={() => load(true)} disabled={loading}>
            {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            Refresh
          </button>
        }
      />
      <div className="space-y-8 p-8">
        {error && <ApiErrorBanner message={error} />}

        <div className="card overflow-x-auto p-6">
          <div className="flex min-w-[1100px] items-stretch gap-3">
            <Stage title="State &amp; Dept Sources">
              <NodeCard icon={Database} name="Ration / PDS" subtitle="illustrative source" status="n/a" />
              <NodeCard icon={Database} name="Land Records" subtitle="illustrative source" status="n/a" />
              <NodeCard icon={Database} name="Income &amp; Asset" subtitle="illustrative source" status="n/a" />
            </Stage>

            <Arrow />

            <Stage title="Building the Registry">
              <NodeCard icon={Plug} name="Connector Config" subtitle="onboarding &amp; ingestion" status={svc("connectors")} />
              <NodeCard icon={IdCard} name="Registry Intelligence" subtitle="matching · golden + doubt" status={svc("registry")} />
            </Stage>

            <Arrow />

            <Stage title="Delivery of Benefits">
              <NodeCard icon={Wallet} name="Delivery Intelligence" subtitle="eligibility &amp; exclusion" status={svc("delivery")} />
            </Stage>

            <Arrow />

            <Stage title="DPG Adapters">
              <NodeCard icon={Database} name="Sunbird RC" subtitle="via sunbird-adapter" status={dpg("sunbird")} />
              <NodeCard icon={ShieldCheck} name="DIGIT" subtitle="via digit-adapter (digit-mock)" status={dpg("digit")} />
              <NodeCard icon={ShieldCheck} name="Inji Certify + Verify" subtitle="via inji-adapter" status={dpg("inji")} />
              <NodeCard icon={RefreshCw} name="OpenG2P" subtitle="via openg2p-sync" status={dpg("openg2p-sync")} />
            </Stage>
          </div>

          <div className="mt-5 flex items-center gap-2 border-t border-zinc-100 pt-4">
            <ScrollText size={15} className="text-zinc-400" />
            <p className="text-xs text-zinc-500">
              <span className="font-medium text-zinc-700">Consent Management</span> underpins every arrow above — no
              record moves between a source, the registry, or delivery without a recorded purpose and consent status.
            </p>
            <span className="ml-auto">
              <StatusDot status={svc("consent")} />
            </span>
          </div>
        </div>

        <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs text-zinc-500">
          <span className="flex items-center gap-1.5">
            <CircleCheck size={13} className="text-emerald-500" /> Reachable
          </span>
          <span className="flex items-center gap-1.5">
            <CircleX size={13} className="text-red-400" /> Unreachable — expected until that DPG is deployed and joined
            to the shared network (see <code>deploy/README.md</code>)
          </span>
          <span className="flex items-center gap-1.5">
            <CircleDashed size={13} className="text-zinc-300" /> Not applicable (illustrative source, or status unknown)
          </span>
        </div>
      </div>
    </div>
  );
}
