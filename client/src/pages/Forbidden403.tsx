import { useState } from "react";
import { ShieldAlert } from "lucide-react";
import { accounts, AccountApiError } from "../api/accounts.ts";

/** Mount code from ?code= or the /m/{code}/ segment of ?next=. */
function mountCode(): string {
  const params = new URLSearchParams(window.location.search);
  const direct = params.get("code");
  if (direct) return direct;
  const next = params.get("next") ?? "";
  const m = /^\/m\/([^/]+)/.exec(next);
  return m ? m[1] : "";
}

export default function Forbidden403() {
  const [code, setCode] = useState(mountCode());
  const [state, setState] = useState<"idle" | "sent" | "error">("idle");

  async function requestAccess(): Promise<void> {
    try {
      await accounts.createRequest(code);
      setState("sent");
    } catch (err) {
      if (err instanceof AccountApiError && err.status === 401) {
        window.location.assign(
          `/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`,
        );
        return;
      }
      setState("error");
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center px-4">
      <div className="w-full max-w-md bg-white dark:bg-gray-800 rounded-xl shadow-lg p-8 text-center">
        <ShieldAlert className="h-10 w-10 text-amber-500 mx-auto mb-3" />
        <h1 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-1">
          Access denied
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
          Your account is not on the allowlist for this server.
        </p>
        {state === "sent" ? (
          <p className="text-sm text-green-600 dark:text-green-400">
            Request sent. The owner or an admin will review it.
          </p>
        ) : (
          <div className="space-y-3">
            <input
              aria-label="Mount code"
              className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-gray-900 dark:text-gray-100"
              placeholder="Mount code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
            {state === "error" && (
              <p className="text-sm text-red-600 dark:text-red-400">
                Could not send request.
              </p>
            )}
            <button
              disabled={!code}
              onClick={() => void requestAccess()}
              className="w-full rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-2 font-medium"
            >
              Request access
            </button>
          </div>
        )}
        <a
          href="/"
          className="mt-4 inline-block text-sm text-gray-500 dark:text-gray-400 hover:underline"
        >
          Back to home
        </a>
      </div>
    </div>
  );
}
