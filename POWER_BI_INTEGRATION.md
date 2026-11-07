# Power BI integration status and usage

The Streamlit application includes a **Power BI-style executive dashboard** in its Power BI tab. It calculates KPI cards and dataset-aware charts from the uploaded and filtered dataset. This is a Streamlit/Plotly dashboard, not a native Power BI `.pbix` report.

## Export to Power BI Desktop
1. Run the Streamlit app and upload a CSV/Excel dataset.
2. Open the **Power BI** tab and choose **Download Power BI data package (ZIP)**.
3. Extract the ZIP.
4. In Power BI Desktop choose **Home > Get Data > Text/CSV** and import `Transactions.csv`.
5. Import optional summary tables as needed and build or customise the report.

A native `.pbix` file is not included. Publishing and secure embedding require a Microsoft work/school account with Power BI Service access, an authorised workspace, and suitable licensing. The app can display a published report only after `POWERBI_EMBED_URL` is configured with an authorised embed URL. Do not use public embedding for confidential business data.
