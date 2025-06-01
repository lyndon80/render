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
