"""Plotly chart builders that use only columns present in the dataset."""
import plotly.express as px
import pandas as pd

def categorical_bar(data, category_column, value_column, title=None, top_n=12):
    if category_column not in data or value_column not in data:
        return None
    grouped = (data.groupby(category_column, dropna=False)[value_column]
               .sum().sort_values(ascending=False).head(top_n).reset_index())
    if grouped.empty:
        return None
    return px.bar(grouped, x=category_column, y=value_column,
                  title=title or f"{value_column} by {category_column}")

def time_series_line(data, date_column, value_column, title=None):
    if date_column not in data or value_column not in data:
        return None
    frame = data[[date_column, value_column]].copy()
    frame[date_column] = pd.to_datetime(frame[date_column], errors="coerce")
    frame[value_column] = pd.to_numeric(frame[value_column], errors="coerce")
    frame = frame.dropna()
    if frame.empty:
        return None
    trend = frame.set_index(date_column)[value_column].resample("ME").sum().reset_index()
    return px.line(trend, x=date_column, y=value_column,
                   markers=True, title=title or f"{value_column} over time")
