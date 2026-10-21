import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { compactCurrency } from "../format";
import type { MonthlyRevenue } from "../types";

const monthLabel = (month: string) =>
  new Intl.DateTimeFormat("en", { month: "short", timeZone: "UTC" }).format(
    new Date(`${month}-01T00:00:00Z`),
  );

function chartScale(values: number[]) {
  const dataMin = Math.min(...values);
  const dataMax = Math.max(...values);
  const roughStep = Math.max((dataMax - dataMin) / 4, 1);
  const magnitude = 10 ** Math.floor(Math.log10(roughStep));
  const normalized = roughStep / magnitude;
  const niceFactor = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  const step = niceFactor * magnitude;
  const minimum = Math.floor(dataMin / step) * step;
  const maximum = Math.ceil(dataMax / step) * step;
  return {
    domain: [minimum, maximum] as [number, number],
    ticks: Array.from(
      { length: Math.round((maximum - minimum) / step) + 1 },
      (_, index) => minimum + index * step,
    ),
  };
}

export function RevenueChart({ data }: { data: MonthlyRevenue[] }) {
  const scale = chartScale(data.map((point) => point.revenue));

  return (
    <section className="panel revenue-panel" id="revenue">
      <h2>Revenue over time</h2>
      <div className="chart-wrap" aria-label="Monthly revenue line chart">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 22, right: 12, bottom: 0, left: 8 }}>
            <defs>
              <linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#1670eb" stopOpacity={0.18} />
                <stop offset="100%" stopColor="#1670eb" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#dce5f0" strokeDasharray="3 3" vertical />
            <XAxis
              dataKey="month"
              tickFormatter={monthLabel}
              axisLine={{ stroke: "#c8d4e2" }}
              tickLine={false}
              tick={{ fill: "#526585", fontSize: 12 }}
              dy={10}
            />
            <YAxis
              domain={scale.domain}
              ticks={scale.ticks}
              tickFormatter={(value: number) => compactCurrency(value).replace(".00", "")}
              axisLine={false}
              tickLine={false}
              tick={{ fill: "#526585", fontSize: 12 }}
              width={66}
              tickCount={5}
            />
            <Tooltip
              cursor={{ stroke: "#6f86a6", strokeDasharray: "4 4" }}
              content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null;
                return (
                  <div className="chart-tooltip">
                    <span>{monthLabel(String(label))}</span>
                    <strong>{compactCurrency(Number(payload[0].value))}</strong>
                  </div>
                );
              }}
            />
            <Area
              type="monotone"
              dataKey="revenue"
              stroke="#1267e8"
              strokeWidth={2.5}
              fill="url(#revenueFill)"
              dot={{ r: 4, fill: "#1267e8", stroke: "#ffffff", strokeWidth: 2 }}
              activeDot={{ r: 6, stroke: "#ffffff", strokeWidth: 3 }}
              animationDuration={550}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
