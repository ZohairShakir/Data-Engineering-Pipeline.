import { CheckCircle2, CircleDashed, CircleX, SkipForward } from "lucide-react";

import { integer } from "../format";
import type { PipelineRun } from "../types";

const StatusIcon = ({ status }: { status: PipelineRun["status"] }) => {
  if (status === "succeeded" || status === "partially_succeeded") return <CheckCircle2 />;
  if (status === "failed") return <CircleX />;
  if (status === "skipped") return <SkipForward />;
  return <CircleDashed />;
};

export function PipelineRuns({ rows }: { rows: PipelineRun[] }) {
  return (
    <section className="table-panel secondary-table" id="pipeline-runs">
      <h2>Pipeline runs</h2>
      <div className="table-scroll">
        <table>
          <thead><tr><th>Status</th><th>Batch</th><th>Rows read</th><th>Facts loaded</th><th>Rejected</th></tr></thead>
          <tbody>
            {rows.slice(0, 8).map((row) => (
              <tr key={row.run_id}>
                <td><span className={`run-status ${row.status}`}><StatusIcon status={row.status} />{row.status.replace("_", " ")}</span></td>
                <td className="batch-id">{row.batch_id}</td>
                <td className="numeric">{integer(row.rows_read)}</td>
                <td className="numeric">{integer(row.rows_loaded)}</td>
                <td className="numeric">{integer(row.rows_rejected)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
