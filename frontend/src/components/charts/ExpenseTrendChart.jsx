import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const monthShort = (value) => MONTHS[Number(String(value).slice(5, 7)) - 1] || value;
const money = (value) => "$" + Number(value).toLocaleString("en-US", {
  minimumFractionDigits: 2, maximumFractionDigits: 2,
});
const compact = (value) => "$" + new Intl.NumberFormat("en-US", {
  notation: "compact", maximumFractionDigits: 1,
}).format(value);

function ExpenseTrendChart({ data = [] }) {
  return (
    <div role="img" aria-label="Line chart of monthly expense totals">
      <ResponsiveContainer width="100%" height={290}>
        <AreaChart data={data} margin={{ top: 16, right: 18, left: 2, bottom: 4 }}>
          <defs>
            <linearGradient id="ledgerAreaFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#69799f" stopOpacity={0.25} />
              <stop offset="100%" stopColor="#69799f" stopOpacity={0.015} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="var(--ledger-line)" strokeDasharray="3 6" />
          <XAxis
            dataKey="month"
            tickFormatter={monthShort}
            tick={{ fontSize: 11, fill: "#777e8e" }}
            tickLine={false}
            axisLine={false}
            dy={8}
          />
          <YAxis
            tickFormatter={compact}
            tick={{ fontSize: 11, fill: "#777e8e" }}
            tickLine={false}
            axisLine={false}
            width={55}
          />
          <Tooltip
            labelFormatter={(value) => monthShort(value) + " " + String(value).slice(0, 4)}
            formatter={(value) => [money(value), "Expenses"]}
            contentStyle={{
              background: "var(--ledger-surface)",
              border: "1px solid var(--ledger-line)",
              borderRadius: 12,
              color: "var(--ink)",
              fontSize: 12,
              boxShadow: "0 12px 30px rgba(33,40,66,0.12)",
            }}
          />
          <Area
            type="monotone"
            dataKey="expense"
            stroke="var(--ink)"
            strokeWidth={3}
            fill="url(#ledgerAreaFill)"
            dot={{ r: 3, fill: "var(--ink)", stroke: "var(--ledger-surface)", strokeWidth: 2 }}
            activeDot={{ r: 6, fill: "var(--ledger-gold)", stroke: "var(--ledger-surface)", strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export default ExpenseTrendChart;
