import { useState } from "react";
import { Link } from "react-router-dom";
import "./landing.css";

const steps = [
  { id: "UPLOAD", desc: "A raw CSV or ledger export. That's all the system needs to begin." },
  { id: "PARSE", desc: "The engine categorizes, maps, and normalizes thousands of rows instantly." },
  { id: "VISUALIZE", desc: "Live, interactive dashboards appear immediately, exposing hidden trends." },
  { id: "ACT", desc: "Get specific, ruthless guidance from the AI advisor on where to cut." },
];

function LandingPage() {
  const [hoveredStep, setHoveredStep] = useState(null);
  return (
    <div className="home-page">
      <section className="home-hero">
        <div className="home-hero-copy">
          <h1 className="display-title">Know your burn.<br />Protect your cash.</h1>
          <p>
            Upload your raw ledger and gain immediate visibility into your capital flow. No complex modeling required.
          </p>
          <div className="home-actions">
            <Link to="/upload" className="btn btn-solid">Upload your ledger</Link>
          </div>
        </div>
        <div className="home-hero-visual">
          <img src={`${import.meta.env.BASE_URL}hero-finance.png`} alt="Vintage cash counting machine on a desk" />
        </div>
      </section>

      <section className="home-process" aria-labelledby="home-process-title">
        <h2 id="home-process-title">Working</h2>
        <div className="home-workflow">
          {steps.map((step, index) => (
            <div className="home-workflow-item" key={step.id}>
              <button
                type="button"
                className={hoveredStep === step.id ? "is-active" : ""}
                onMouseEnter={() => setHoveredStep(step.id)}
                onMouseLeave={() => setHoveredStep(null)}
                onFocus={() => setHoveredStep(step.id)}
                onBlur={() => setHoveredStep(null)}
                onClick={() => setHoveredStep(hoveredStep === step.id ? null : step.id)}
                aria-describedby="home-workflow-description"
              >
                {step.id}
              </button>
              {index < steps.length - 1 && <span className="home-workflow-arrow" aria-hidden="true">▶</span>}
            </div>
          ))}
        </div>
        <p className="home-workflow-description" id="home-workflow-description" aria-live="polite">
          {hoveredStep ? steps.find((step) => step.id === hoveredStep)?.desc : "Hover a phase to inspect."}
        </p>
      </section>
    </div>
  );
}

export default LandingPage;
