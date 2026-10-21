type Metric = {
  label: string;
  value: string;
  tone?: "primary" | "danger";
};

export function KpiStrip({ metrics }: { metrics: Metric[] }) {
  return (
    <section className="kpi-strip" aria-label="Key performance indicators">
      {metrics.map((metric) => (
        <div className="kpi" key={metric.label}>
          <strong className={metric.tone === "danger" ? "danger" : "primary"}>
            {metric.value}
          </strong>
          <span>{metric.label}</span>
        </div>
      ))}
    </section>
  );
}
