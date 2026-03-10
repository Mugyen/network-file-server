import { Lock } from "lucide-react";

interface ModeBadgesProps {
  readOnly: boolean;
  passwordProtected: boolean;
}

function ModeBadges({ readOnly, passwordProtected }: ModeBadgesProps) {
  if (!readOnly && !passwordProtected) {
    return null;
  }

  return (
    <div className="flex items-center gap-2 ml-3">
      {readOnly && (
        <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300">
          Read Only
        </span>
      )}
      {passwordProtected && (
        <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
          <Lock className="h-3.5 w-3.5" />
          Protected
        </span>
      )}
    </div>
  );
}

export default ModeBadges;
