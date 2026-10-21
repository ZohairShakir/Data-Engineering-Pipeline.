export type MonthlyRevenue = {
  month: string;
  revenue: number;
  order_count: number;
};

export type ProductPerformance = {
  product_id: string;
  product_name: string;
  category: string;
  revenue: number;
  units: number;
};

export type CustomerValue = {
  customer_id: string;
  customer_name: string;
  order_count: number;
  lifetime_value: number;
};

export type CategoryContribution = {
  category: string;
  revenue: number;
  contribution_percentage: number;
};

export type CategoryMetric = {
  category: string;
  net_revenue: number;
  order_count: number;
  average_order_value: number;
  cancelled_order_percentage: number;
};

export type CategoryMonthly = MonthlyRevenue & { category: string };

export type PipelineRun = {
  run_id: number;
  batch_id: string;
  status: "running" | "succeeded" | "failed" | "partially_succeeded" | "skipped";
  rows_read: number;
  rows_loaded: number;
  rows_rejected: number;
  started_at: string;
  completed_at: string | null;
};

export type AnalyticsPayload = {
  metadata: {
    generated_at: string;
    dataset: string;
    fact_rows: number;
  };
  results: {
    total_revenue_by_month: MonthlyRevenue[];
    top_products_by_revenue: ProductPerformance[];
    highest_value_customers: CustomerValue[];
    average_order_value: Array<{
      average_order_value: number;
      included_orders: number;
    }>;
    category_performance: Array<{
      category: string;
      revenue: number;
      order_count: number;
      units: number;
    }>;
    revenue_change_over_time: Array<MonthlyRevenue & { month_over_month_pct: number | null }>;
    cancelled_order_percentage: Array<{
      total_orders: number;
      cancelled_orders: number;
      cancelled_order_percentage: number;
    }>;
    repeat_customers: Array<{
      customer_id: string;
      customer_name: string;
      order_count: number;
      revenue: number;
    }>;
    category_revenue_contribution: CategoryContribution[];
    orders_processed_per_day: Array<{
      order_date: string;
      order_count: number;
      revenue: number;
    }>;
  };
  dashboard: {
    category_monthly: CategoryMonthly[];
    category_metrics: CategoryMetric[];
    product_performance: ProductPerformance[];
    pipeline_status: PipelineRun[];
  };
};
