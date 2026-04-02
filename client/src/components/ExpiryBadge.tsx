/**
 * Countdown badge for file TTL expiry.
 *
 * Displays time remaining until a file expires with urgency-based colors:
 * - Red when < 1 hour remaining
 * - Orange when < 6 hours remaining
 * - Grey otherwise
 *
 * Updates every 60 seconds.
 */

import { useEffect, useState } from "react";

interface ExpiryBadgeProps {
  expiresAt: string;
}

function formatTimeLeft(expiresAt: string): string {
  const diff = new Date(expiresAt).getTime() - Date.now();
  if (diff <= 0) return "Expired";
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  if (days > 0) return `${String(days)}d left`;
  if (hours > 0) return `${String(hours)}h left`;
  return `${String(minutes)}m left`;
}

function getUrgencyClass(expiresAt: string): string {
  const diff = new Date(expiresAt).getTime() - Date.now();
  const hours = diff / 3600000;
  if (hours < 1) return "text-red-600 dark:text-red-400";
  if (hours < 6) return "text-orange-600 dark:text-orange-400";
  return "text-gray-500 dark:text-gray-400";
}

export function ExpiryBadge({ expiresAt }: ExpiryBadgeProps): React.ReactElement {
  const [timeLeft, setTimeLeft] = useState(formatTimeLeft(expiresAt));
  const [urgencyClass, setUrgencyClass] = useState(getUrgencyClass(expiresAt));

  useEffect(() => {
    function update(): void {
      setTimeLeft(formatTimeLeft(expiresAt));
      setUrgencyClass(getUrgencyClass(expiresAt));
    }

    const interval = window.setInterval(update, 60000);
    return () => clearInterval(interval);
  }, [expiresAt]);

  return (
    <span className={`text-xs font-medium ${urgencyClass}`} title={`Expires: ${expiresAt}`}>
      {timeLeft}
    </span>
  );
}
