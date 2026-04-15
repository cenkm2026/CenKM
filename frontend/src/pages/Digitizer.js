// src/pages/Tool3Page.js
import Header from "../components/Header";
import { useThemeStore } from "../style/useThemeStore";
import React, { useRef, useState } from "react";
import axios from "axios";

import { Card, SectionHeader } from "../components/Cards";
import { Button, Popover, TextArea, TextInput, Tip } from "../components/PageComponents"

import {
  MousePointer2,
  Ruler,
  Undo2,
  Trash2,
  Send,
} from "lucide-react";

// ===============================================================
//  MANUAL DIGITIZER PAGE (FULL FUNCTIONALITY)
// ===============================================================
// Manual KM curve digitizer with calibration and export.
export default function ManualDigitizer() {
  const { theme: c } = useThemeStore();

  const canvasRef = useRef(null);
  const imgRef = useRef(null);

  const [imageSrc, setImageSrc] = useState(null);
  const [ctx, setCtx] = useState(null);

  const [curvePoints, setCurvePoints] = useState([]);
  const [censorPoints, setCensorPoints] = useState([]);

  const [digitizeMode, setDigitizeMode] = useState("curve");

  // calibration
  const calibrationLabels = ["x_start", "x_end", "y_start","y_end" ];;
  const [calibrationStage, setCalibrationStage] = useState(0);
  const [calibPixels, setCalibPixels] = useState({});
  const [calibValues, setCalibValues] = useState({
    x_start: 0,
    x_end: null,
    y_start: 0,
    y_end: null,
  });
  const [errorMsg, setErrorMsg] = useState("");

  const getDownloadUrl = (fileRef) => {
    if (!fileRef) return null;

    const value = String(fileRef).trim();
    if (!value) return null;
    if (value.startsWith("http://") || value.startsWith("https://") || value.startsWith("/")) {
      return value;
    }

    // Backend may return Windows absolute paths like D:\...\digitized_xxx.xlsx.
    const filename = value.split(/[\\/]/).pop();
    return filename ? `/data/${filename}` : null;
  };

  // =================================================================
  // Load selected image into an in-memory data URL.
  const handleImageUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (ev) => setImageSrc(ev.target.result);
    reader.readAsDataURL(file);
  };

  // Initialize canvas size and draw the uploaded image.
  const handleImageLoad = () => {
    const canvas = canvasRef.current;
    const context = canvas.getContext("2d");
    const img = imgRef.current;

    canvas.width = img.width;
    canvas.height = img.height;

    context.drawImage(img, 0, 0);
    setCtx(context);
  };

  // ===================================================================
  // Handle calibration clicks or digitization points on the canvas.
  const handleCanvasClick = (e) => {
    if (!ctx) return;

    const rect = canvasRef.current.getBoundingClientRect();
    const scaleX = canvasRef.current.width / rect.width;
    const scaleY = canvasRef.current.height / rect.height;

    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;

    // Calibration
    if (calibrationStage < 4) {
      const label = calibrationLabels[calibrationStage];
      setCalibPixels((prev) => ({
        ...prev,
        [`${label}_px`]: { x, y },
      }));

      drawMarker(x, y, "#7dd3fc", label.toUpperCase());
      setCalibrationStage((s) => s + 1);
      return;
    }


    // ---- NEW: block digitization if calibration incomplete ----
    for (const key of ["x_start", "x_end", "y_start", "y_end"]) {
      if (calibValues[key] === null) {
        setErrorMsg(`Calibration value "${key.toUpperCase()}" is missing.`);
        return;
      }
    }

    setErrorMsg("");

    // Data conversion
    const xData = pixelToDataX(x);
    const yData = pixelToDataY(y);
    if (xData == null) return;

    if (digitizeMode === "curve") {
      setCurvePoints((p) => [...p, { x_px: x, y_px: y, x: xData, y: yData }]);
      drawMarker(x, y, "#4e7cff");
    }
    if (digitizeMode === "censor") {
      setCensorPoints((p) => [...p, { x_px: x, y_px: y, x: xData }]);
      drawCensorMark(x, y);
    }
  };

  // ===================================================================
  // Draw a circular point marker with optional label.
  const drawMarker = (x, y, color, label = null) => {
    ctx.fillStyle = color;
    ctx.shadowBlur = 6;
    ctx.shadowColor = color;

    ctx.beginPath();
    ctx.arc(x, y, 5, 0, 2 * Math.PI);
    ctx.fill();
    ctx.shadowBlur = 0;

    if (label) {
      ctx.fillStyle = color;
      ctx.font = "14px Inter";
      ctx.fillText(label, x + 8, y - 8);
    }
  };

  // Draw a short vertical tick for a censor point.
  const drawCensorMark = (x, y) => {
    ctx.strokeStyle = "#4e7cff";
    ctx.lineWidth = 2;
    ctx.shadowBlur = 6;
    ctx.shadowColor = "#4e7cff";

    ctx.beginPath();
    ctx.moveTo(x, y - 6);
    ctx.lineTo(x, y + 6);
    ctx.stroke();
    ctx.shadowBlur = 0;
  };

  // ===================================================================
  // Convert pixel X to data X using calibration points.
  const pixelToDataX = (x) => {
    const { x_start_px, x_end_px } = calibPixels;
    const { x_start, x_end } = calibValues;
    if (!x_start_px || !x_end_px) return null;
    const ratio = (x - x_start_px.x) / (x_end_px.x - x_start_px.x);
    return x_start + ratio * (x_end - x_start);
  };

  // Convert pixel Y to data Y with top/bottom detection.
  const pixelToDataY = (y) => {
    const { y_start_px, y_end_px } = calibPixels;
    const { y_start, y_end } = calibValues;
    if (!y_start_px || !y_end_px) return null;

    // 1) figure out which pixel is visually top/bottom
    const topPx = y_start_px.y < y_end_px.y ? y_start_px.y : y_end_px.y;
    const bottomPx = y_start_px.y < y_end_px.y ? y_end_px.y : y_start_px.y;

    // 2) figure out which value is min/max
    const minVal = Math.min(y_start, y_end);
    const maxVal = Math.max(y_start, y_end);

    // 3) compute ratio: 1 at top, 0 at bottom
    const ratio = (bottomPx - y) / (bottomPx - topPx);

    // 4) map to data range
    return minVal + ratio * (maxVal - minVal);
  };


  // Clear and redraw image with all stored markers.
  const redrawCanvas = () => {
    if (!ctx) return;
    ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
    ctx.drawImage(imgRef.current, 0, 0);

    Object.values(calibPixels).forEach((p) => drawMarker(p.x, p.y, "#7dd3fc"));
    curvePoints.forEach((p) => drawMarker(p.x_px, p.y_px, "#4e7cff"));
    censorPoints.forEach((p) => drawCensorMark(p.x_px, p.y_px));
  };

  // Remove the last point from the active digitize mode.
  const undoLastPoint = () => {
    if (digitizeMode === "curve") setCurvePoints(curvePoints.slice(0, -1));
    else setCensorPoints(censorPoints.slice(0, -1));
    redrawCanvas();
  };

  // Reset calibration and digitized points.
  const resetAll = () => {
    setCalibrationStage(0);
    setCalibPixels({});
    setCurvePoints([]);
    setCensorPoints([]);
    if (ctx) {
      ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
      if (imageSrc) ctx.drawImage(imgRef.current, 0, 0);
    }
  };

  // ===================================================================
  // Validate calibration/points and send to backend for export.
  const sendPointsToBackend = async () => {

    for (const key of ["x_start", "x_end", "y_start", "y_end"]) {
      if (calibValues[key] === null) {
        setErrorMsg(`Calibration value "${key.toUpperCase()}" is missing.`);
        return;
      }
    }

    const pxKeys = ["x_start_px", "x_end_px", "y_start_px", "y_end_px"];
    for (const key of pxKeys) {
      if (!calibPixels[key]) {
        setErrorMsg(
          `Calibration pixel "${key.toUpperCase()}" is missing. Please click on the image to calibrate.`
        );
        return;
      }
    }

    if (curvePoints.length === 0 && censorPoints.length === 0) {
      setErrorMsg("No digitized points found.");
      return;
    }

    setErrorMsg("");

    try {
      const res = await axios.post("/api/save_points", {
        calibration: { calibPixels, calibValues },
        curve_points: curvePoints,
        censor_points: censorPoints,
      });

      const files = [
        // res.data.json_file,
        // res.data.curve_csv,
        // res.data.censor_csv,
        res.data.excel_file,
      ];

      for (const f of files) {
        const url = getDownloadUrl(f);
        if (!url) continue;

        const r = await axios.get(url, {
          responseType: "blob",
        });
        const fileName = String(f).split(/[\\/]/).pop() || "digitized_points.xlsx";
        const blobUrl = URL.createObjectURL(new Blob([r.data]));
        const link = document.createElement("a");
        link.href = blobUrl;
        link.download = fileName;
        link.click();
        URL.revokeObjectURL(blobUrl);
      }

      alert("Digitized files saved & downloaded!");
    } catch (err) {
      console.log(err.response?.data || err.message);
      alert("Save failed.");
    }
  };

  // ========== UI ====================================================
  return (
    <div
      className="min-h-screen w-full"
      style={{
        background: c.pageBackground,
        color: c.text,
      }}
    >
      <main className="container mx-auto p-10">
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
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">

          {/* ------------- LEFT PANEL: CANVAS ---------------- */}
          <Card className="lg:col-span-2">
            <SectionHeader
              icon={MousePointer2}
              title="KM Digitizer"
              action={
                <label
                  className="cursor-pointer text-sm"
                  style={{ color: c.primary }}
                  onMouseEnter={e => e.currentTarget.style.color = c.primaryHover}
                  onMouseLeave={e => e.currentTarget.style.color = c.primary}
                  >
                  <input type="file" accept="image/*" className="hidden" onChange={handleImageUpload} />
                  Upload Image
                </label>
              }
            />

            <div className="p-6" style={{ minHeight: "750px" }}>
              {!imageSrc && (
                <p style={{ color: c.muted }}>Upload a plot to begin.</p>
              )}

              {imageSrc && (
                <>
                  <p className="mb-4 text-sm" style={{ color: c.muted }}>
                    {calibrationStage < 4
                      ? `Calibration Step ${calibrationStage + 1}/4 : Click ${calibrationLabels[
                          calibrationStage
                        ].toUpperCase()}`
                      : `Calibration complete Mode: ${digitizeMode}`}
                  </p>

                  <img
                    ref={imgRef}
                    src={imageSrc}
                    alt="plot"
                    onLoad={handleImageLoad}
                    style={{ display: "none" }}
                  />

                  <div className="flex gap-3 mb-4">
                    <Button
                      onClick={() => setDigitizeMode("curve")}
                      className={digitizeMode === "curve" ? "bg-blue-600" : "bg-gray-600"}
                    >
                      Curve
                    </Button>
                    <Button
                      onClick={() => setDigitizeMode("censor")}
                      className={digitizeMode === "censor" ? "bg-blue-600" : "bg-gray-600"}
                    >
                      Censor
                    </Button>
                  </div>

                  <canvas
                    ref={canvasRef}
                    onClick={handleCanvasClick}
                    className="w-full rounded-xl border"
                    style={{
                      borderColor: c.border,
                      background: "rgba(0,0,0,0.3)",
                    }}
                  />
                </>
              )}
            </div>
          </Card>

          {/* ------------- RIGHT PANEL: CALIBRATION + POINTS ---------------- */}
          <div className="flex flex-col gap-10">

            <Card>
              <SectionHeader icon={Ruler} title="Axis Calibration" />
              <div className="pt-1 pb-6 grid grid-cols-2 gap-4">
                {["x_start", "x_end", "y_start", "y_end"].map((k) => (
                  <div key={k}>
                    <label className="text-sm" style={{ color: c.muted }}>
                      {k.toUpperCase()}
                    </label>
                    <input
                      type="number"
                      value={calibValues[k]}
                      placeholder="None"
                      onChange={(e) =>
                        setCalibValues({
                          ...calibValues,
                          [k]: e.target.value === "" ? null : parseFloat(e.target.value),
                        })
                      }
                      className="w-full rounded-lg p-2 mt-1"
                      style={{
                        background: c.glass,
                        border: `1px solid ${c.border}`,
                        color: c.text,
                      }}
                    />
                  </div>
                ))}
              </div>
            </Card>

            <Card>
              <SectionHeader icon={Ruler} title="Digitized Points" />
              <div className="pt-1 pb-6">
                <div className="flex justify-center gap-6 mb-4">
                  <Button className="w-40" icon={Undo2} onClick={undoLastPoint}>
                    Undo
                  </Button>
                  <Button
                    icon={Trash2}
                    onClick={resetAll}
                    className="w-40 bg-red-600"
                  >
                    Reset
                  </Button>
                </div>

                <div
                  className="rounded-xl p-3 text-xs overflow-auto"
                  style={{
                    height: "260px",
                    background: c.textAreaBackground,
                    border: `1px solid ${c.border}`,
                  }}
                >
                  <pre style={{ whiteSpace: "pre-wrap", color: c.text }}>
                    {JSON.stringify(
                      digitizeMode === "curve" ? curvePoints : censorPoints,
                      null,
                      2
                    )}
                  </pre>
                </div>

                <div className="flex justify-end mt-4">
                  <Button icon={Send} onClick={sendPointsToBackend}>
                    Save Points
                  </Button>
                </div>
              </div>
            </Card>

          </div>
        </div>
      </main>
    </div>
  );
}
