import { LucideIcon } from "lucide-react";

interface StatTileProps {
  label: string;
  value: string | number;
  icon: LucideIcon;
  emphasis?: boolean;
  hint?: string;
}

export default function StatTile({ label, value, icon: Icon, emphasis, hint }: StatTileProps) {
  return (
    <div className={`card p-5 ${emphasis ? "border-accent-300 bg-accent-50/40" : ""}`}>
      <div className="flex items-start justify-between">
        <p className="text-sm font-medium text-zinc-500">{label}</p>
        <div
          className={`flex h-8 w-8 items-center justify-center rounded-md ${
            emphasis ? "bg-accent-400 text-ink-900" : "bg-zinc-100 text-zinc-600"
          }`}
        >
          <Icon size={16} strokeWidth={2.25} />
        </div>
      </div>
      <p className="mt-3 text-3xl font-semibold tracking-tight text-ink-900">{value}</p>
      {hint && <p className="mt-1 text-xs text-zinc-500">{hint}</p>}
    </div>
  );
}
