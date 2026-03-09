import { useEffect, useState } from "react";

function getPathFromUrl(): string {
  const params = new URLSearchParams(window.location.search);
  return params.get("path") ?? "";
}

interface PathNavigation {
  currentPath: string;
  navigateTo: (path: string) => void;
}

/**
 * Syncs folder navigation path with the URL query parameter `?path=`.
 * Supports browser back/forward via popstate events.
 */
export function usePathNavigation(): PathNavigation {
  const [currentPath, setCurrentPath] = useState<string>(getPathFromUrl());

  useEffect(() => {
    function handlePopState(): void {
      setCurrentPath(getPathFromUrl());
    }
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  function navigateTo(path: string): void {
    const params = new URLSearchParams();
    if (path !== "") {
      params.set("path", path);
    }
    const search = params.toString();
    const newUrl = search !== "" ? `?${search}` : window.location.pathname;
    window.history.pushState({}, "", newUrl);
    setCurrentPath(path);
  }

  return { currentPath, navigateTo };
}
