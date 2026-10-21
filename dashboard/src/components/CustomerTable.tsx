import { currency, integer } from "../format";
import type { CustomerValue } from "../types";

export function CustomerTable({ rows }: { rows: CustomerValue[] }) {
  return (
    <section className="table-panel secondary-table" id="customers">
      <h2>Highest-value customers</h2>
      <div className="table-scroll">
        <table>
          <thead><tr><th>Customer</th><th>Customer ID</th><th>Orders</th><th>Lifetime value</th></tr></thead>
          <tbody>
            {rows.slice(0, 8).map((row) => (
              <tr key={row.customer_id}>
                <td>{row.customer_name}</td>
                <td>{row.customer_id}</td>
                <td className="numeric">{integer(row.order_count)}</td>
                <td className="numeric">{currency(row.lifetime_value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
