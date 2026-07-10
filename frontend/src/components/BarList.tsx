import "./BarList.css";

export interface BarListItem {
  label: string;
  value: number;
  detail?: string;
}

export function BarList({
  items,
  color = "var(--series-1)",
  formatValue = (v: number) => v.toLocaleString(),
}: {
  items: BarListItem[];
  color?: string;
  formatValue?: (v: number) => string;
}) {
  const max = Math.max(...items.map((i) => i.value), 1);

  return (
    <div className="bar-list" role="list">
      {items.map((item) => {
        const pct = Math.max((item.value / max) * 100, 2);
        return (
          <div className="bar-list__row" role="listitem" tabIndex={0} key={item.label}>
            <div className="bar-list__label" title={item.label}>
              {item.label}
            </div>
            <div className="bar-list__track">
              <div
                className="bar-list__fill"
                style={{ width: `${pct}%`, background: color }}
              />
            </div>
            <div className="bar-list__value tabular">{formatValue(item.value)}</div>
            <div className="bar-list__tooltip" role="tooltip">
              <strong className="tabular">{formatValue(item.value)}</strong>
              <span>{item.detail ?? item.label}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
