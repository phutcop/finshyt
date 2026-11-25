import { useState } from "react";
import { useNavigate } from "react-router-dom";
import UploadPanel from "../components/UploadPanel";
import { ArrowUpRight } from "../components/Icons";
import { apiFetch } from "../api";
import "./upload.css";

/* Upload → server-side validation/preview → explicit confirmation. */
function UploadFlowPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState("idle"); // idle | previewing | preview | confirming | ready
  const [fileName, setFileName] = useState(null);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState(null);

  const handleFileSelected = async (file) => {
    setFileName(file?.name ?? null);
    setError(null);
    setStatus("previewing");
    try {
      const form = new FormData();
      form.append("kind", "expenses");
      form.append("file", file);
      const response = await apiFetch("/api/imports/preview", { method: "POST", body: form });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "We could not preview this file.");
      setPreview(data);
      setStatus("preview");
    } catch (err) {
      setError(err instanceof TypeError
        ? "The upload service is unavailable. Please try again shortly."
        : err.message);
      setStatus("idle");
    }
  };

  const confirmImport = async () => {
    setStatus("confirming");
    try {
      const response = await apiFetch("/api/imports/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ import_id: preview.import_id }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "We could not save this import.");
      if (preview.year) localStorage.setItem("finshyt:selectedYear", String(preview.year));
      setPreview({ ...preview, result: data });
      setStatus("ready");
    } catch (err) {
      setError(err.message);
      setStatus("preview");
    }
  };

  const reset = () => {
    setFileName(null);
    setPreview(null);
    setError(null);
    setStatus("idle");
  };

  return (
    <div className="page upload-page">
      <div className="upload-inner">
        <h1 className="display-title upload-title">
          Upload your annual expense ledger.
        </h1>
        <p className="muted upload-subtitle">
          Use one expense file for one calendar year. We compare its monthly spending after import.
        </p>
        {import.meta.env.VITE_API_BASE_URL && (
          <p className="muted upload-subtitle">
            Public demo: use sample files only. Uploads are temporary and reset when the demo server restarts.
          </p>
        )}

        <div className="upload-surface">
          {status === "idle" && (
            <div style={{ width: "100%" }}>
              <UploadPanel onFileSelected={handleFileSelected} />
              {error && <p role="alert" style={{ color: "#b42318", marginTop: "1rem", fontSize: "0.9rem" }}>{error}</p>}
            </div>
          )}

          {status === "previewing" && (
            <div className="upload-status">
              <div className="upload-spinner" aria-hidden="true" />
              <div style={{ fontWeight: 600, marginBottom: "0.3rem" }}>Checking {fileName}…</div>
              <div className="muted" style={{ fontSize: "0.85rem" }}>
                Validating columns, identifying duplicates, and preparing your preview.
              </div>
            </div>
          )}

          {status === "preview" && preview && (
            <div className="upload-preview">
              <div className="card-label" style={{ marginBottom: "0.6rem" }}>Review before importing</div>
              <p className="muted" style={{ margin: "0 0 1rem", fontSize: "0.85rem" }}>
                {preview.year && `${preview.year} expense file, ${preview.months_covered.length} months covered. `}
                {preview.total_rows.toLocaleString()} rows checked. {preview.valid_rows.toLocaleString()} valid rows will be imported. This file will replace the current expense ledger. {preview.duplicate_rows > 0 && `${preview.duplicate_rows.toLocaleString()} duplicates in this file will be skipped.`}
                {preview.errors.length > 0 && ` ${preview.errors.length.toLocaleString()} invalid rows were excluded.`}
              </p>
              <div className="upload-preview-table-wrap">
                <table className="upload-preview-table">
                  <thead><tr>{Object.keys(preview.preview[0] || {}).filter((key) => key !== "confidence").map((key) => <th key={key}>{key}</th>)}</tr></thead>
                  <tbody>{preview.preview.map((row, index) => <tr key={index}>{Object.entries(row).filter(([key]) => key !== "confidence").map(([key, value]) => <td key={key}>{String(value)}</td>)}</tr>)}</tbody>
                </table>
              </div>
              {preview.errors.length > 0 && <p className="muted" style={{ fontSize: "0.78rem", marginBottom: "1rem" }}>Example issue: row {preview.errors[0].row}: {preview.errors[0].reason}</p>}
              <div className="upload-preview-actions">
                <button type="button" className="btn btn-solid" disabled={!preview.valid_rows} onClick={confirmImport}>Confirm import</button>
                <button type="button" className="btn btn-outline" onClick={reset}>Cancel</button>
              </div>
              {error && <p role="alert" style={{ color: "#b42318", marginTop: "1rem", fontSize: "0.9rem" }}>{error}</p>}
            </div>
          )}

          {status === "confirming" && (
            <div className="upload-status"><div className="upload-spinner" aria-hidden="true" /><div style={{ fontWeight: 600 }}>Saving your confirmed import…</div></div>
          )}

          {status === "ready" && (
            <div className="upload-status">
              <div className="upload-status-check" aria-hidden="true">✓</div>
              <div style={{ fontWeight: 600, marginBottom: "0.4rem" }}>Your dashboard is ready</div>
              <div className="muted" style={{ fontSize: "0.85rem", marginBottom: "1.4rem" }}>
                {preview?.result?.message || `Built from ${fileName}.`}
              </div>
              <button type="button" className="btn btn-solid" onClick={() => navigate("/dashboard")}>
                View dashboard <ArrowUpRight width={15} height={15} />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default UploadFlowPage;
