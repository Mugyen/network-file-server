interface QrCodeDisplayProps {
  svgContent: string;
}

function QrCodeDisplay({ svgContent }: QrCodeDisplayProps) {
  return (
    <div className="flex flex-col items-center">
      <div
        className="max-w-48"
        dangerouslySetInnerHTML={{ __html: svgContent }}
      />
      <p className="text-sm text-gray-500 mt-2">Scan to connect</p>
    </div>
  );
}

export default QrCodeDisplay;
