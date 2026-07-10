import "./SplitBar.css";

export interface SplitSegment {
  label: string;
  value: number;
  pct: number;
  color: string;
}

export function SplitBar({ segments }: { segments: SplitSegment[] }) {
  return (
    <div className="split-bar">
      <div className="split-bar__track">
        {segments.map((s, i) => (
          <div
            key={s.label}
            className="split-bar__segment"
            style={{
              width: `${s.pct}%`,
              background: s.color,
              marginLeft: i === 0 ? 0 : "2px",
            }}
            tabIndex={0}
          >
            <div className="split-bar__tooltip" role="tooltip">
              <strong className="tabular">{s.value.toLocaleString()}</strong>
              <span>{s.label} · {s.pct}%</span>
            </div>
          </div>
        ))}
      </div>
      <div className="split-bar__legend">
        {segments.map((s) => (
          <div className="split-bar__legend-item" key={s.label}>
            <span className="split-bar__swatch" style={{ background: s.color }} />
            <span className="split-bar__legend-label">{s.label}</span>
            <span className="split-bar__legend-value tabular">{s.pct}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
