# Demo script for faculty presentation

## 1. Introduction
“Our project is the Small Business Intelligence & Advisory Dashboard. It helps small businesses and startups explore sales performance, understand profit and cost patterns, and receive AI-assisted recommendations.”

## 2. Demonstrate the dashboard
- Open the dashboard using `streamlit run app.py`.
- Point out the revenue, estimated profit, costs, margin and units KPIs.
- Show the monthly trend and product chart.
- Open Data Quality & Explorer and show the cleaned dataset and CSV download.
- Upload a CSV or Excel file with a Sales/Revenue column to demonstrate user-provided data.

## 3. Explain the AI architecture
“Python and Pandas calculate the metrics from the uploaded dataset. The Gemini API receives a compact summary of those computed results and generates explanations and recommendations. The chatbot uses the same selected-data summary to answer business questions.”

## 4. Live AI demo
- Enter a Gemini API key in the sidebar (do not show or share the key on screen).
- Click “Generate AI recommendations”.
- Open the chat tab and ask: “Which business area should I investigate first, and what metrics should I monitor next month?”
- Explain that Gemini calls require internet access and valid API access/quota.

## 5. Closing
“The current version is an academic prototype. Future work includes secure login, database integration, forecasting, anomaly detection, industry-specific templates, and deployment.”

## Honesty note
Do not claim that AI is running if no API key is configured. Without a key, the data calculations, charts, cleaning, and rule-based observations still work, but Gemini-generated responses require a configured key and successful API request.
