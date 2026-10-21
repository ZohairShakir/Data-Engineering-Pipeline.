import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import type { AnalyticsPayload } from "./types";

const payload: AnalyticsPayload = {
  metadata: {
    generated_at: "2026-10-21T00:00:00Z",
    dataset: "deterministic synthetic e-commerce data",
    fact_rows: 25122,
  },
  results: {
    total_revenue_by_month: [{ month: "2025-01", revenue: 900000, order_count: 1000 }],
    top_products_by_revenue: [],
    highest_value_customers: [
      { customer_id: "C1", customer_name: "Kavya Patel", order_count: 10, lifetime_value: 17733.95 },
    ],
    average_order_value: [{ average_order_value: 1104.31, included_orders: 9041 }],
    category_performance: [],
    revenue_change_over_time: [],
    cancelled_order_percentage: [
      { total_orders: 10000, cancelled_orders: 594, cancelled_order_percentage: 5.94 },
    ],
    repeat_customers: [],
    category_revenue_contribution: [
      { category: "electronics", revenue: 1870998.42, contribution_percentage: 18.74 },
    ],
    orders_processed_per_day: [],
  },
  dashboard: {
    category_monthly: [
      { category: "electronics", month: "2025-01", revenue: 180000, order_count: 250 },
    ],
    category_metrics: [
      {
        category: "electronics",
        net_revenue: 1870998.42,
        order_count: 4045,
        average_order_value: 520.5,
        cancelled_order_percentage: 5.5,
      },
    ],
    product_performance: [
      { product_id: "P1", product_name: "Webcam 001", category: "electronics", revenue: 50000, units: 120 },
    ],
    pipeline_status: [
      {
        run_id: 1,
        batch_id: "run-1",
        status: "succeeded",
        rows_read: 47622,
        rows_loaded: 25122,
        rows_rejected: 0,
        started_at: "2026-10-21T00:00:00Z",
        completed_at: "2026-10-21T00:01:00Z",
      },
    ],
  },
};

afterEach(() => vi.unstubAllGlobals());

describe("dashboard", () => {
  it("renders verified metrics and applies category filtering", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => payload }));
    render(<App />);

    expect(await screen.findByText("Commerce overview")).toBeInTheDocument();
    expect(screen.getByText("₹900.00K")).toBeInTheDocument();
    expect(screen.getByText("25,122 fact rows")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "electronics" } });
    await waitFor(() => expect(screen.getByText("₹1.87M")).toBeInTheDocument());
    expect(screen.getByText("Webcam 001")).toBeInTheDocument();
  });
});
