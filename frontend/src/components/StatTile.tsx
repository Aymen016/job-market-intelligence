import "./StatTile.css";

export function StatTile({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="stat-tile">
      <div className={`stat-tile__value ${accent ? "stat-tile__value--accent" : ""}`}>{value}</div>
      <div className="stat-tile__label">{label}</div>
    </div>
  );
}
