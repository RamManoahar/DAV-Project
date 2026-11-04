"""Reusable data-quality and cleaning helpers."""
import pandas as pd

def clean_business_data(data):
    """
    Remove fully empty rows/columns and exact duplicate rows.
    Returns (cleaned_dataframe, report).
    Does not fabricate missing values or overwrite source fields.
    """
    df = data.copy()
    report = {
        "input_rows": int(len(df)),
        "input_columns": int(len(df.columns)),
        "duplicate_rows": int(df.duplicated().sum()),
        "missing_cells": int(df.isna().sum().sum()),
    }
    df.columns = [str(column).strip() for column in df.columns]
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    df = df.drop_duplicates().copy()
    report["output_rows"] = int(len(df))
    report["output_columns"] = int(len(df.columns))
    report["removed_rows"] = report["input_rows"] - report["output_rows"]
    return df, report
