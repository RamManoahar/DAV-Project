# Project Proposal: Small Business Intelligence & Advisory Dashboard

## Problem
Small businesses often store sales and operational information in CSV or Excel files but may not have an easy way to clean, analyse, and visualize those records.

## Proposed solution
Build BizInsight AI, a dashboard that accepts a user's own business dataset and adapts its analysis to the fields available in that dataset.

## Objectives
- Collect data from uploaded CSV and Excel files.
- Inspect missing values, duplicate rows, and data types.
- Detect common business fields such as dates, sales, quantities, products, customers, and locations.
- Calculate only metrics supported by the uploaded data.
- Create relevant filters and visualizations dynamically.
- Provide optional Gemini AI explanations based on computed summaries.

## Scope and limitations
The application is an academic prototype. Automatic field detection may need user review for unusual column names. Profit is not calculated unless suitable profit or cost information exists. The application must not invent unavailable business values. Gemini output is advisory and should be verified.

## Workflow
Upload → Data collection → Data cleaning → Data analysis → Data visualization → Interactive dashboard → Optional AI advisory.
