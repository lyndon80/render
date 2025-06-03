import zipfile
import pandas as pd
from pathlib import Path
import tempfile
import shutil

def summarize_toast_zip(zip_bytes: bytes) -> pd.DataFrame:
    with tempfile.TemporaryDirectory() as tempdir:
        zip_path = Path(tempdir) / "input.zip"
        extract_path = Path(tempdir) / "extracted"
        zip_path.write_bytes(zip_bytes)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for member in zip_ref.infolist():
                member_path = extract_path / member.filename
                resolved_path = member_path.resolve()
                if not str(resolved_path).startswith(str(extract_path.resolve())):
                    raise Exception(f"Unsafe path detected: {member.filename}")
                if member.is_dir():
                    resolved_path.mkdir(parents=True, exist_ok=True)
                else:
                    resolved_path.parent.mkdir(parents=True, exist_ok=True)
                    with zip_ref.open(member) as source, open(resolved_path, "wb") as target:
                        shutil.copyfileobj(source, target)

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
