import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

const money = (value) => "$" + Number(value).toLocaleString("en-US", {
  minimumFractionDigits: 2, maximumFractionDigits: 2,
});

function CategoryPieChart({ data = [] }) {
  const total = data.reduce((sum, row) => sum + row.value, 0);
  const topShare = total ? Math.round(data[0].value / total * 100) : 0;

  return (
    <div className="ledger-category-layout">
      <div className="ledger-donut-wrap" role="img" aria-label="Donut chart of expense categories">
        <ResponsiveContainer width="100%" height={245}>
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius={68}
              outerRadius={96}
              paddingAngle={2}
              stroke="none"
            >
              {data.map((entry) => <Cell key={entry.name} fill={entry.color} />)}
            </Pie>
            <Tooltip
              formatter={(value, name) => [money(value), name]}
              contentStyle={{
                background: "var(--ledger-surface)",
                border: "1px solid var(--ledger-line)",
                borderRadius: 12,
                color: "var(--ink)",
                fontSize: 12,
                boxShadow: "0 12px 30px rgba(33,40,66,0.12)",
              }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="ledger-donut-center"><strong>{topShare}%</strong><span>top category</span></div>
      </div>
      <ul className="ledger-category-list">
        {data.map((entry) => (
          <li key={entry.name}>
            <span className="ledger-category-dot" style={{ background: entry.color }} />
            <span title={entry.name}>{entry.name}</span>
            <strong>{total ? Math.round(entry.value / total * 100) : 0}%</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default CategoryPieChart;
