import { useEffect, useRef, useState, type DragEvent, type FormEvent } from "react";
import { FileUp, X } from "lucide-react";

interface UploadPanelProps {
  busy: boolean;
  error: string | null;
  resetVersion: number;
  onSelectionChange: () => void;
  onUpload: (file: File) => void;
}

function isSupportedTabularFile(file: File): boolean {
  return /\.(csv|json|jsonl|ndjson)$/i.test(file.name);
}

export function UploadPanel({ busy, error, resetVersion, onSelectionChange, onUpload }: UploadPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    if (resetVersion === 0) return;
    setFile(null);
    setLocalError(null);
    if (inputRef.current) inputRef.current.value = "";
  }, [resetVersion]);

  function chooseFile(candidate?: File) {
    if (!candidate) return;
    onSelectionChange();
    if (!isSupportedTabularFile(candidate)) {
      setFile(null);
      setLocalError("Choose a UTF-8 CSV, JSON, or JSON Lines file. The backend will validate its contents.");
      return;
    }
    setLocalError(null);
    setFile(candidate);
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    chooseFile(event.dataTransfer.files[0]);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (file && !busy) onUpload(file);
  }

  function clearFile() {
    onSelectionChange();
    setFile(null);
    setLocalError(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  const visibleError = localError ?? error;

  return (
    <section className="surface upload-surface" aria-labelledby="upload-heading">
      <div className="section-header upload-header">
        <div><p className="eyebrow">SOURCE REGISTRY</p><h2 id="upload-heading">Register tabular data</h2></div>
        <span className="section-icon section-icon-teal" aria-hidden="true"><FileUp size={17} /></span>
      </div>
      <p className="section-description">DataTrace stores the uploaded file and returns its checksum, detected columns and source ID.</p>
      <form onSubmit={submit} className="upload-form">
        <label
          className={`file-drop${dragging ? " file-drop-active" : ""}${file ? " file-drop-selected" : ""}`}
          htmlFor="source-file"
          onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          aria-describedby="upload-help"
        >
          <span className="upload-symbol" aria-hidden="true"><FileUp size={19} /></span>
          <span className="file-drop-title">{file ? file.name : "Drop CSV or JSON files here, or browse"}</span>
          <span id="upload-help" className="file-drop-help">UTF-8 CSV · JSON object/array · JSON Lines · validated by the backend</span>
        </label>
        <input
          ref={inputRef}
          id="source-file"
          className="visually-hidden"
          type="file"
          accept=".csv,.json,.jsonl,.ndjson,text/csv,application/json"
          disabled={busy}
          aria-invalid={Boolean(visibleError)}
          aria-describedby={visibleError ? "upload-help upload-error" : "upload-help"}
          onChange={(event) => chooseFile(event.currentTarget.files?.[0])}
        />
        {file ? <div className="selected-file-row"><span><strong>{file.name}</strong><small>{file.size.toLocaleString()} bytes · selected for registration</small></span><button className="icon-button" type="button" onClick={clearFile} disabled={busy} aria-label="Remove selected file"><X size={15} /></button></div> : null}
        <button className="button button-primary upload-submit" type="submit" disabled={!file || busy}>
          {busy ? <><span className="spinner" aria-hidden="true" />Registering source…</> : <><FileUp size={16} aria-hidden="true" />Register source</>}
        </button>
      </form>
      {visibleError ? <p id="upload-error" className="form-error" role="alert">{visibleError}</p> : null}
    </section>
  );
}
