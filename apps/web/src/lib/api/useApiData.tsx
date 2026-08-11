"use client";

import { useCallback, useEffect, useState } from "react";

export function useApiData<T>(load: () => Promise<T>, dependencies: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try { setData(await load()); } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to load live data"); } finally { setLoading(false); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencies);
  useEffect(() => { void reload(); }, [reload]);
  return { data, error, loading, reload };
}

export function usePublicApiData<T>(load: () => Promise<T>, dependencies: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try { setData(await load()); } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to load dashboard data"); } finally { setLoading(false); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencies);
  useEffect(() => { void reload(); }, [reload]);
  return { data, error, loading, reload };
}

export function DataState({ loading, error, empty, children }: { loading: boolean; error: string | null; empty: boolean; children: React.ReactNode }) {
  if (loading) return <div className="p-8 text-sm text-[var(--text-secondary)]">Loading live data…</div>;
  if (error) return <div className="m-4 rounded-xl border border-[#FECACA] bg-[#FEF2F2] p-4 text-sm text-[#B91C1C]">{error}</div>;
  if (empty) return <div className="p-8 text-sm text-[var(--text-secondary)]">No persisted records are available for this view.</div>;
  return <>{children}</>;
}
