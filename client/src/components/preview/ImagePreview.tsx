import { useState, useEffect, useCallback } from "react";
import type { FileEntry } from "../../types/files.ts";
import { ChevronLeft, ChevronRight, Download } from "lucide-react";

interface ImagePreviewProps {
  url: string;
  file: FileEntry;
  imageFiles: FileEntry[];
  currentIndex: number;
  onNavigate: (index: number) => void;
  downloadUrl: string;
}

/**
 * Image preview with zoom toggle and gallery navigation.
 *
 * Click toggles between fit-to-container and actual-size (scrollable).
 * Left/right arrow buttons and keyboard arrows navigate between images.
 * Position indicator shows "N of M" at bottom center.
 */
function ImagePreview({
  url,
  file,
  imageFiles,
  currentIndex,
  onNavigate,
  downloadUrl,
}: ImagePreviewProps) {
  const [isZoomed, setIsZoomed] = useState<boolean>(false);
  const hasMultiple = imageFiles.length > 1;

  function toggleZoom(): void {
    setIsZoomed((prev) => !prev);
  }

  const navigatePrev = useCallback((): void => {
    if (currentIndex > 0) {
      onNavigate(currentIndex - 1);
      setIsZoomed(false);
    }
  }, [currentIndex, onNavigate]);

  const navigateNext = useCallback((): void => {
    if (currentIndex < imageFiles.length - 1) {
      onNavigate(currentIndex + 1);
      setIsZoomed(false);
    }
  }, [currentIndex, imageFiles.length, onNavigate]);

  // Keyboard navigation for arrows
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent): void {
      if (e.key === "ArrowLeft") {
        navigatePrev();
      } else if (e.key === "ArrowRight") {
        navigateNext();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [navigatePrev, navigateNext]);

  return (
    <div className="relative flex flex-col items-center">
      {/* Image container */}
      <div
        className={`relative bg-gray-100 dark:bg-gray-900 flex items-center justify-center ${
          isZoomed ? "overflow-auto max-h-[75vh]" : "overflow-hidden"
        }`}
      >
        <img
          src={url}
          alt={file.name}
          onClick={toggleZoom}
          className={`${
            isZoomed
              ? "max-w-none cursor-zoom-out"
              : "max-h-[70vh] max-w-full object-contain cursor-zoom-in"
          }`}
        />
      </div>

      {/* Gallery navigation arrows */}
      {hasMultiple && (
        <>
          {currentIndex > 0 && (
            <button
              type="button"
              onClick={navigatePrev}
              className="absolute left-2 top-1/2 -translate-y-1/2 rounded-full bg-black/40 p-2 text-white hover:bg-black/60 transition-colors"
              aria-label="Previous image"
            >
              <ChevronLeft className="h-5 w-5" />
            </button>
          )}
          {currentIndex < imageFiles.length - 1 && (
            <button
              type="button"
              onClick={navigateNext}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full bg-black/40 p-2 text-white hover:bg-black/60 transition-colors"
              aria-label="Next image"
            >
              <ChevronRight className="h-5 w-5" />
            </button>
          )}
        </>
      )}

      {/* Bottom bar: position indicator + download */}
      <div className="mt-2 flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400">
        {hasMultiple && (
          <span>
            {String(currentIndex + 1)} of {String(imageFiles.length)}
          </span>
        )}
        <a
          href={downloadUrl}
          download
          className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
          title="Download"
        >
          <Download className="h-4 w-4" />
          Download
        </a>
      </div>
    </div>
  );
}

export default ImagePreview;
