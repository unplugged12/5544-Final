import "./Skeleton.css";

/**
 * Minimal skeleton loader primitives.
 * - <Skeleton /> — one block; pass width/height or custom className.
 * - <SkeletonCard /> — card-sized placeholder matching KB/history card shape.
 * - <SkeletonRow /> — a horizontal row for tabular/list UIs.
 */

export default function Skeleton({ width, height, radius, className = "", style }) {
  const s = {
    width,
    height,
    borderRadius: radius,
    ...(style || {}),
  };
  return <span className={`skeleton ${className}`.trim()} style={s} aria-hidden="true" />;
}

export function SkeletonCard() {
  return (
    <div className="skeleton-card" aria-hidden="true">
      <div className="skeleton-card__top">
        <Skeleton height={14} width="60%" />
        <Skeleton height={18} width={64} radius={12} />
      </div>
      <Skeleton height={12} width="95%" />
      <Skeleton height={12} width="88%" />
      <Skeleton height={12} width="72%" />
      <Skeleton height={10} width="40%" className="skeleton-card__foot" />
    </div>
  );
}

export function SkeletonRow({ columns = 6 }) {
  return (
    <div className="skeleton-row" aria-hidden="true">
      {Array.from({ length: columns }, (_, i) => (
        <Skeleton key={i} height={12} width={i === 1 ? "90%" : "60%"} />
      ))}
    </div>
  );
}

export function SkeletonGrid({ count = 6 }) {
  return (
    <div className="skeleton-grid">
      {Array.from({ length: count }, (_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}

export function SkeletonList({ rows = 6, columns = 6 }) {
  return (
    <div className="skeleton-list">
      {Array.from({ length: rows }, (_, i) => (
        <SkeletonRow key={i} columns={columns} />
      ))}
    </div>
  );
}
