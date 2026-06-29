/** A tiny dependency-free price sparkline. */
export function Sparkline({
  values,
  width = 240,
  height = 44,
}: {
  values: number[];
  width?: number;
  height?: number;
}) {
  if (values.length < 2) {
    return <svg width={width} height={height} aria-hidden />;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const points = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * width;
      const y = height - ((v - min) / span) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const up = values[values.length - 1] >= values[0];

  return (
    <svg width={width} height={height} className="block">
      <polyline
        points={points}
        fill="none"
        strokeWidth={1.5}
        className={up ? "stroke-emerald-400" : "stroke-rose-400"}
      />
    </svg>
  );
}
