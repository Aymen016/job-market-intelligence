import "./DataTable.css";

export interface Column<T> {
  key: keyof T;
  label: string;
  align?: "left" | "right";
  tabular?: boolean;
}

export function DataTable<T extends object>({
  columns,
  rows,
}: {
  columns: Column<T>[];
  rows: T[];
}) {
  return (
    <div className="data-table__scroll">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={String(c.key)} style={{ textAlign: c.align ?? "left" }}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td
                  key={String(c.key)}
                  className={c.tabular ? "tabular" : ""}
                  style={{ textAlign: c.align ?? "left" }}
                >
                  {String(row[c.key as keyof T])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
