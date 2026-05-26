import './Skeleton.css';

interface SkeletonProps {
  width: string;
  height: string;
}

export function Skeleton({ width, height }: SkeletonProps) {
  return (
    <div
      className="skeleton"
      style={{ width, height }}
    />
  );
}

export function GraphSkeleton() {
  return (
    <div className="graph-skeleton">
      <Skeleton width="100%" height="600px" />
    </div>
  );
}