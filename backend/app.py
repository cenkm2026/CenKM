from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
import datetime
import json
import logging
import os
import secrets
import time
import traceback
from pathlib import Path

import pandas as pd
from werkzeug.middleware.proxy_fix import ProxyFix

from reconstruct.utils.save_points import save_points as reconstruct_save_points
from reconstruct.utils.save_risk_table import save_risk_table as reconstruct_save_risk_table
from reconstruct.utils.reconstruct_v1 import reconstruct_v1
from reconstruct.utils.reconstruct_overlay import reconstruct_no_overlay, reconstruct_with_overlay


# --------------------------------------------------------------------------------------
# App setup
# --------------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
FRONTEND_BUILD = PROJECT_ROOT / "frontend" / "build"
PUBLIC_DIR = PROJECT_ROOT / "frontend" / "public"
STATUS_PATH = PUBLIC_DIR / "__maint" / "status.json"

app = Flask(
    __name__,
    static_folder=str(FRONTEND_BUILD / "static"),
    static_url_path="/static",
)

logging.basicConfig(level=logging.INFO)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN")
if ALLOWED_ORIGIN:
    CORS(app, supports_credentials=True, origins=[ALLOWED_ORIGIN])

DATA_FOLDER = BASE_DIR / "data"
OUTPUT_FOLDER = BASE_DIR / "output"
RECONSTRUCT_DATA_FOLDER = BASE_DIR / "reconstruct" / "data"
for p in (DATA_FOLDER, OUTPUT_FOLDER, RECONSTRUCT_DATA_FOLDER):
    p.mkdir(parents=True, exist_ok=True)


@app.route("/data/<path:filename>")
def serve_data_files(filename):
    return send_from_directory(DATA_FOLDER, filename)


def maint_on() -> bool:
    return os.getenv("MAINTENANCE", "0") == "1"


@app.route("/__maint/status.json")
def maint_status():
    try:
        with open(STATUS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {
            "maintenance": True,
            "message": "Service under maintenance.",
            "last_update": datetime.datetime.utcnow().isoformat() + "Z",
        }
    resp = make_response(json.dumps(data), 200)
    resp.headers["Content-Type"] = "application/json"
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.before_request
def maybe_maintenance():
    if maint_on() and not request.path.startswith("/__maint/"):
        resp = make_response(send_from_directory(str(PUBLIC_DIR), "maintenance.html"), 503)
        resp.headers["Retry-After"] = "3600"
        resp.headers["Cache-Control"] = "no-store"
        return resp


@app.after_request
def add_no_cache(resp):
    if request.path in ("/", "/index", "/index.html"):
        resp.headers["Cache-Control"] = "no-store, must-revalidate"
    return resp


# Serve frontend static assets
@app.route("/")
def index():
    return send_from_directory(FRONTEND_BUILD, "index.html")


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(str(FRONTEND_BUILD / "static"), filename)


@app.route("/asset-manifest.json")
def asset_manifest():
    return send_from_directory(str(FRONTEND_BUILD), "asset-manifest.json")


@app.route("/manifest.json")
def manifest():
    return send_from_directory(str(FRONTEND_BUILD), "manifest.json")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(str(FRONTEND_BUILD), "favicon.ico")


@app.errorhandler(Exception)
def _any_error(e):
    app.logger.error("UNCAUGHT EXCEPTION:\n%s", traceback.format_exc())
    return jsonify({"status": "FAIL", "reason": str(e)}), 500


# SPA fallback: keep at bottom so API routes take precedence.
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    candidate = FRONTEND_BUILD / path
    if path and candidate.exists() and candidate.is_file():
        return send_from_directory(FRONTEND_BUILD, path)
    index_html = FRONTEND_BUILD / "index.html"
    if not index_html.exists():
        return jsonify({"error": "frontend build missing", "expected_path": str(index_html)}), 500
    return send_from_directory(FRONTEND_BUILD, "index.html")


@app.route("/api/save_points", methods=["POST"])
def reconstruct_save_points_endpoint():
    data = request.get_json()
    result = reconstruct_save_points(data)

    def passthrough(path):
        return path if path else None

    return jsonify(
        {
            "message": result["message"],
            "json_file": passthrough(result["json_file"]),
            "curve_csv": passthrough(result["curve_csv"]),
            "censor_csv": passthrough(result["censor_csv"]),
            "excel_file": passthrough(result["excel_file"]),
        }
    )


@app.route("/api/save_risk_table", methods=["POST"])
def save_risk_table_endpoint():
    data = request.get_json()
    return jsonify(reconstruct_save_risk_table(data))


@app.route("/api/reconstruct_v1", methods=["POST"])
def reconstruct_v1_endpoint():
    n = int(request.form.get("n"))
    out_file = reconstruct_v1(n=n)
    return jsonify({"message": "IPD reconstructed (v1)", "ipd_file": f"/{out_file}"})


@app.route("/api/reconstruct_from_excel", methods=["POST"])
def reconstruct_from_excel():
    excel_file = request.files.get("excel_file")
    n = request.form.get("n")
    risk_table = request.form.get("risk_table")

    excel_path = os.path.join(DATA_FOLDER, excel_file.filename)
    excel_file.save(excel_path)

    xls = pd.ExcelFile(excel_path)
    curve_df = pd.read_excel(xls, "curve_points").rename(columns={"x": "time", "y": "survival"})

    censor_df = None
    if "censor_points" in xls.sheet_names:
        censor_df = pd.read_excel(xls, "censor_points").rename(columns={"x": "time"})

    risk_df = None
    if risk_table:
        risk_df = json.loads(risk_table)

    try:
        ipd_csv, km_png = reconstruct_no_overlay(
            n=int(n) if n else None,
            curve_df=curve_df,
            censor_df=censor_df,
            output_dir=DATA_FOLDER,
            risk_table=risk_df,
        )

        return jsonify({"status": "ok", "ipd_file": ipd_csv, "plot_file": km_png}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route("/api/reconstruct_with_overlay_from_excel", methods=["POST"])
def reconstruct_with_overlay_from_excel():
    excel_file = request.files.get("excel_file")
    plot_image = request.files.get("plot_image")
    n = request.form.get("n")
    risk_table = request.form.get("risk_table")

    excel_path = os.path.join(DATA_FOLDER, excel_file.filename)
    excel_file.save(excel_path)

    plot_path = os.path.join(DATA_FOLDER, plot_image.filename)
    plot_image.save(plot_path)

    xls = pd.ExcelFile(excel_path)
    curve_df = pd.read_excel(xls, "curve_points").rename(columns={"x": "time", "y": "survival"})

    censor_df = None
    if "censor_points" in xls.sheet_names:
        censor_df = pd.read_excel(xls, "censor_points").rename(columns={"x": "time"})

    calib_df = pd.read_excel(xls, "calibration_pixels")

    risk_df = None
    if risk_table:
        risk_df = json.loads(risk_table)

    ipd_csv, overlay_png = reconstruct_with_overlay(
        curve_df=curve_df,
        censor_df=censor_df,
        calib_df=calib_df,
        plot_path=plot_path,
        n=int(n) if n else None,
        output_dir=DATA_FOLDER,
        risk_table=risk_df,
    )

    return jsonify({"ipd_file": ipd_csv, "plot_file": overlay_png})


@app.get("/api/ping")
def ping():
    return {"ok": True, "ts": time.time()}


if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)
