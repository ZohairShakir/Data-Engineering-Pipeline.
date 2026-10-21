import { AlertTriangle, CheckCircle2, Database, LoaderCircle } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";

import { CustomerTable } from "./components/CustomerTable";
import { KpiStrip } from "./components/KpiStrip";
import { PipelineRuns } from "./components/PipelineRuns";
import { ProductTable } from "./components/ProductTable";
import { Sidebar } from "./components/Sidebar";
import { categoryLabel, compactCurrency, currency, integer } from "./format";
import type { AnalyticsPayload } from "./types";

const RevenueChart = lazy(() =>
  import("./components/RevenueChart").then((module) => ({ default: module.RevenueChart })),
);
const CategoryDonut = lazy(() =>
  import("./components/CategoryDonut").then((module) => ({ default: module.CategoryDonut })),
);

export default function App() {
  const [data, setData] = useState<AnalyticsPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [category, setCategory] = useState("all");
  const [activeNav, setActiveNav] = useState("Overview");

  useEffect(() => {
    fetch("/analytics.json")
      .then((response) => {
        if (!response.ok) throw new Error(`Analytics request failed: ${response.status}`);
        return response.json() as Promise<AnalyticsPayload>;
      })
      .then(setData)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Unable to load analytics"));
  }, []);

  const view = useMemo(() => {
    if (!data) return null;
    const globalCancellation = data.results.cancelled_order_percentage[0];
    const globalAov = data.results.average_order_value[0];
    const globalRevenue = data.results.total_revenue_by_month.reduce(
      (total, row) => total + row.revenue,
      0,
    );
    const selected = data.dashboard.category_metrics.find((row) => row.category === category);
    const monthly = category === "all"
      ? data.results.total_revenue_by_month
      : data.dashboard.category_monthly.filter((row) => row.category === category);
    const products = category === "all"
      ? data.dashboard.product_performance
      : data.dashboard.product_performance.filter((row) => row.category === category);
    return {
      monthly,
      products,
      metrics: [
        {
          label: "Net revenue",
          value: compactCurrency(selected?.net_revenue ?? globalRevenue),
        },
        {
          label: "Orders",
          value: integer(selected?.order_count ?? globalCancellation.total_orders),
        },
        {
          label: "Average order value",
          value: currency(selected?.average_order_value ?? globalAov.average_order_value),
        },
        {
          label: "Cancelled",
          value: `${(selected?.cancelled_order_percentage ?? globalCancellation.cancelled_order_percentage).toFixed(2)}%`,
          tone: "danger" as const,
        },
      ],
    };
  }, [category, data]);

  if (error) {
    return <main className="state-screen"><AlertTriangle /><h1>Dashboard unavailable</h1><p>{error}</p></main>;
  }
  if (!data || !view) {
    return <main className="state-screen"><LoaderCircle className="spin" /><h1>Loading analytics</h1></main>;
  }

  const latestRun = data.dashboard.pipeline_status[0];
  const runLabel = latestRun ? `Last run ${latestRun.status.replace("_", " ")}` : "No pipeline run";
  const isHealthy = latestRun?.status === "succeeded" || latestRun?.status === "skipped";
  const categories = data.results.category_revenue_contribution.map((row) => row.category);

  return (
    <div className="app-shell" id="top">
      <Sidebar active={activeNav} onNavigate={setActiveNav} />
      <main className="main-content">
        <div className="status-bar" aria-label="Pipeline status">
          <span className={isHealthy ? "healthy" : "unhealthy"}>
            <CheckCircle2 size={16} />{runLabel}
          </span>
          <span><Database size={17} />{integer(data.metadata.fact_rows)} fact rows</span>
          <span><AlertTriangle size={17} />{integer(latestRun?.rows_rejected ?? 0)} rejected</span>
        </div>

        <header className="page-header">
          <div><h1>Commerce overview</h1><p>Verified synthetic dataset · 2025</p></div>
          <div className="filters">
            <label><span className="sr-only">Year</span><select value="2025" disabled><option>2025</option></select></label>
            <label>
              <span className="sr-only">Category</span>
              <select value={category} onChange={(event) => setCategory(event.target.value)}>
                <option value="all">All categories</option>
                {categories.map((value) => <option key={value} value={value}>{categoryLabel(value)}</option>)}
              </select>
            </label>
          </div>
        </header>

        <KpiStrip metrics={view.metrics} />
        <div className="analytics-grid">
          <Suspense fallback={<div className="panel chart-loading">Loading revenue chart…</div>}>
            <RevenueChart data={view.monthly} />
          </Suspense>
          <Suspense fallback={<div className="panel chart-loading">Loading category chart…</div>}>
            <CategoryDonut
              data={data.results.category_revenue_contribution}
              selectedCategory={category}
              onSelect={setCategory}
            />
          </Suspense>
        </div>
        <ProductTable rows={view.products} />
        <CustomerTable rows={data.results.highest_value_customers} />
        <PipelineRuns rows={data.dashboard.pipeline_status} />
        <footer>
          Generated from PostgreSQL analytics · {new Date(data.metadata.generated_at).toLocaleString()}
        </footer>
      </main>
    </div>
  );
}
