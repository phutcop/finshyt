function AboutPage() {
  return (
    <>
      <style>{`
        .about-header {
          padding: 5rem 4rem 4rem;
          border-bottom: 1px solid var(--ink);
        }
        .about-grid {
          display: flex;
          flex-direction: row;
        }
        .about-col {
          flex: 1;
          padding: 4rem;
          display: flex;
          flex-direction: column;
          gap: 2rem;
        }
        .about-col:first-child {
          border-right: 1px solid var(--ink);
        }
        @media (max-width: 860px) {
          .about-header {
            padding: 3rem 1.5rem 2rem;
          }
          .about-grid {
            flex-direction: column;
          }
          .about-col {
            padding: 2.5rem 1.5rem;
          }
          .about-col:first-child {
            border-right: none;
            border-bottom: 1px solid var(--ink);
          }
        }
      `}</style>
      <div style={{ padding: 0, minHeight: "100vh", display: "flex", flexDirection: "column" }}>
        {/* HEADER SECTION */}
        <section className="about-header">
          <h1 className="display-title" style={{ 
            fontSize: "clamp(3rem, 7vw, 6rem)", 
            lineHeight: 0.95, 
            margin: 0,
            maxWidth: "1200px",
            textTransform: "uppercase",
            wordBreak: "break-word"
          }}>
            Built for founders to focus on building rather than budgeting.
          </h1>
        </section>

        {/* CONTENT GRID */}
        <section className="about-grid" style={{ flex: 1 }}>
          <div className="about-col">
            <h2 style={{ fontFamily: "var(--font-display)", fontSize: "2rem", textTransform: "uppercase", color: "var(--text-muted)", margin: 0 }}>
              The Origin
            </h2>
            <p style={{ fontFamily: "var(--font-body)", fontSize: "1.1rem", lineHeight: 1.8, color: "var(--ink)", margin: 0 }}>
              It started with a late-night conversation about where our money was going. We had the transactions, but finding a clear answer meant digging through a spreadsheet. That conversation led us to build a simpler way to understand spending.
            </p>
          </div>
          
          <div className="about-col" style={{ backgroundColor: "rgba(33, 40, 66, 0.02)" }}>
            <h2 style={{ fontFamily: "var(--font-display)", fontSize: "2rem", textTransform: "uppercase", color: "var(--text-muted)", margin: 0 }}>
              The Founders
            </h2>
            <p style={{ fontFamily: "var(--font-body)", fontSize: "1.1rem", lineHeight: 1.8, color: "var(--ink)", margin: 0 }}>
              We are Yashraj, Heiley, Sahil, and Triza, the founders of finshyt. We built it to make expenses easier to understand, so founders can spend more time on what they are building.
            </p>
          </div>
        </section>
      </div>
    </>
  );
}

export default AboutPage;
