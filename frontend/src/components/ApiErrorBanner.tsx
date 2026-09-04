import { AlertTriangle } from "lucide-react";

export default function ApiErrorBanner({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-accent-300 bg-accent-50 px-4 py-3 text-sm text-accent-700">
      <AlertTriangle size={16} strokeWidth={2.25} />
      <span>{message}</span>
    </div>
  );
}
