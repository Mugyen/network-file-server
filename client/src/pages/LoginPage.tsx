import { useState } from "react";
import { accounts, AccountApiError } from "../api/accounts.ts";

function nextTarget(): string {
  const p = new URLSearchParams(window.location.search).get("next");
  return p && p.startsWith("/") ? p : "/";
}

export default function RelayLoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(
    new URLSearchParams(window.location.search).get("sso_error")
      ? "Sign-in with Mugyen failed. Please try again."
      : null,
  );
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await accounts.login(username, password);
      window.location.assign(nextTarget());
    } catch (err) {
      setError(
        err instanceof AccountApiError && err.status === 401
          ? "Invalid username or password"
          : "Connection failed",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center px-4">
      <div className="w-full max-w-sm bg-white dark:bg-gray-800 rounded-xl shadow-lg p-8">
        <h1 className="text-2xl font-bold text-gray-800 dark:text-gray-100 text-center mb-1">
          Sign in
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 text-center mb-6">
          Access restricted servers with your account
        </p>
        <form onSubmit={(e) => void submit(e)} className="space-y-3">
          <input
            aria-label="Username"
            className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-gray-900 dark:text-gray-100"
            placeholder="Username"
            value={username}
            autoFocus
            onChange={(e) => setUsername(e.target.value)}
          />
          <input
            aria-label="Password"
            type="password"
            className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-gray-900 dark:text-gray-100"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error && (
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          )}
          <button
            type="submit"
            disabled={busy || !username || !password}
            className="w-full rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-2 font-medium"
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <div className="my-4 flex items-center gap-3 text-xs text-gray-400 dark:text-gray-500">
          <span className="h-px flex-1 bg-gray-200 dark:bg-gray-700" />
          or
          <span className="h-px flex-1 bg-gray-200 dark:bg-gray-700" />
        </div>
        <a
          href={`/auth/oidc/login?next=${encodeURIComponent(nextTarget())}`}
          className="block w-full rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 text-center text-gray-800 dark:text-gray-100 py-2 font-medium"
        >
          Sign in with Mugyen
        </a>
        <div className="mt-4 flex items-center justify-between text-sm">
          <a href="/signup" className="text-blue-600 hover:underline">
            Create account
          </a>
          <button
            onClick={() => window.location.assign(nextTarget())}
            className="text-gray-500 dark:text-gray-400 hover:underline"
          >
            Continue as guest
          </button>
        </div>
      </div>
    </div>
  );
}
