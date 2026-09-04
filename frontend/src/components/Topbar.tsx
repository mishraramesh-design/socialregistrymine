interface TopbarProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export default function Topbar({ title, description, action }: TopbarProps) {
  return (
    <header className="flex items-center justify-between border-b border-zinc-200 bg-white px-8 py-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink-900">{title}</h1>
        {description && <p className="mt-1 text-sm text-zinc-500">{description}</p>}
      </div>
      {action}
    </header>
  );
}
