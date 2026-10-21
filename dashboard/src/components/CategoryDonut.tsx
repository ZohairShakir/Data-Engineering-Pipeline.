import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

import { categoryLabel } from "../format";
import type { CategoryContribution } from "../types";

const colors = ["#2475e9", "#63aaf3", "#42ad72", "#f69a43", "#9664df", "#9aaabc"];

export function CategoryDonut({
  data,
  selectedCategory,
  onSelect,
}: {
  data: CategoryContribution[];
  selectedCategory: string;
  onSelect: (category: string) => void;
}) {
  return (
    <section className="panel category-panel">
      <h2>Category contribution</h2>
      <div className="category-content">
        <div className="donut" aria-label="Category revenue contribution donut chart">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey="contribution_percentage"
                nameKey="category"
                innerRadius="56%"
                outerRadius="82%"
                stroke="#ffffff"
                strokeWidth={2}
                animationDuration={500}
              >
                {data.map((item, index) => (
                  <Cell
                    key={item.category}
                    fill={colors[index % colors.length]}
                    opacity={
                      selectedCategory === "all" || selectedCategory === item.category ? 1 : 0.3
                    }
                  />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <strong>100%</strong>
        </div>
        <div className="category-legend">
          {data.map((item, index) => (
            <button
              type="button"
              key={item.category}
              className={selectedCategory === item.category ? "selected" : ""}
              onClick={() => onSelect(selectedCategory === item.category ? "all" : item.category)}
            >
              <span className="legend-dot" style={{ background: colors[index % colors.length] }} />
              <span>{categoryLabel(item.category)}</span>
              <strong>{item.contribution_percentage.toFixed(2)}%</strong>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
