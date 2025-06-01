# bootstrap_toast_api.py
import subprocess
from pathlib import Path
import sys
import shutil

# Define paths
PROJECT_DIR = Path.cwd() / "toast_summary_api"
TOAST_TOOL_DIR = PROJECT_DIR / "toast_tool"
MAIN_FILE = PROJECT_DIR / "main.py"
ZIP_SUMMARY_FILE = TOAST_TOOL_DIR / "zip_summary.py"
REQUIREMENTS = PROJECT_DIR / "requirements.txt"
RENDER_YAML = PROJECT_DIR / "render.yaml"




# Create folder structure
TOAST_TOOL_DIR.mkdir(parents=True, exist_ok=True)

# Create main.py
MAIN_FILE.write_text("""\
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from toast_tool.zip_summary import summarize_toast_zip

app = FastAPI(
    title="Toast Summary API",
    version="1.0.0",
    description="Upload a Toast ZIP file and receive a summarized report of sales, voids, and discounts.",
    servers=[
        {"url": "https://toastapi.onrender.com"}
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/summarize")
async def summarize_zip(zip_file: UploadFile = File(...)):
    zip_bytes = await zip_file.read()
    df = summarize_toast_zip(zip_bytes)
    return df.to_dict(orient="records")
""")

# Create zip_summary.py
ZIP_SUMMARY_FILE.write_text("""\
import zipfile
import pandas as pd
from pathlib import Path
import tempfile

def summarize_toast_zip(zip_bytes: bytes) -> pd.DataFrame:
    with tempfile.TemporaryDirectory() as tempdir:
        zip_path = Path(tempdir) / "input.zip"
        extract_path = Path(tempdir) / "extracted"
        zip_path.write_bytes(zip_bytes)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

        all_items = list(extract_path.rglob("*AllItemsReport.csv"))
        if not all_items:
            raise FileNotFoundError("No AllItemsReport.csv found in ZIP.")

        def summarize(file):
            df = pd.read_csv(file)
            return {
                "date": file.parts[-2],
                "net_sales": round(df["Net Amount"].sum(), 2),
                "voids": round(df[df["Revenue Center"].str.contains("Void", na=False)]["Net Amount"].sum(), 2),
                "discounts": round(df[df["Revenue Center"].str.contains("Discount", na=False)]["Net Amount"].sum(), 2),
                "orders": df["Check Number"].nunique() if "Check Number" in df.columns else len(df)
            }

        summary = [summarize(f) for f in all_items]
        df_summary = pd.DataFrame(summary)
        df_summary["flag_voids"] = df_summary["voids"] > 50
        df_summary["flag_discounts"] = df_summary["discounts"] > 50
        return df_summary
""")

# Create requirements.txt
REQUIREMENTS.write_text("fastapi\npandas\npython-multipart\nuvicorn\n")

# Create render.yaml
RENDER_YAML.write_text("""\
services:
  - type: web
    name: toast-summary-api
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port 10000
""")

print("📁 Project structure created!")

# Create virtual environment and install dependencies
venv_path = PROJECT_DIR / "venv"
if not venv_path.exists():
    subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
pip_path = venv_path / ("Scripts" if sys.platform.startswith("win") else "bin") / "pip"
subprocess.run([str(pip_path), "install", "-r", str(REQUIREMENTS)], check=True)

# Initialize git repo
git_path = shutil.which("git")
if git_path and not (PROJECT_DIR / ".git").exists():
    subprocess.run(["git", "init"], cwd=PROJECT_DIR)
    subprocess.run(["git", "add", "."], cwd=PROJECT_DIR)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=PROJECT_DIR)
    print("✅ Git initialized.")

# Launch VS Code
print("🚀 Launching VS Code...")
code_path = shutil.which("code")
if code_path:
    subprocess.run([code_path, str(PROJECT_DIR)])
else:
    print("⚠️ VS Code command-line tool 'code' not found. Please open the project folder manually.")

print("🎉 All set! Deploy it from GitHub to Render and connect to GPT.")
