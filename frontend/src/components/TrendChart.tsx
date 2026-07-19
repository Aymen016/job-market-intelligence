import { useMemo, useRef, useState } from "react";
import "./TrendChart.css";

export interface TrendSeries {
  name: string;
  color: string;
  points: { x: string; y: number }[];
}

const WIDTH = 640;
const HEIGHT = 220;
const PAD_LEFT = 40;
const PAD_RIGHT = 16;
const PAD_TOP = 12;
const PAD_BOTTOM = 28;

export function TrendChart({ series }: { series: TrendSeries[] }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const xLabels = useMemo(() => {
    const set = new Set<string>();
    series.forEach((s) => s.points.forEach((p) => set.add(p.x)));
    return Array.from(set).sort();
  }, [series]);

  const maxY = Math.max(...series.flatMap((s) => s.points.map((p) => p.y)), 1);
  const niceMax = Math.ceil(maxY / 5) * 5 || 1;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(niceMax * f));

  const plotW = WIDTH - PAD_LEFT - PAD_RIGHT;
  const plotH = HEIGHT - PAD_TOP - PAD_BOTTOM;

  const xPos = (i: number) =>
    xLabels.length <= 1
      ? PAD_LEFT + plotW / 2
      : PAD_LEFT + (i / (xLabels.length - 1)) * plotW;
  const yPos = (v: number) => PAD_TOP + plotH - (v / niceMax) * plotH;

  function handleMove(e: React.PointerEvent<SVGSVGElement>) {
    const svg = svgRef.current;
    if (!svg || xLabels.length === 0) return;
    const rect = svg.getBoundingClientRect();
    const scaleX = WIDTH / rect.width;
    const mouseX = (e.clientX - rect.left) * scaleX;
    let nearest = 0;
    let best = Infinity;
    xLabels.forEach((_, i) => {
      const d = Math.abs(xPos(i) - mouseX);
      if (d < best) {
        best = d;
        nearest = i;
      }
    });
    setHoverIdx(nearest);
  }

  const hasData = xLabels.length > 0;

  return (
    <div className="trend-chart">
      {hasData ? (
        <svg
          ref={svgRef}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="trend-chart__svg"
          onPointerMove={handleMove}
          onPointerLeave={() => setHoverIdx(null)}
          role="img"
          aria-label="Postings per day by source"
        >
          {ticks.map((t) => (
            <g key={t}>
              <line
                x1={PAD_LEFT}
                x2={WIDTH - PAD_RIGHT}
                y1={yPos(t)}
                y2={yPos(t)}
                className="trend-chart__grid"
              />
              <text x={PAD_LEFT - 8} y={yPos(t) + 4} className="trend-chart__tick" textAnchor="end">
                {t.toLocaleString()}
              </text>
            </g>
          ))}

          <line
            x1={PAD_LEFT}
            x2={WIDTH - PAD_RIGHT}
            y1={PAD_TOP + plotH}
            y2={PAD_TOP + plotH}
            className="trend-chart__baseline"
          />

          {xLabels.map((label, i) => (
            <text key={label} x={xPos(i)} y={HEIGHT - 8} className="trend-chart__tick" textAnchor="middle">
              {label.slice(5)}
            </text>
          ))}

          {hoverIdx !== null && (
            <line
              x1={xPos(hoverIdx)}
              x2={xPos(hoverIdx)}
              y1={PAD_TOP}
              y2={PAD_TOP + plotH}
              className="trend-chart__crosshair"
            />
          )}

          {series.map((s) => {
            const byX = new Map(s.points.map((p) => [p.x, p.y]));
            const coords = xLabels
              .map((label, i) => (byX.has(label) ? [xPos(i), yPos(byX.get(label)!)] : null))
              .filter((c): c is [number, number] => c !== null);
            const path = coords.map((c, i) => `${i === 0 ? "M" : "L"}${c[0]},${c[1]}`).join(" ");
            return (
              <g key={s.name}>
                {coords.length > 1 && <path d={path} fill="none" stroke={s.color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />}
                {xLabels.map((label, i) => {
                  const y = byX.get(label);
                  if (y === undefined) return null;
                  return (
                    <circle
                      key={label}
                      cx={xPos(i)}
                      cy={yPos(y)}
                      r={5}
                      fill={s.color}
                      stroke="var(--surface)"
                      strokeWidth={2}
                    />
                  );
                })}
              </g>
            );
          })}
        </svg>
      ) : (
        <p className="trend-chart__empty">No daily history yet.</p>
      )}

      {hoverIdx !== null && hasData && (
        <div
          className="trend-chart__tooltip"
          style={{ left: `${(xPos(hoverIdx) / WIDTH) * 100}%` }}
        >
          <div className="trend-chart__tooltip-date">{xLabels[hoverIdx]}</div>
          {series.map((s) => {
            const pt = s.points.find((p) => p.x === xLabels[hoverIdx!]);
            return (
              <div className="trend-chart__tooltip-row" key={s.name}>
                <span className="trend-chart__tooltip-key" style={{ background: s.color }} />
                <span className="trend-chart__tooltip-name">{s.name}</span>
                <strong className="tabular">{pt ? pt.y.toLocaleString() : "—"}</strong>
              </div>
            );
          })}
        </div>
      )}

      <div className="trend-chart__legend">
        {series.map((s) => (
          <div className="trend-chart__legend-item" key={s.name}>
            <span className="trend-chart__swatch" style={{ background: s.color }} />
            {s.name}
          </div>
        ))}
      </div>
    </div>
  );
}
