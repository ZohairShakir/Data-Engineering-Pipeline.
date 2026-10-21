import { ArrowUpDown } from "lucide-react";
import { useMemo, useState } from "react";

import { categoryLabel, currency, integer } from "../format";
import type { ProductPerformance } from "../types";

type SortKey = keyof Pick<ProductPerformance, "product_name" | "category" | "revenue" | "units">;

export function ProductTable({ rows }: { rows: ProductPerformance[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("revenue");
  const [descending, setDescending] = useState(true);
  const sorted = useMemo(() => {
    return [...rows].sort((left, right) => {
      const a = left[sortKey];
      const b = right[sortKey];
      const result = typeof a === "number" && typeof b === "number"
        ? a - b
        : String(a).localeCompare(String(b));
      return descending ? -result : result;
    });
  }, [descending, rows, sortKey]);

  const updateSort = (key: SortKey) => {
    if (sortKey === key) {
      setDescending((value) => !value);
    } else {
      setSortKey(key);
      setDescending(key === "revenue" || key === "units");
    }
  };

  const headers: Array<{ key: SortKey; label: string }> = [
    { key: "product_name", label: "Product" },
    { key: "category", label: "Category" },
    { key: "revenue", label: "Revenue" },
    { key: "units", label: "Units" },
  ];

  return (
    <section className="table-panel" id="products">
      <h2>Top products</h2>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {headers.map(({ key, label }) => (
                <th key={key} aria-sort={sortKey === key ? (descending ? "descending" : "ascending") : "none"}>
                  <button type="button" onClick={() => updateSort(key)}>
                    {label}<ArrowUpDown size={14} aria-hidden="true" />
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.slice(0, 8).map((row) => (
              <tr key={row.product_id}>
                <td>{row.product_name}</td>
                <td>{categoryLabel(row.category)}</td>
                <td className="numeric">{currency(row.revenue)}</td>
                <td className="numeric">{integer(row.units)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
