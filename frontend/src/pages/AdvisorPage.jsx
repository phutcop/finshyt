import { useState, useEffect } from "react";
import { DownloadIcon } from "../components/Icons";
import { apiFetch } from "../api";
import "./advisor.css";

function AdvisorPage() {
  const [selectedYear, setSelectedYear] = useState(null);
  const [operationText, setOperationText] = useState("");
  const [chatResponse, setChatResponse] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [insights, setInsights] = useState(null);
  const [insightMonth, setInsightMonth] = useState(null);
  const [showAllWarnings, setShowAllWarnings] = useState(false);

  useEffect(() => {
    apiFetch("/api/intel/years")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP error ${res.status}`);
        return res.json();
      })
      .then((data) => {
        const years = data.years || [];
        setSelectedYear(years.at(-1) ?? null);
      })
      .catch(() => setSelectedYear(null));
  }, []);

  useEffect(() => {
    if (selectedYear) localStorage.setItem("finshyt:selectedYear", String(selectedYear));
  }, [selectedYear]);

  useEffect(() => {
    if (!selectedYear) return;
    let active = true;
    setInsights(null);
    setChatResponse(null);
    setShowAllWarnings(false);
    apiFetch(`/api/intel/insights${selectedYear ? `?year=${selectedYear}` : ""}`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP error ${res.status}`);
        return res.json();
      })
      .then(data => {
        if (active) {
          setInsights(data?.warnings || []);
          setInsightMonth(data?.month || null);
        }
      })
      .catch(err => {
        console.warn("Could not load insights:", err);
        if (active) setInsights([]);
      });
    return () => { active = false; };
  }, [selectedYear]);

  const handleGetInsights = async () => {
    if (!operationText.trim()) return;
    setIsLoading(true);
    setChatResponse(null);
    try {
      const res = await apiFetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: operationText, year: selectedYear })
      });
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const data = await res.json();
      setChatResponse(data);
    } catch (err) {
      console.warn("Chatbot request failed:", err);
      setChatResponse({
        answer: "The advisor could not reach the data service. Please try again shortly.",
        type: "error"
      });
    } finally {
      setIsLoading(false);
    }
  };

  const downloadInsights = () => {
    const warningLines = insights?.length
      ? insights.map((warning, index) => `${index + 1}. ${warning.narrative}`).join("\n")
      : "No warnings were found for the selected period.";
    const contents = [
      "finshyt expense insights",
      `Period: ${insightMonth || selectedYear || "latest recorded year"}`,
      "",
      "Warnings",
      warningLines,
      "",
      "Advisor question",
      operationText || "No question asked.",
      "Advisor answer",
      chatResponse?.answer || "No answer requested.",
      "",
    ].join("\n");
    const url = URL.createObjectURL(new Blob([contents], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `finshyt-insights-${insightMonth || selectedYear || "latest"}.txt`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return (
    <div className="page advisor-page">
      <div className="advisor-heading">
        <div>
          <h1 className="display-title">
            The Oracle.
          </h1>
          <p className="muted">Questions about your {selectedYear || "latest"} expense file</p>
        </div>
      </div>

      {/* ---------- AI INSIGHTS / WARNINGS ---------- */}
      <div className="advisor-top-grid">
        {insights?.length > 0 && (
          <div className="advisor-warning-heading">
            <h2>Spending changes in {insightMonth || selectedYear}</h2>
            <span>{insights.length} {insights.length === 1 ? "finding" : "findings"}</span>
          </div>
        )}
        {insights?.length ? insights.slice(0, showAllWarnings ? undefined : 2).map((warning, idx) => (
          <div key={idx} className={"advisor-warning " + (warning.severity === "high" ? "is-high" : "is-medium")}>
            <div className="card-label" style={{ marginBottom: "0.5rem" }}>
              {warning.type.replace(/_/g, ' ').toUpperCase()} • {warning.department || warning.category}
            </div>
            <div style={{ fontSize: "0.95rem", lineHeight: 1.5, color: "var(--ink)", marginBottom: "0.8rem" }}>
              {warning.narrative}
            </div>
            <div className="muted" style={{ fontSize: "0.85rem", display: "flex", gap: "1rem" }}>
              {warning.evidence?.excess_over_typical && (
                <span>Excess: ${warning.evidence.excess_over_typical.toLocaleString()}</span>
              )}
              {warning.evidence?.streak_length && (
                <span>Streak: {warning.evidence.streak_length} months</span>
              )}
            </div>
          </div>
        )) : (
          <div className="advisor-empty">{insights ? "No unusual spending found for the latest month." : "Checking the latest month..."}</div>
        )}
        {insights?.length > 2 && (
          <button type="button" className="advisor-warning-toggle" onClick={() => setShowAllWarnings(!showAllWarnings)}>
            {showAllWarnings ? "Show fewer findings" : "Show all " + insights.length + " findings"}
          </button>
        )}
      </div>

      {/* ---------- ASK ABOUT RECORDED EXPENSES ---------- */}
      <div className="advisor-question-card">
        <div className="card-label" style={{ marginBottom: "0.9rem" }}>
          Ask your expense question
        </div>
        <textarea
          value={operationText}
          onChange={(e) => setOperationText(e.target.value)}
          placeholder="Type a question about the active expense ledger"
          aria-label="Ask a question about your expense file"
          rows={4}
          className="advisor-textarea"
        />
        <button type="button" className="btn btn-solid" onClick={handleGetInsights} disabled={isLoading || !selectedYear}>
          {isLoading ? "Checking ledger..." : "Get answer"}
        </button>

        {chatResponse && (
          <div className="advisor-answer" role="status">
            {chatResponse.answer}
          </div>
        )}
      </div>

      {/* ---------- FOOTER ACTION BAR ---------- */}
      <div className="advisor-footer">
        <div className="muted" style={{ fontSize: "0.88rem" }}>
          Answers use your confirmed expense file.
        </div>
        <button type="button" className="btn btn-solid" onClick={downloadInsights}>
          <DownloadIcon width={16} height={16} />
          Download insights
        </button>
      </div>

    </div>
  );
}

export default AdvisorPage;
