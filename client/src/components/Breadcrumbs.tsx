interface BreadcrumbsProps {
  currentPath: string;
  onNavigate: (path: string) => void;
}

interface BreadcrumbSegment {
  label: string;
  path: string;
}

function buildSegments(currentPath: string): BreadcrumbSegment[] {
  if (currentPath === "") {
    return [];
  }
  const parts = currentPath.split("/").filter((part) => part !== "");
  const segments: BreadcrumbSegment[] = [];
  for (let i = 0; i < parts.length; i++) {
    segments.push({
      label: parts[i],
      path: parts.slice(0, i + 1).join("/"),
    });
  }
  return segments;
}

/**
 * Renders clickable breadcrumb path segments: Home / photos / vacation
 * Last segment is plain text (current location). All others are clickable.
 */
function Breadcrumbs({ currentPath, onNavigate }: BreadcrumbsProps) {
  const segments = buildSegments(currentPath);

  return (
    <nav className="flex items-center gap-1 text-sm py-2" aria-label="Breadcrumb">
      {segments.length === 0 ? (
        <span className="text-gray-800 dark:text-gray-100 font-medium">Home</span>
      ) : (
        <button
          type="button"
          onClick={() => onNavigate("")}
          className="text-blue-600 dark:text-blue-400 hover:underline"
        >
          Home
        </button>
      )}

      {segments.map((segment, index) => {
        const isLast = index === segments.length - 1;
        return (
          <span key={segment.path} className="flex items-center gap-1">
            <span className="text-gray-400 dark:text-gray-500" aria-hidden="true">/</span>
            {isLast ? (
              <span className="text-gray-800 dark:text-gray-100 font-medium">{segment.label}</span>
            ) : (
              <button
                type="button"
                onClick={() => onNavigate(segment.path)}
                className="text-blue-600 dark:text-blue-400 hover:underline"
              >
                {segment.label}
              </button>
            )}
          </span>
        );
      })}
    </nav>
  );
}

export default Breadcrumbs;
