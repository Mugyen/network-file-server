import { useState } from "react";
import { accounts, AccountApiError } from "../api/accounts.ts";

function nextTarget(): string {
  const p = new URLSearchParams(window.location.search).get("next");
  return p && p.startsWith("/") ? p : "/";
}

export default function SignupPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await accounts.signup(username, password, email.trim() || null);
      await accounts.login(username, password);
      window.location.assign(nextTarget());
    } catch (err) {
      if (err instanceof AccountApiError && err.status === 409) {
        setError("That username is already taken");
      } else if (err instanceof AccountApiError && err.status === 400) {
        setError("Password is too weak or invalid");
      } else {
        setError("Connection failed");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center px-4">
      <div className="w-full max-w-sm bg-white dark:bg-gray-800 rounded-xl shadow-lg p-8">
        <h1 className="text-2xl font-bold text-gray-800 dark:text-gray-100 text-center mb-1">
          Create account
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 text-center mb-6">
          Pick any unused username
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
          <input
            aria-label="Email (optional)"
            type="email"
            className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-gray-900 dark:text-gray-100"
            placeholder="Email (optional)"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          {error && (
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          )}
          <button
            type="submit"
            disabled={busy || !username || !password}
            className="w-full rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-2 font-medium"
          >
            {busy ? "Creating…" : "Create account"}
          </button>
        </form>
        <div className="mt-4 text-sm text-center">
          <a href="/login" className="text-blue-600 hover:underline">
            Already have an account? Sign in
          </a>
        </div>
      </div>
    </div>
  );
}
