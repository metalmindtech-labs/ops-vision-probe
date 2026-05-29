export default function CategoryBreakdown({ categories }) {
    const total = categories.reduce((a, c) => a + c.count, 0) || 1;
    return (
        <aside className="border border-zinc-800 bg-zinc-900/30 rounded-sm terminal-shadow">
            <div className="px-4 py-3 border-b border-zinc-800 flex items-center justify-between">
                <h3 className="font-mono text-xs uppercase tracking-[0.25em] text-zinc-300">
                    Category Distribution
                </h3>
                <span className="font-mono text-[10px] text-zinc-600">n={total}</span>
            </div>
            <div className="p-4 space-y-3">
                {categories.length === 0 && (
                    <p className="font-mono text-[10px] uppercase tracking-wider text-zinc-600">
                        no data
                    </p>
                )}
                {categories.map((c) => {
                    const pct = Math.round((c.count / total) * 100);
                    return (
                        <div key={c.name} className="space-y-1">
                            <div className="flex items-center justify-between font-mono text-[11px]">
                                <span className="text-zinc-300 truncate pr-2">
                                    {c.name}
                                </span>
                                <span className="text-zinc-500">
                                    {c.count}{" "}
                                    <span className="text-zinc-600">· {pct}%</span>
                                </span>
                            </div>
                            <div className="h-1 bg-zinc-800 rounded-sm overflow-hidden">
                                <div
                                    className="h-full bg-lime-400/80"
                                    style={{ width: `${pct}%` }}
                                />
                            </div>
                        </div>
                    );
                })}
            </div>
        </aside>
    );
}
