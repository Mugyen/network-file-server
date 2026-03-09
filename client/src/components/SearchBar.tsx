import { Search, X, Loader2 } from "lucide-react";

interface SearchBarProps {
  query: string;
  onQueryChange: (q: string) => void;
  isSearching: boolean;
}

/**
 * Full-width search input with search icon, loading indicator, and clear button.
 * Renders on its own row above the toolbar.
 */
function SearchBar({ query, onQueryChange, isSearching }: SearchBarProps) {
  function handleChange(e: React.ChangeEvent<HTMLInputElement>): void {
    onQueryChange(e.target.value);
  }

  function handleClear(): void {
    onQueryChange("");
  }

  return (
    <div className="relative w-full">
      <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
        {isSearching ? (
          <Loader2 className="h-4 w-4 text-gray-400 dark:text-gray-500 animate-spin" />
        ) : (
          <Search className="h-4 w-4 text-gray-400 dark:text-gray-500" />
        )}
      </div>
      <input
        type="text"
        value={query}
        onChange={handleChange}
        placeholder="Search files and folders..."
        className="w-full rounded-lg border border-gray-300 bg-white py-2 pl-10 pr-10 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:bg-gray-800 dark:border-gray-600 dark:text-gray-100 dark:placeholder-gray-400 dark:focus:border-blue-400 dark:focus:ring-blue-400/20"
      />
      {query !== "" && (
        <button
          type="button"
          onClick={handleClear}
          className="absolute inset-y-0 right-0 flex items-center pr-3 text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}

export default SearchBar;
