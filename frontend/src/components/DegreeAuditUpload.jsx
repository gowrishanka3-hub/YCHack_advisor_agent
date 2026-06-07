import { useRef, useState } from "react";

export default function DegreeAuditUpload() {
  const inputRef = useRef(null);
  const [status, setStatus] = useState(null);

  const handleClick = () => {
    inputRef.current?.click();
  };

  const handleChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setStatus("uploading");
    setTimeout(() => {
      setStatus("success");
      setTimeout(() => setStatus(null), 4000);
    }, 800);

    e.target.value = "";
  };

  return (
    <div className="relative">
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,application/pdf"
        className="hidden"
        onChange={handleChange}
      />
      <button
        type="button"
        onClick={handleClick}
        disabled={status === "uploading"}
        className="cursor-pointer rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs font-medium text-zinc-300 transition-colors hover:border-emerald-500/40 hover:bg-zinc-800 hover:text-zinc-100 disabled:opacity-60"
      >
        {status === "uploading" ? "Uploading…" : "Upload degree audit (PDF)"}
      </button>

      {status === "success" && (
        <div className="absolute left-0 top-full z-50 mt-2 whitespace-nowrap rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs font-medium text-emerald-300 shadow-lg">
          File uploaded successfully
        </div>
      )}
    </div>
  );
}
