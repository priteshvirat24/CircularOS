"use client";

import { createContext, useContext, useState } from "react";
import { api, ApiError, TokenResponse } from "@/lib/api/client";

type AuthState = { session: TokenResponse | null; signIn: (email: string, password: string) => Promise<void>; signOut: () => void };
const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<TokenResponse | null>(null);
  const signIn = async (email: string, password: string) => {
    const token = await api.login(email, password);
    api.setAccessToken(token.access_token);
    setSession(token);
  };
  const signOut = () => { api.setAccessToken(null); setSession(null); };
  return <AuthContext.Provider value={{ session, signIn, signOut }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error("useAuth must be rendered beneath AuthProvider");
  return auth;
}

export function AuthGate({ children }: { children: React.ReactNode }) {
  const { session, signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  if (session) return <>{children}</>;
  return <main className="min-h-screen bg-[var(--background-secondary)] flex items-center justify-center p-6"><form className="editorial-card w-full max-w-md p-8 space-y-5" onSubmit={async event => { event.preventDefault(); setPending(true); setError(null); try { await signIn(email, password); } catch (cause) { setError(cause instanceof ApiError ? cause.message : "Unable to sign in"); } finally { setPending(false); } }}><div><p className="text-[11px] font-bold tracking-widest text-[var(--text-muted)] uppercase">CircularOS</p><h1 className="text-[28px] font-semibold mt-2">Sign in to the live registry</h1><p className="text-sm text-[var(--text-secondary)] mt-2">Your session is held only in memory and is used for authorized API requests.</p></div><label className="block text-sm font-medium">Email<input className="mt-2 w-full border border-[var(--border-default)] rounded-lg p-2.5" type="email" value={email} onChange={event => setEmail(event.target.value)} required /></label><label className="block text-sm font-medium">Password<input className="mt-2 w-full border border-[var(--border-default)] rounded-lg p-2.5" type="password" value={password} onChange={event => setPassword(event.target.value)} required /></label>{error && <p className="text-sm text-[var(--danger)]">{error}</p>}<button className="w-full bg-[var(--primary)] text-white rounded-lg py-2.5 font-medium disabled:opacity-60" disabled={pending}>{pending ? "Signing in…" : "Sign in"}</button></form></main>;
}
