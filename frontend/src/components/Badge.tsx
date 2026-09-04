import { CheckCircle2, Circle, XCircle, AlertTriangle, LucideIcon } from "lucide-react";

type Tone = "neutral" | "success" | "warning" | "critical" | "info";

const TONE_STYLES: Record<Tone, { classes: string; icon: LucideIcon }> = {
  neutral: { classes: "bg-zinc-100 text-zinc-700", icon: Circle },
  success: { classes: "bg-emerald-50 text-emerald-700", icon: CheckCircle2 },
  warning: { classes: "bg-accent-100 text-accent-700", icon: AlertTriangle },
  critical: { classes: "bg-red-50 text-red-700", icon: XCircle },
  info: { classes: "bg-zinc-800 text-zinc-100", icon: Circle },
};

interface BadgeProps {
  label: string;
  tone?: Tone;
}

export default function Badge({ label, tone = "neutral" }: BadgeProps) {
  const { classes, icon: Icon } = TONE_STYLES[tone];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${classes}`}>
      <Icon size={12} strokeWidth={2.5} />
      {label}
    </span>
  );
}
