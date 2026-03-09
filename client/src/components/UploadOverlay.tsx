interface UploadOverlayProps {
  visible: boolean;
}

/**
 * Full-page drop zone overlay shown when user drags files over the window.
 * pointer-events-none so drop events are handled by the parent div's handlers.
 */
function UploadOverlay({ visible }: UploadOverlayProps) {
  if (!visible) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-blue-500/30 pointer-events-none">
      <div className="rounded-xl border-4 border-dashed border-blue-400 bg-white/80 px-16 py-12">
        <p className="text-2xl font-semibold text-blue-600">
          Drop files to upload
        </p>
      </div>
    </div>
  );
}

export default UploadOverlay;
