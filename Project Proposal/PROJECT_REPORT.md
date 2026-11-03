# Project Report: Small Business Intelligence & Advisory Dashboard

## Abstract
Small businesses and early-stage startups often store sales and expense records but may lack accessible tools to interpret them. This project provides a dashboard for uploading business data, cleaning common data-quality issues, calculating key performance indicators, visualising patterns, and requesting Gemini AI explanations and recommendations.

## Problem statement
Business owners may find it difficult to transform raw transaction records into useful decisions. The system aims to make basic business analytics accessible through a simple interactive application.

## Objectives
1. Accept business data in CSV or Excel format.
2. Clean duplicate rows and handle missing/numeric/date values.
3. Calculate revenue, cost, estimated profit, profit margin and units.
4. Visualise trends and product performance.
5. Produce deterministic rule-based observations.
6. Use Gemini to interpret computed summaries and answer questions about the selected data.

## Technology stack
- Python: application logic
- Pandas: data cleaning, aggregation and calculations
- Streamlit: user interface
- Plotly: interactive visualisations
- Google Gen AI Python SDK: Gemini API integration

## System workflow
1. User uploads a dataset or uses the included demo data.
2. Application standardises common column names.
3. Data is cleaned and derived metrics are calculated.
4. Dashboard displays KPIs, filters and charts.
5. Python creates an aggregate summary.
6. Gemini receives that summary and produces recommendations or a chat response.

## Modules
- Data input and column normalisation
- Data cleaning and validation
- KPI calculation and analysis
- Interactive visualisation
- Rule-based business insights
- Gemini AI advisor and chatbot
- Cleaned data export

## Limitations
This is a prototype and does not include authentication, persistent database storage, production-grade validation, or tenant isolation. AI responses may be inaccurate. Data should be authorised for use and sensitive information should be removed before sending summaries to an external AI service.

## Future enhancements
Secure login and roles, database support, time-series forecasting, anomaly detection, industry-specific KPI templates, deployment, audit logs, and more robust data validation.
