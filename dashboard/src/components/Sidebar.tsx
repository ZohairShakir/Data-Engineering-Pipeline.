import {
  Box,
  ChartNoAxesCombined,
  CircleUserRound,
  Database,
  House,
  Package,
} from "lucide-react";

const items = [
  { label: "Overview", href: "#top", icon: House },
  { label: "Revenue", href: "#revenue", icon: ChartNoAxesCombined },
  { label: "Products", href: "#products", icon: Package },
  { label: "Customers", href: "#customers", icon: CircleUserRound },
  { label: "Pipeline runs", href: "#pipeline-runs", icon: Database },
];

type SidebarProps = {
  active: string;
  onNavigate: (label: string) => void;
};

export function Sidebar({ active, onNavigate }: SidebarProps) {
  return (
    <aside className="sidebar" aria-label="Dashboard navigation">
      <a className="brand" href="#top" onClick={() => onNavigate("Overview")}>
        <span className="brand-mark" aria-hidden="true">
          <Box size={24} strokeWidth={2.1} />
        </span>
        <span>E-commerce<br />Pipeline</span>
      </a>
      <nav>
        {items.map(({ label, href, icon: Icon }) => (
          <a
            key={label}
            aria-label={label}
            className={active === label ? "nav-item active" : "nav-item"}
            href={href}
            onClick={() => onNavigate(label)}
            title={label}
          >
            <Icon size={20} strokeWidth={1.8} aria-hidden="true" />
            <span>{label}</span>
          </a>
        ))}
      </nav>
    </aside>
  );
}
