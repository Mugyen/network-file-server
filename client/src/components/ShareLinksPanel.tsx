import { useState, useEffect, useCallback, useRef } from "react";
import { X, Copy, Check, Trash2, Link } from "lucide-react";
import type { ShareLinkInfo } from "../api/shares.ts";
import { listShareLinks, revokeShareLink } from "../api/shares.ts";

interface ShareLinksPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

function formatDateTime(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatTimeRemaining(expiresAt: string): string {
  const now = Date.now();
  const expiry = new Date(expiresAt).getTime();
  const diffMs = expiry - now;

  if (diffMs <= 0) {
    return "expired";
  }

  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 60) {
    return `expires in ${String(diffMin)}min`;
  }
  const diffHours = Math.floor(diffMin / 60);
  const remainMin = diffMin % 60;
  if (remainMin === 0) {
    return `expires in ${String(diffHours)}h`;
  }
  return `expires in ${String(diffHours)}h ${String(remainMin)}min`;
}

function ShareLinkCard({ link, onRevoke }: { link: ShareLinkInfo; onRevoke: (token: string) => void }) {
  const [copied, setCopied] = useState<boolean>(false);
  const urlInputRef = useRef<HTMLInputElement>(null);

  async function handleCopy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(link.share_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      urlInputRef.current?.select();
    }
  }

  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-3">
      {/* File name and revoke */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <Link className="h-4 w-4 text-blue-500 flex-shrink-0" />
          <span className="text-sm font-medium text-gray-800 dark:text-gray-100 truncate">
            {link.file_name}
          </span>
        </div>
        <button
          type="button"
          onClick={() => onRevoke(link.token)}
          className="p-1 text-gray-400 hover:text-red-600 dark:hover:text-red-400 transition-colors flex-shrink-0"
          title="Revoke link"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>

      {/* Metadata */}
      <div className="text-xs text-gray-500 dark:text-gray-400 mb-2 space-y-0.5">
        <p>Created: {formatDateTime(link.created_at)}</p>
        <p className="capitalize">{formatTimeRemaining(link.expires_at)}</p>
      </div>

      {/* URL + copy */}
      <div className="flex gap-1">
        <input
          ref={urlInputRef}
          type="text"
          value={link.share_url}
          readOnly
          className="flex-1 min-w-0 rounded border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-2 py-1 text-xs text-gray-600 dark:text-gray-300 focus:outline-none"
          onClick={() => urlInputRef.current?.select()}
        />
        <button
          type="button"
          onClick={() => void handleCopy()}
          className={`rounded px-2 py-1 text-xs font-medium transition-colors flex items-center gap-1 ${
            copied
              ? "bg-green-600 text-white"
              : "bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-300 dark:hover:bg-gray-500"
          }`}
        >
          {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
        </button>
      </div>
    </div>
  );
}

/**
 * Slide-out panel listing active share links with revoke capability.
 * Follows the same pattern as ScratchpadPanel.
 */
function ShareLinksPanel({ isOpen, onClose }: ShareLinksPanelProps) {
  const [links, setLinks] = useState<ShareLinkInfo[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchLinks = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listShareLinks();
      setLinks(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to load share links";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      void fetchLinks();
    }
  }, [isOpen, fetchLinks]);

  async function handleRevoke(token: string): Promise<void> {
    try {
      await revokeShareLink(token);
      setLinks((prev) => prev.filter((link) => link.token !== token));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to revoke link";
      setError(message);
    }
  }

  return (
    <>
      {/* Backdrop overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-40"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Panel */}
      <div
        className={`fixed top-0 right-0 h-full w-full sm:w-96 bg-gray-50 dark:bg-gray-900 shadow-xl z-50 flex flex-col transition-transform duration-300 ease-in-out ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100">
            Share Links {links.length > 0 && `(${String(links.length)})`}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-md text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
            aria-label="Close share links panel"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-3 space-y-3">
          {isLoading && (
            <p className="text-center text-gray-500 dark:text-gray-400 py-8">
              Loading...
            </p>
          )}

          {error !== null && (
            <p className="text-center text-red-600 dark:text-red-400 py-4 text-sm">
              {error}
            </p>
          )}

          {!isLoading && error === null && links.length === 0 && (
            <p className="text-center text-gray-500 dark:text-gray-400 py-8">
              No active share links
            </p>
          )}

          {!isLoading &&
            links.map((link) => (
              <ShareLinkCard
                key={link.token}
                link={link}
                onRevoke={(token) => void handleRevoke(token)}
              />
            ))}
        </div>
      </div>
    </>
  );
}

export default ShareLinksPanel;
