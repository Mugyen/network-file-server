import { useState, useEffect, useRef } from "react";
import { X, Copy, Check, Loader2 } from "lucide-react";
import { createShareLink, ShareTTL, TTL_LABELS, TTL_OPTIONS } from "../api/shares.ts";

interface ShareDialogProps {
  filePath: string;
  fileName: string;
  onClose: () => void;
}

/**
 * Modal dialog for creating a share link with TTL selection.
 * Two phases: (1) TTL picker + Create button, (2) share URL display + Copy button.
 */
function ShareDialog({ filePath, fileName, onClose }: ShareDialogProps) {
  const [selectedTTL, setSelectedTTL] = useState<ShareTTL>(ShareTTL.ONE_HOUR);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const urlInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent): void {
      if (e.key === "Escape") {
        onClose();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  async function handleCreate(): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const link = await createShareLink(filePath, selectedTTL);
      setShareUrl(link.share_url);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to create share link";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  async function handleCopy(): Promise<void> {
    if (shareUrl === null) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback: select the text so user can copy manually
      urlInputRef.current?.select();
    }
  }

  function handleOverlayClick(e: React.MouseEvent): void {
    if (e.target === e.currentTarget) {
      onClose();
    }
  }

  function handleTTLChange(e: React.ChangeEvent<HTMLSelectElement>): void {
    setSelectedTTL(Number(e.target.value) as ShareTTL);
  }

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50"
      onClick={handleOverlayClick}
    >
      <div className="w-full max-w-sm rounded-lg bg-white dark:bg-gray-800 p-6 shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-100">
            Share {fileName}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {error !== null && (
          <p className="text-sm text-red-600 dark:text-red-400 mb-3">{error}</p>
        )}

        {shareUrl === null ? (
          /* Phase 1: TTL selection + Create */
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Link expires in
            </label>
            <select
              value={selectedTTL}
              onChange={handleTTLChange}
              className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 mb-4"
            >
              {TTL_OPTIONS.map((ttl) => (
                <option key={ttl} value={ttl}>
                  {TTL_LABELS[ttl]}
                </option>
              ))}
            </select>

            <button
              type="button"
              onClick={() => void handleCreate()}
              disabled={loading}
              className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
            >
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              {loading ? "Creating..." : "Create Share Link"}
            </button>
          </div>
        ) : (
          /* Phase 2: Share URL display + Copy */
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Share URL
            </label>
            <div className="flex gap-2">
              <input
                ref={urlInputRef}
                type="text"
                value={shareUrl}
                readOnly
                className="flex-1 rounded-md border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-3 py-2 text-sm text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                onClick={() => urlInputRef.current?.select()}
              />
              <button
                type="button"
                onClick={() => void handleCopy()}
                className={`rounded-md px-3 py-2 text-sm font-medium transition-colors flex items-center gap-1 ${
                  copied
                    ? "bg-green-600 text-white"
                    : "bg-blue-600 text-white hover:bg-blue-700"
                }`}
              >
                {copied ? (
                  <>
                    <Check className="h-4 w-4" />
                    Copied!
                  </>
                ) : (
                  <>
                    <Copy className="h-4 w-4" />
                    Copy
                  </>
                )}
              </button>
            </div>
            <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
              Expires in {TTL_LABELS[selectedTTL]}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default ShareDialog;
