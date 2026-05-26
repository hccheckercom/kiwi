import './ScanProgress.css';

interface ScanProgressProps {
  patternsChecked: number;
  totalPatterns: number;
  violationsFound: number;
  isScanning: boolean;
}

export function ScanProgress({
  patternsChecked,
  totalPatterns,
  violationsFound,
  isScanning
}: ScanProgressProps) {
  const progress = totalPatterns > 0 ? (patternsChecked / totalPatterns) * 100 : 0;

  return (
    <div className="scan-progress">
      <div className="progress-bar">
        <div
          className="progress-fill"
          style={{ width: `${progress}%` }}
        />
      </div>
      <div className="progress-text">
        {isScanning ? (
          <>
            Scanning: {patternsChecked}/{totalPatterns} patterns • {violationsFound} violations
          </>
        ) : (
          <>
            Scan complete: {violationsFound} violations found
          </>
        )}
      </div>
    </div>
  );
}