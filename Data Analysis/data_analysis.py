"""Dataset-agnostic analysis helpers for the dashboard."""
import pandas as pd

def numeric_summary(data):
    """Return descriptive statistics for numeric columns actually present."""
    numeric = data.select_dtypes(include="number")
    if numeric.empty:
        return pd.DataFrame()
    return numeric.describe().T

def categorical_summary(data, column, value_column=None, top_n=10):
    """Count rows or aggregate a numeric measure by a categorical column."""
    if column not in data.columns:
        raise KeyError(f"Column not found: {column}")
    if value_column and value_column in data.columns:
        result = data.groupby(column, dropna=False)[value_column].sum()
        return result.sort_values(ascending=False).head(top_n).reset_index()
    return data[column].value_counts(dropna=False).head(top_n).rename_axis(column).reset_index(name="records")

def date_trend(data, date_column, value_column, frequency="ME"):
    """Aggregate a numeric measure over a detected date column."""
    if date_column not in data or value_column not in data:
        raise KeyError("Date or value column is unavailable.")
    frame = data[[date_column, value_column]].copy()
    frame[date_column] = pd.to_datetime(frame[date_column], errors="coerce")
    frame[value_column] = pd.to_numeric(frame[value_column], errors="coerce")
    frame = frame.dropna()
    if frame.empty:
        return pd.DataFrame(columns=[date_column, value_column])
    return (frame.set_index(date_column)[value_column]
            .resample(frequency).sum().reset_index())
