import React, { useState } from "react";
import axios from "axios";
import { useThemeStore } from "../style/useThemeStore";
import { Card, SectionHeader } from "../components/Cards";
import { Button, TextInput } from "../components/PageComponents";
import { UploadCloud, Image as ImageIcon } from "lucide-react";

// Reconstruct KM curves from digitized Excel with optional overlay.
export default function ReconstructionPage() {
  const { theme: c } = useThemeStore();
  // ===== Excel is the ONLY input =====
  const [excelFile, setExcelFile] = useState(null);

  // N (optional if backend can infer from risk table)
  const [n, setN] = useState("");

  // ===== Overlay optional step =====
  const [wantsOverlay, setWantsOverlay] = useState(false);
  const [plotImg, setPlotImg] = useState(null);

  // ===== UI state =====
  // Optional manual risk table as rows
  const [riskRows, setRiskRows] = useState([{ time: "", risk: "" }]);

  const [loading, setLoading] = useState(false);
  const [previewImg, setPreviewImg] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [reconDone, setReconDone] = useState(false);

  // Append an empty risk row for manual entry.
  const addRiskRow = () => {
    setRiskRows([...riskRows, { time: "", risk: "" }]);
  };

  // Update a single field in a risk row.
  const updateRiskRow = (i, field, value) => {
    const newRows = [...riskRows];
    newRows[i][field] = value;
    setRiskRows(newRows);
  };

  // Remove a risk row and keep at least one empty row.
  const removeRiskRow = (i) => {
    const newRows = riskRows.filter((_, idx) => idx !== i);
    setRiskRows(newRows.length > 0 ? newRows : [{ time: "", risk: "" }]);
  };

  // Convert manual risk rows to numeric payload.
  const serializeRiskRows = () => {
    return riskRows
      .map((row) => {
        const time = parseFloat(row.time);
        const risk = parseFloat(row.risk);
        if (isNaN(time) || isNaN(risk)) return null;
        return { time, risk };
      })
      .filter((row) => row !== null);
  };

  const [ipdFile, setIpdFile] = useState(null);

 
  // --------------------------------------------------------
  // STEP 1 — RECONSTRUCT FROM EXCEL (No overlay)
  // --------------------------------------------------------
  // Step 1: reconstruct from Excel only (no overlay).
  const reconstructFromExcel = async () => {
    setErrorMsg("");
    setPreviewImg(null);
    setReconDone(false);

    if (!excelFile) {
      setErrorMsg("Please upload one Excel file (digitized_*.xlsx).");
      return;
    }

    const formData = new FormData();
    formData.append("excel_file", excelFile);
    const riskTable = serializeRiskRows();
    if (riskTable.length > 0) {
      formData.append("risk_table", JSON.stringify(riskTable));
    }
    if (n !== "") formData.append("n", n);

    try {
      setLoading(true);

      const res = await axios.post(
        "/api/reconstruct_from_excel",
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );

      // show reconstructed KM curve
      if (res.data.plot_file) {
        const url = res.data.plot_file.startsWith("/")
          ? res.data.plot_file
          : "/" + res.data.plot_file;

        setPreviewImg(url);
      }


      if (res.data.ipd_file) {
        setIpdFile(res.data.ipd_file);
      }

      setReconDone(true);

    } catch (err) {
      console.error(err);
      if (err.response && err.response.data && err.response.data.message) {
        setErrorMsg(err.response.data.message);  
      } else {
        setErrorMsg("Reconstruction from Excel failed.");
      }
    } finally {
      setLoading(false);
    }
  };

  // --------------------------------------------------------
  // STEP 2 — OVERLAY FROM EXCEL (Excel sheet 3 contains calibration)
  // --------------------------------------------------------
  // Step 2: reconstruct with overlay using the original plot.
  const reconstructOverlayFromExcel = async () => {
    setErrorMsg("");

    if (!excelFile) {
      setErrorMsg("Excel file missing — re-upload if needed.");
      return;
    }
    if (!plotImg) {
      setErrorMsg("Please upload the original KM plot for overlay.");
      return;
    }

    const formData = new FormData();
    formData.append("excel_file", excelFile);
    const riskTable = serializeRiskRows();
    if (riskTable.length > 0) {
      formData.append("risk_table", JSON.stringify(riskTable));
    }
    if (n !== "") formData.append("n", n);
    formData.append("plot_image", plotImg);

    try {
      setLoading(true);

      const res = await axios.post(
        "/api/reconstruct_with_overlay_from_excel",
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );

      if (res.data.plot_file) {
        setPreviewImg(res.data.plot_file);
      }
    } catch (err) {
      console.error(err);
      setErrorMsg("Overlay reconstruction failed.");
    } finally {
      setLoading(false);
    }
  };

  // --------------------------------------------------------
  // UI
  // --------------------------------------------------------
  return (
    <div
      className="min-h-screen w-full flex flex-col"
      style={{
        backgroundImage: c.pageBackground,
        backgroundRepeat: "no-repeat",
        backgroundSize: "cover",
        color: c.text,
      }}
    >
      <main className="container mx-auto px-4 py-10 max-w-7xl">

        {/* Error message */}
        {errorMsg && (
          <div
            className="rounded-xl p-4 mb-6 text-sm"
            style={{
              background: c.errorBackground,
              border: `1px solid ${c.errorBorder}`,
              color: c.errorText,
            }}
          >
            {errorMsg}
          </div>
        )}

        {/* TWO COLUMN GRID */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">

        {/* LEFT COLUMN — SINGLE CARD WITH TWO MODES */}
        <div className="flex flex-col gap-10 ">

          <Card className="relative overflow-hidden flex flex-col">


            {/* Smooth slide container */}
            <div
              className="flex h-full transition-transform duration-500"
              style={{
                width: "200%",
                transform: reconDone ? "translateX(-50%)" : "translateX(0%)",
              }}
            >
              {/* ========================================================= */}
              {/*             STEP 1 PANEL — Upload + Run Recon             */}
              {/* ========================================================= */}
              <div className="w-1/2 p-6 pr-8">
                <SectionHeader icon={UploadCloud} title="1) Upload Excel File" />

                <div className="space-y-6 mt-4">

                  <p className="text-sm" style={{ color: c.muted }}>
                    Excel must contain: curve_points, censor_points, calibration sheets.
                  </p>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8">

                    {/* LEFT SIDE — Excel File */}
                    <div className="flex flex-col gap-2">
                      <h4 className="text-base font-semibold" style={{ color: c.text }}>
                        Digitized Excel File
                      </h4>

                      <input
                        type="file"
                        accept=".xlsx"
                        onChange={(e) => setExcelFile(e.target.files?.[0] || null)}
                        className="text-sm"
                        style={{ color: c.text }}
                      />
                    </div>

                    {/* RIGHT SIDE — Total N */}
                    <div className="flex flex-col gap-2">
                      <h4 className="text-base font-semibold" style={{ color: c.text }}>
                        Total Patients
                      </h4>

                      <TextInput
                        as="input"
                        type="number"
                        value={n}
                        onChange={(e) => setN(e.target.value)}
                        placeholder="Total Number"
                        className="text-sm py-2"
                      />
                    </div>

                  </div>

                  {/* Table Header */}
                  <h4 className="text-base font-semibold" style={{ color: c.text }}>
                    Optional: Risk Table (row by row)
                  </h4>

                  {/* Table Rows */}
                  <div className="space-y-0.5">
                    {riskRows.map((row, i) => (
                      <div
                        key={i}
                        className="grid grid-cols-[40px_1fr_1fr_30px] items-center gap-3 p-1 rounded-lg transition-all"
                        style={{
                          background: "c.glass",
                          border: `1px solid ${c.border}`,
                        }}
                      >
                        {/* Index */}
                        <div className="text-center text-sm" style={{ color: c.muted }}>
                          {i + 1}
                        </div>

                        {/* Time */}
                        <TextInput
                          type="number"
                          value={row.time}
                          placeholder="time"
                          onChange={(e) => updateRiskRow(i, "time", e.target.value)}
                          className="text-sm px-3 py-1"
                        />

                        {/* Risk */}
                        <TextInput
                          as="input"
                          type="number"
                          value={row.risk}
                          placeholder="risk"
                          onChange={(e) => updateRiskRow(i, "risk", e.target.value)}
                          className="text-sm px-3 py-1"
                        />

                        {/* Delete (round button) */}
                        <button
                          onClick={() => removeRiskRow(i)}
                          className="w-6 h-6 flex items-center justify-center rounded-full transition-all hover:brightness-125"
                          style={{
                            background: "c.secondary",
                            color: c.text,
                            fontSize:"12px",
                            boxShadow: `0 0 6px ${c.glow}`,
                          }}
                        >
                          ⨯
                        </button>
                      </div>
                    ))}
                  </div>

                  {/* Add Row (blue clickable text) */}
                  <div
                    onClick={addRiskRow}
                    className="mt-2 cursor-pointer text-xs font-medium"
                    style={{
                      color: c.primary,
                      textDecoration: "none" 
                    }}
                    onMouseEnter={e => e.currentTarget.style.color = c.primaryHover}
                    onMouseLeave={e => e.currentTarget.style.color = c.primary}

                  >
                    + Add Row
                  </div>

                  <div className="mt-4 flex justify-end">
                  <Button className="mt-4" onClick={reconstructFromExcel} disabled={loading}>
                    {loading ? "Reconstructing..." : "Run Reconstruction"}
                  </Button>
                  </div>
                </div>
              </div>

              {/* ========================================================= */}
              {/*             STEP 2 PANEL — Overlay Options                */}
              {/* ========================================================= */}
              <div className="w-1/2 p-6 pl-8 flex flex-col h-full">                
                {/* Back Button */}

                <SectionHeader icon={ImageIcon} title="2) Overlay Options" />

                <div className="flex flex-col gap-6 mt-4 flex-grow">
                  <div className="flex gap-6 text-sm">
                    <label className="flex gap-2 items-center">
                      <input
                        type="radio"
                        checked={!wantsOverlay}
                        onChange={() => setWantsOverlay(false)}
                      />
                      No Overlay
                    </label>

                    <label className="flex gap-2 items-center">
                      <input
                        type="radio"
                        checked={wantsOverlay}
                        onChange={() => setWantsOverlay(true)}
                      />
                      Overlay on Original Plot
                    </label>
                  </div>

                  {wantsOverlay && (
                    <div className="flex flex-col gap-4">
                      <div>
                        <h4 className="mb-2 text-sm" style={{ color: c.text }}>
                          Upload Original KM Plot
                        </h4>

                        <input
                          type="file"
                          accept="image/*"
                          onChange={(e) => setPlotImg(e.target.files?.[0] || null)}
                          style={{ color: c.text }}
                        />
                      </div>
                    </div>
                  )}


                <div className="mt-auto flex justify-between pt-6">
                  <Button variant="subtle" onClick={() => setReconDone(false)}>
                    ← Back
                  </Button>

                  {wantsOverlay && (
                    <Button
                      disabled={loading}
                      onClick={reconstructOverlayFromExcel}
                    >
                      {loading ? "Overlaying..." : "Run Overlay"}
                    </Button>
                  )}
                </div>
                </div>

              </div>

            </div>
          </Card>
        </div>



          {/* RIGHT COLUMN — Preview + Overlay */}
          <div className="flex flex-col gap-10">

            {/* Preview */}
            {previewImg && (
              <Card className="flex flex-col">
                <SectionHeader icon={ImageIcon} title="Reconstruction Preview" />
                <div className="p-6">
                  <img
                    src={previewImg}
                    alt="preview"
                    className="w-full rounded-xl"
                    style={{ border: `1px solid ${c.border}` }}
                  />
                </div>

                {ipdFile && (
                  <div className="px-6 pb-6 flex justify-end">
                    <Button
                      onClick={async () => {
                        try {
                          const fileRes = await axios.get(ipdFile, { responseType: "blob" });

                          const url = URL.createObjectURL(fileRes.data);
                          const a = document.createElement("a");
                          a.href = url;
                          a.download = ipdFile.split("/").pop();
                          a.click();
                          URL.revokeObjectURL(url);
                        } catch (err) {
                          console.error(err);
                          alert("Failed to download reconstruction data.");
                        }
                      }}
                    >
                      Download Reconstruction Data
                    </Button>
                  </div>
                )}

              </Card>
            )}


          </div>
        </div>
      </main>
    </div>
  );
}
