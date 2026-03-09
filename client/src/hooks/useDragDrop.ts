import { useCallback, useRef, useState } from "react";

interface DragHandlers {
  onDragEnter: (e: React.DragEvent) => void;
  onDragLeave: (e: React.DragEvent) => void;
  onDragOver: (e: React.DragEvent) => void;
  onDrop: (e: React.DragEvent) => void;
}

interface DragDropResult {
  isDragging: boolean;
  dragHandlers: DragHandlers;
}

/**
 * Hook for drag-and-drop file upload with counter pattern.
 * The drag counter prevents overlay flicker caused by dragenter/dragleave
 * events firing on child elements.
 *
 * Increment counter on dragenter, decrement on dragleave, reset on drop.
 * isDragging = counter > 0.
 */
export function useDragDrop(onDrop: (files: FileList) => void): DragDropResult {
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const dragCounter = useRef<number>(0);

  const handleDragEnter = useCallback((e: React.DragEvent): void => {
    e.preventDefault();
    dragCounter.current += 1;
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent): void => {
    e.preventDefault();
    dragCounter.current -= 1;
    if (dragCounter.current === 0) {
      setIsDragging(false);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent): void => {
    e.preventDefault();
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent): void => {
      e.preventDefault();
      dragCounter.current = 0;
      setIsDragging(false);
      if (e.dataTransfer.files.length > 0) {
        onDrop(e.dataTransfer.files);
      }
    },
    [onDrop],
  );

  return {
    isDragging,
    dragHandlers: {
      onDragEnter: handleDragEnter,
      onDragLeave: handleDragLeave,
      onDragOver: handleDragOver,
      onDrop: handleDrop,
    },
  };
}
