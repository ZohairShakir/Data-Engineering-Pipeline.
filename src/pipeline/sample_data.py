"""Generate deterministic, explicitly synthetic e-commerce source data."""

from __future__ import annotations

import csv
import json
import random
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

FIRST_NAMES = (
    "Aarav", "Aditi", "Amelia", "Arjun", "Daniel", "Elena", "Fatima", "Ishaan",
    "James", "Kavya", "Liam", "Maya", "Noah", "Olivia", "Priya", "Rohan",
    "Sara", "Sophia", "Vikram", "Zara",
)
LAST_NAMES = (
    "Brown", "Chen", "Garcia", "Gupta", "Johnson", "Khan", "Kim", "Kumar",
    "Lee", "Martin", "Mehta", "Miller", "Patel", "Rodriguez", "Shah", "Singh",
    "Smith", "Taylor", "Thomas", "Wilson",
)
LOCATIONS = (
    ("Bengaluru", "Karnataka", "IN"),
    ("Chennai", "Tamil Nadu", "IN"),
    ("Delhi", "Delhi", "IN"),
    ("Hyderabad", "Telangana", "IN"),
    ("Kolkata", "West Bengal", "IN"),
    ("Mumbai", "Maharashtra", "IN"),
    ("Pune", "Maharashtra", "IN"),
)
CATEGORIES = {
    "books": ("Novel", "Cookbook", "Biography", "Study Guide"),
    "electronics": ("Headphones", "Keyboard", "Power Bank", "Webcam"),
    "beauty": ("Face Wash", "Moisturizer", "Shampoo", "Sunscreen"),
    "home": ("Bedsheet", "Lamp", "Storage Box", "Water Bottle"),
    "sports": ("Cricket Bat", "Resistance Band", "Yoga Mat", "Football"),
    "toys": ("Building Blocks", "Puzzle", "Remote Car", "Strategy Game"),
}
PAYMENT_METHODS = ("card", "upi", "net_banking", "wallet", "cash_on_delivery")
GENERATOR_ID = "aws-ecommerce-etl.synthetic.v1"


@dataclass(frozen=True, slots=True)
class DatasetSummary:
    generator: str
    seed: int
    customers: int
    products: int
    orders: int
    order_items: int
    payments: int
    total_records: int
    order_status_counts: dict[str, int]
    generated_at: str


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows: Iterable[dict[str, object]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _prepare_output_directory(output_dir: Path) -> None:
    """Refresh only files owned by this generator, preserving unrelated files."""
    if not output_dir.exists():
        output_dir.mkdir(parents=True)
        return

    existing_entries = list(output_dir.iterdir())
    if not existing_entries:
        return

    manifest_path = output_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Refusing to replace non-empty unowned directory: {output_dir}"
        ) from exc
    if manifest.get("generator") != GENERATOR_ID:
        raise ValueError(f"Refusing to replace non-empty unowned directory: {output_dir}")

    owned_patterns = (
        "customers/customers.csv",
        "products/products.csv",
        "orders/orders_*.csv",
        "order_items/order_items_*.csv",
        "payments/payments_*.csv",
        "manifest.json",
    )
    for pattern in owned_patterns:
        for path in output_dir.glob(pattern):
            if path.is_file():
                path.unlink()


def generate_dataset(
    output_dir: Path,
    *,
    seed: int = 42,
    customer_count: int = 2_000,
    product_count: int = 500,
    order_count: int = 10_000,
) -> DatasetSummary:
    """Create a repeatable multi-file synthetic dataset under ``output_dir``."""
    if min(customer_count, product_count, order_count) <= 0:
        raise ValueError("customer, product, and order counts must all be positive")

    rng = random.Random(seed)
    _prepare_output_directory(output_dir)

    customer_rows: list[dict[str, object]] = []
    for number in range(1, customer_count + 1):
        first_name = rng.choice(FIRST_NAMES)
        last_name = rng.choice(LAST_NAMES)
        city, state, country = rng.choice(LOCATIONS)
        registered_at = datetime(2023, 1, 1, tzinfo=UTC) + timedelta(
            minutes=rng.randrange(0, 730 * 24 * 60)
        )
        customer_rows.append(
            {
                "customer_id": f"CUST{number:07d}",
                "first_name": first_name,
                "last_name": last_name,
                "email": f"{first_name.lower()}.{last_name.lower()}.{number}@example.com",
                "city": city,
                "state": state,
                "country_code": country,
                "registered_at": _timestamp(registered_at),
                "customer_status": rng.choices(
                    ("active", "inactive"), weights=(96, 4), k=1
                )[0],
            }
        )
    _write_csv(
        output_dir / "customers" / "customers.csv",
        tuple(customer_rows[0]),
        customer_rows,
    )

    product_rows: list[dict[str, object]] = []
    product_prices: dict[str, Decimal] = {}
    for number in range(1, product_count + 1):
        category = rng.choice(tuple(CATEGORIES))
        product_name = f"{rng.choice(CATEGORIES[category])} {number:03d}"
        price = Decimal(rng.randrange(199, 49_999)) / Decimal(100)
        product_id = f"PROD{number:06d}"
        product_prices[product_id] = price
        product_rows.append(
            {
                "product_id": product_id,
                "product_name": product_name,
                "category": category,
                "unit_price": _money(price),
                "is_active": str(rng.random() >= 0.03).lower(),
                "created_at": "2023-01-01T00:00:00Z",
            }
        )
    _write_csv(
        output_dir / "products" / "products.csv",
        tuple(product_rows[0]),
        product_rows,
    )

    partitioned_orders: dict[str, list[dict[str, object]]] = {}
    partitioned_items: dict[str, list[dict[str, object]]] = {}
    partitioned_payments: dict[str, list[dict[str, object]]] = {}
    statuses: Counter[str] = Counter()
    item_count = 0
    start = datetime(2025, 1, 1, tzinfo=UTC)
    product_ids = tuple(product_prices)

    for order_number in range(1, order_count + 1):
        order_id = f"ORD{order_number:08d}"
        customer_id = f"CUST{rng.randint(1, customer_count):07d}"
        ordered_at = start + timedelta(minutes=rng.randrange(0, 365 * 24 * 60))
        partition = ordered_at.strftime("%Y_%m")
        status = rng.choices(
            ("completed", "cancelled", "returned", "pending"),
            weights=(86, 6, 4, 4),
            k=1,
        )[0]
        statuses[status] += 1

        selected_products = rng.sample(product_ids, k=rng.randint(1, min(4, product_count)))
        total = Decimal("0.00")
        order_items: list[dict[str, object]] = []
        for line_number, product_id in enumerate(selected_products, start=1):
            quantity = rng.randint(1, 3)
            unit_price = product_prices[product_id]
            line_amount = unit_price * quantity
            total += line_amount
            item_count += 1
            order_items.append(
                {
                    "order_item_id": f"{order_id}-{line_number:02d}",
                    "order_id": order_id,
                    "product_id": product_id,
                    "quantity": quantity,
                    "unit_price": _money(unit_price),
                    "line_amount": _money(line_amount),
                }
            )

        partitioned_items.setdefault(partition, []).extend(order_items)
        partitioned_orders.setdefault(partition, []).append(
            {
                "order_id": order_id,
                "customer_id": customer_id,
                "ordered_at": _timestamp(ordered_at),
                "order_status": status,
                "order_total": _money(total),
                "currency": "INR",
            }
        )

        payment_status = {
            "completed": "paid",
            "cancelled": "voided",
            "returned": "refunded",
            "pending": "pending",
        }[status]
        paid_at = ordered_at + timedelta(minutes=rng.randint(1, 20))
        partitioned_payments.setdefault(partition, []).append(
            {
                "payment_id": f"PAY{order_number:08d}",
                "order_id": order_id,
                "payment_method": rng.choice(PAYMENT_METHODS),
                "payment_status": payment_status,
                "payment_amount": _money(
                    total if status in {"completed", "returned"} else Decimal(0)
                ),
                "paid_at": _timestamp(paid_at) if status in {"completed", "returned"} else "",
            }
        )

    for partition in sorted(partitioned_orders):
        _write_csv(
            output_dir / "orders" / f"orders_{partition}.csv",
            tuple(partitioned_orders[partition][0]),
            partitioned_orders[partition],
        )
        _write_csv(
            output_dir / "order_items" / f"order_items_{partition}.csv",
            tuple(partitioned_items[partition][0]),
            partitioned_items[partition],
        )
        _write_csv(
            output_dir / "payments" / f"payments_{partition}.csv",
            tuple(partitioned_payments[partition][0]),
            partitioned_payments[partition],
        )

    summary = DatasetSummary(
        generator=GENERATOR_ID,
        seed=seed,
        customers=customer_count,
        products=product_count,
        orders=order_count,
        order_items=item_count,
        payments=order_count,
        total_records=customer_count + product_count + order_count + item_count + order_count,
        order_status_counts=dict(sorted(statuses.items())),
        generated_at="deterministic-from-seed",
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(asdict(summary), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary
