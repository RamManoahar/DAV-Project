# Small Business Intelligence AI Dashboard

This repository follows the requested project-stage folder structure.

## Run
Open a terminal in `Interactive Dashboard` and run:

```powershell
pip install -r ../requirements.txt
streamlit run app.py
```

The app shows a project overview before upload (no demo figures). After upload, it adapts its KPIs, filters, headings, and visualizations to the dataset.

Optional test files are in `Data Collection/`; the app does not load them automatically.

## Power BI hand-off

After uploading a dataset, open the Power BI tab and download the Power BI ZIP package. It contains the cleaned transaction data and available summary tables for import into Power BI Desktop. See `POWER_BI_INTEGRATION.md` for report creation and secure embedding. Native PBIX publishing and automatic Power BI Service refresh require the user's Power BI tenant/workspace setup.


## AI provider setup
The sidebar lets you choose **Google Gemini** or **OpenAI**. Paste the matching API key into the password field and use the AI Advisor or Ask Your Data tabs. Gemini uses `gemini-3.8-flash`; OpenAI uses `gpt-5.5` by default. The key is held only in the current Streamlit session unless you separately configure an environment variable. Do not commit API keys to GitHub. AI calls receive computed aggregate summaries, not the raw uploaded rows. API access, billing, quotas and model availability depend on the provider account.
