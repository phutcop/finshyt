import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import ExpenseTrendChart from "../components/charts/ExpenseTrendChart";
import CategoryPieChart from "../components/charts/CategoryPieChart";
import { DownloadIcon } from "../components/Icons";
import { apiFetch } from "../api";
import "./dashboard.css";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const CATEGORY_COLORS = [
  "var(--ledger-category-1)", "var(--ledger-category-2)", "var(--ledger-category-3)",
  "var(--ledger-category-4)", "var(--ledger-category-5)", "var(--ledger-category-6)",
];
const monthName = (month) => MONTHS[Number(String(month).slice(5, 7)) - 1] || month;
const formatMoney = (amount) => {
  const value = Number(amount) || 0;
  return (value < 0 ? "-$" : "$") + Math.abs(value).toLocaleString("en-US", {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  });
};
const formatCompactMoney = (amount) => "$" + new Intl.NumberFormat("en-US", {
  notation: "compact", maximumFractionDigits: 1,
}).format(Number(amount) || 0);

function DashboardPage() {
  const [summaryData, setSummaryData] = useState(null);
  const [selectedYear, setSelectedYear] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    apiFetch("/api/intel/years")
      .then((response) => {
        if (!response.ok) throw new Error("Year list unavailable");
        return response.json();
      })
      .then((data) => {
        const years = data.years || [];
        if (years.length) setSelectedYear(years.at(-1));
        else {
          setError("No expense data is available yet. Import an annual file first.");
          setLoading(false);
        }
      })
      .catch(() => {
        setError("The dashboard could not reach the data service. Please try again shortly.");
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!selectedYear) return;
    let active = true;
    localStorage.setItem("finshyt:selectedYear", String(selectedYear));
    setLoading(true);
    setError(null);
    async function fetchData() {
      try {
        const query = "?year=" + selectedYear;
        const responses = await Promise.all([
          apiFetch("/api/intel/summary" + query),
          apiFetch("/api/intel/trend" + query),
          apiFetch("/api/intel/departments" + query),
          apiFetch("/api/intel/categories" + query),
          apiFetch("/api/intel/comparison" + query),
        ]);
        if (responses.some((response) => !response.ok)) throw new Error("Dashboard data unavailable");
        const [summary, trend, departments, categories, comparison] = await Promise.all(
          responses.map((response) => response.json())
        );
        if (active) setSummaryData({
          summary,
          trend: (trend.data || []).map((row) => ({ month: row.month, expense: row.total })),
          departments: (departments.data || []).map((row) => ({
            department: row.department, spend: row.total,
          })),
          categories: (categories.data || []).map((row, index) => ({
            name: row.category, value: row.total, color: CATEGORY_COLORS[index % CATEGORY_COLORS.length],
          })),
          comparison: comparison.data || [],
          comparisonYear: comparison.year,
        });
      } catch (err) {
        console.error("Dashboard API unavailable:", err);
        if (active) setError("The dashboard could not load its data. Please try again shortly.");
      } finally {
        if (active) setLoading(false);
      }
    }
    fetchData();
    return () => { active = false; };
  }, [selectedYear]);

  if (loading) return <div className="page ledger ledger-state">Preparing your ledger...</div>;
  if (error || !summaryData) {
    return <div className="page ledger ledger-state" role="alert">{error || "No dashboard data is available."}</div>;
  }

  const { summary, trend, departments, categories, comparison, comparisonYear } = summaryData;
  const latestMonth = summary.month || trend.at(-1)?.month;
  const annualTotal = trend.reduce((total, row) => total + row.expense, 0);
  const maxMonthSpend = Math.max(...trend.map((row) => row.expense), 1);
  const maxDepartment = departments[0]?.spend || 1;
  const change = summary.change_pct;
  const categoryMix = categories.slice(0, 5);
  const otherTotal = categories.slice(5).reduce((total, row) => total + row.value, 0);
  if (otherTotal > 0) categoryMix.push({ name: "Other", value: otherTotal, color: CATEGORY_COLORS[5] });

  const downloadComparison = () => {
    const header = ["Month", "Expenses", "Previous month", "Change", "Change %"];
    const rows = comparison.map((row) => [
      row.month, row.total, row.previous_month_total ?? "", row.change ?? "", row.change_pct ?? "",
    ]);
    const csv = [header, ...rows].map((row) => row.join(",")).join("\n") + "\n";
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "finshyt-month-comparison-" + comparisonYear + ".csv";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return (
    <div className="page ledger">
      <header className="ledger-heading">
        <div>
          <h1 className="display-title">The Ledger<span className="ledger-title-dot">.</span></h1>
          <p>Your year of spending, month by month.</p>
        </div>
        <span className="ledger-year-badge"><span className="ledger-year-dot" /> Active year {selectedYear}</span>
      </header>

      <section className="ledger-hero" aria-label="Latest month overview">
        <div className="ledger-hero-art" aria-hidden="true" />
        <div className="ledger-hero-top">
          <span>LATEST MONTH</span>
          <span>{String(latestMonth).replace("-", " / ")}</span>
        </div>
        <div className="ledger-hero-main">
          <div>
            <span className="ledger-hero-overline">Monthly spend</span>
            <strong className="ledger-hero-value">{formatMoney(summary.total_spend)}</strong>
            <p className="ledger-hero-month">{monthName(latestMonth)} {selectedYear}</p>
          </div>
          <div className="ledger-hero-change">
            <span className="ledger-hero-change-icon" aria-hidden="true">{change == null ? "·" : change >= 0 ? "↗" : "↘"}</span>
            <strong>{change == null ? "First recorded month" : (change > 0 ? "+" : "") + change + "%"}</strong>
            <span>{summary.prev_month ? "compared with " + monthName(summary.prev_month) : "No prior month in this file"}</span>
          </div>
        </div>
        <div className="ledger-hero-footer">
          <span>Calculated from your confirmed expense file.</span>
          <Link to="/advisor">Ask the ledger <span aria-hidden="true">↗</span></Link>
        </div>
      </section>

      <section className="ledger-year-summary" aria-label="Year overview">
        <div className="ledger-annual-card">
          <div className="ledger-annual-top">
            <span>Yearly spending</span>
            <span>{selectedYear}</span>
          </div>
          <strong className="ledger-annual-value">{formatMoney(annualTotal)}</strong>
          <div className="ledger-annual-bottom">
            <span>Across {trend.length} recorded {trend.length === 1 ? "month" : "months"}</span>
            <div className="ledger-annual-spark">
              <span>Monthly totals</span>
              <div className="ledger-annual-bars" role="img" aria-label={"Monthly expense totals from " + monthName(trend[0]?.month) + " to " + monthName(trend.at(-1)?.month) + "; dark bar is the latest month"}>
                {trend.map((row) => (
                  <span
                    key={row.month}
                    title={monthName(row.month) + ": " + formatMoney(row.expense)}
                    style={{ height: Math.max(8, row.expense / maxMonthSpend * 100) + "%" }}
                  />
                ))}
              </div>
              <div className="ledger-annual-spark-months">
                <span>{monthName(trend[0]?.month).slice(0, 3)}</span>
                <span>{monthName(trend.at(-1)?.month).slice(0, 3)}</span>
              </div>
            </div>
          </div>
        </div>
        <div className="ledger-year-facts">
          <div className="ledger-year-fact">
            <span>Months on record</span>
            <strong>{trend.length}<em> / 12</em></strong>
            <small>In this expense file</small>
          </div>
          <div className="ledger-year-fact">
            <span>Departments</span>
            <strong>{departments.length}</strong>
            <small>With recorded spending</small>
          </div>
        </div>
      </section>

      <section className="ledger-section ledger-trend-section">
        <div className="ledger-section-heading">
          <div><h2>Monthly spending</h2></div>
          <p>Expense totals for {selectedYear}</p>
        </div>
        <div className="ledger-chart-surface"><ExpenseTrendChart data={trend} /></div>
      </section>

      <section className="ledger-breakdown-grid" aria-label="Spending breakdown">
        <div className="ledger-section ledger-department-section">
          <div className="ledger-section-heading">
            <div><h2>By department</h2></div>
          </div>
          <div className="ledger-department-list">
            {departments.map((row, index) => (
              <div className="ledger-department-row" key={row.department}>
                <div className="ledger-department-line">
                  <span><b>{String(index + 1).padStart(2, "0")}</b>{row.department}</span>
                  <strong>{formatCompactMoney(row.spend)}</strong>
                </div>
                <div className="ledger-bar-track" aria-hidden="true">
                  <span style={{ width: (row.spend / maxDepartment * 100) + "%" }} />
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="ledger-section ledger-category-section">
          <div className="ledger-section-heading">
            <div><h2>By category</h2></div>
          </div>
          <CategoryPieChart data={categoryMix} />
        </div>
      </section>

      <section className="ledger-section ledger-comparison-section">
        <div className="ledger-section-heading ledger-table-heading">
          <div>
            <h2>Monthly comparison</h2>
            <p>Each month compared with the one before it.</p>
          </div>
          <button type="button" className="ledger-download" onClick={downloadComparison} disabled={!comparison.length}>
            <DownloadIcon width={17} height={17} /> Download CSV
          </button>
        </div>
        {comparison.length ? (
          <>
          <p className="ledger-table-swipe">Swipe sideways to view every column.</p>
          <div className="ledger-table-scroll">
            <table className="ledger-table" aria-label={"Monthly expense comparison for " + comparisonYear}>
              <thead><tr>
                <th scope="col">Month</th><th scope="col">Spend</th><th scope="col">Previous</th>
                <th scope="col">Difference</th><th scope="col">Change</th>
              </tr></thead>
              <tbody>
                {comparison.map((row, index) => (
                  <tr key={row.month} className={index === comparison.length - 1 ? "is-latest" : ""}>
                    <td><span className="ledger-table-month">{monthName(row.month)}</span><small>{row.month}</small></td>
                    <td className="ledger-table-amount">{formatMoney(row.total)}</td>
                    <td>{row.previous_month_total == null ? "–" : formatMoney(row.previous_month_total)}</td>
                    <td>{row.change == null ? "–" : (row.change > 0 ? "+" : "") + formatMoney(row.change)}</td>
                    <td>{row.change_pct == null ? <span className="ledger-change-pill neutral">First month</span> :
                      <span className={"ledger-change-pill " + (row.change_pct > 0 ? "up" : row.change_pct < 0 ? "down" : "neutral")}>
                        {row.change_pct > 0 ? "+" : ""}{row.change_pct}%
                      </span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          </>
        ) : <p className="muted">Import an annual expense file to see monthly comparisons.</p>}
      </section>

      <footer className="ledger-footer">
        <span>Built from your latest confirmed upload.</span>
        <Link to="/upload">Replace annual file <span aria-hidden="true">↗</span></Link>
      </footer>
    </div>
  );
}

export default DashboardPage;
