import { Sun, Moon, Monitor } from "lucide-react";
import { ThemeMode } from "../hooks/useTheme.ts";

interface ThemeToggleProps {
  mode: ThemeMode;
  isDark: boolean;
  onToggle: () => void;
}

/**
 * Icon toggle button that cycles through SYSTEM -> DARK -> LIGHT -> SYSTEM.
 * Shows Sun when dark (click to switch to light), Moon when light.
 * Shows a Monitor indicator overlay when in SYSTEM mode.
 */
function ThemeToggle({ mode, isDark, onToggle }: ThemeToggleProps) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="relative p-2 rounded-lg text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700 transition-colors"
      title={`Theme: ${mode}`}
    >
      {isDark ? (
        <Sun className="h-5 w-5" />
      ) : (
        <Moon className="h-5 w-5" />
      )}
      {mode === ThemeMode.SYSTEM && (
        <Monitor className="h-2.5 w-2.5 absolute bottom-1 right-1 text-blue-500 dark:text-blue-400" />
      )}
    </button>
  );
}

export default ThemeToggle;
