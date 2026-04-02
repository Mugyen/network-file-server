/**
 * Connection status overlay for remote mounts.
 *
 * Shows a persistent banner and greys out the file browser when
 * the mount is offline (503) or expired (410).
 */

import { Loader2 } from "lucide-react";
import { MountStatus } from "../hooks/useMountStatus.ts";

interface MountStatusOverlayProps {
  status: MountStatus;
  children: React.ReactNode;
}

export function MountStatusOverlay({ status, children }: MountStatusOverlayProps): React.ReactElement {
  if (status === MountStatus.OFFLINE) {
    return (
      <>
        <div className="bg-amber-100 dark:bg-amber-900/50 border-b border-amber-300 dark:border-amber-700 px-4 py-3 text-center text-amber-800 dark:text-amber-200 flex items-center justify-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>Host Offline — Waiting for reconnection...</span>
        </div>
        <div className="opacity-50 pointer-events-none">{children}</div>
      </>
    );
  }

  if (status === MountStatus.EXPIRED) {
    return (
      <>
        <div className="bg-red-100 dark:bg-red-900/50 border-b border-red-300 dark:border-red-700 px-4 py-3 text-center text-red-800 dark:text-red-200">
          <span>Mount Expired</span>
          <span className="mx-2">—</span>
          <a href="/" className="underline font-medium hover:no-underline">
            Back to home
          </a>
        </div>
        <div className="opacity-50 pointer-events-none">{children}</div>
      </>
    );
  }

  return <>{children}</>;
}
