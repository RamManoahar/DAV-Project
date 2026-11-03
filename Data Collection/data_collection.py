"""Load CSV and Excel business datasets without modifying source values."""
import pandas as pd

def load_business_data(uploaded_file):
    """Read an uploaded CSV/XLS/XLSX file into a DataFrame."""
    uploaded_file.seek(0)
    filename = uploaded_file.name.lower()
    if filename.endswith(".csv"):
        try:
            return pd.read_csv(uploaded_file, low_memory=False)
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            return pd.read_csv(uploaded_file, encoding="latin-1", low_memory=False)
    if filename.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)
    raise ValueError("Unsupported file type. Upload CSV or Excel.")
