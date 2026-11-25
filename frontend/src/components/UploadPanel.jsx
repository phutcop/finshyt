import { useRef, useState } from "react";
import { UploadIcon } from "./Icons";

/* The parent page sends the selected file to the import preview API. */
function UploadPanel({ onFileSelected }) {
  const inputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleFiles = (files) => {
    if (files && files.length > 0) {
      onFileSelected?.(files[0]);
    }
  };

  return (
    <div
      className="upload-picker"
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setIsDragging(false);
        handleFiles(e.dataTransfer.files);
      }}
      style={{ background: isDragging ? "rgba(198,155,92,0.09)" : "transparent" }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
        <div style={{ width: 40, height: 40, borderRadius: "50%", background: "var(--bg-card)", border: "1px solid var(--border-soft)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <UploadIcon width={18} height={18} style={{ opacity: 0.7 }} />
        </div>
        <div>
          <div style={{ fontFamily: "var(--font-display)", fontSize: "1.1rem", marginBottom: "0.2rem" }}>
            Upload ledger
          </div>
          <div className="muted" style={{ fontSize: "0.75rem" }}>
            Drag and drop a CSV or Excel file
          </div>
        </div>
      </div>

      <button type="button" className="btn btn-sm btn-solid" onClick={() => inputRef.current?.click()} style={{ flexShrink: 0 }}>
        Browse
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.xlsx,.xls"
        onChange={(e) => {
          handleFiles(e.target.files);
          e.target.value = "";
        }}
        style={{ display: "none" }}
      />
    </div>
  );
}

export default UploadPanel;
