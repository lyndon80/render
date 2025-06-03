import zipfile
import pandas as pd
from pathlib import Path
import tempfile

VOID_THRESHOLD = 50
DISCOUNT_THRESHOLD = 50

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

            net_sales = 0
            voids = 0
            discounts = 0
            orders = 0

            if "Net Amount" in df.columns:
                net_sales = round(df["Net Amount"].sum(), 2)
                if "Revenue Center" in df.columns:
                    voids = round(df[df["Revenue Center"].str.contains("Void", na=False)]["Net Amount"].sum(), 2)
                    discounts = round(df[df["Revenue Center"].str.contains("Discount", na=False)]["Net Amount"].sum(), 2)

            if "Check Number" in df.columns:
                orders = df["Check Number"].nunique()
            # If "Check Number" is missing, orders remains 0 as per requirement.

            return {
                "date": file.parts[-2],
                "net_sales": net_sales,
                "voids": voids,
                "discounts": discounts,
                "orders": orders
            }

        summary = [summarize(f) for f in all_items]
        df_summary = pd.DataFrame(summary)
        df_summary["flag_voids"] = df_summary["voids"] > VOID_THRESHOLD
        df_summary["flag_discounts"] = df_summary["discounts"] > DISCOUNT_THRESHOLD
        return df_summary
