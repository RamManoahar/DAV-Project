import os, io, json, re, hashlib, sys, zipfile
from pathlib import Path

# Allow the dashboard to use the project's stage-wise modules.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
for module_folder in ["Data Collection", "Data Cleaning", "Data Analysis", "Data Visualization"]:
    folder_path = str(PROJECT_ROOT / module_folder)
    if folder_path not in sys.path:
        sys.path.insert(0, folder_path)

from data_collection import load_business_data
from data_cleaning import clean_business_data
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

try:
    from google import genai
except Exception:
    genai = None

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

st.set_page_config(page_title="BizInsight AI | Universal Analytics", page_icon="📊", layout="wide")
st.markdown("""<style>
.block-container{padding-top:1.5rem}.metric-note{color:#64748b;font-size:.85rem}
div[data-testid='stMetric']{background:#f8fafc;border:1px solid #e2e8f0;padding:13px;border-radius:12px}
</style>""", unsafe_allow_html=True)
st.title("📊 BizInsight AI — Universal Business Analytics")
st.caption("Upload your own business dataset. The dashboard adapts its metrics, filters, chart titles and visualizations to the columns and values in that file.")

# ---------- Input file handling ----------
def read_file(file):
    return load_business_data(file)

with st.sidebar:
    st.header("🧭 Workspace")
    upload=st.file_uploader("Upload CSV or Excel", type=["csv","xlsx","xls"])
    st.caption("Upload a CSV or Excel file to start analysing your own data. No sample or demo data is loaded.")
    st.divider(); st.subheader("✨ AI provider (optional)")
    ai_provider = st.selectbox("Choose AI provider", ["Google Gemini", "OpenAI"], key="ai_provider")
    if ai_provider == "Google Gemini":
        api_key = st.text_input("Gemini API key", type="password", key="gemini_api_key",
                                help="Paste your Google AI Studio API key. It is used only for this app session.")
        model = st.selectbox("Gemini model", ["gemini-3.8-flash"], key="gemini_model")
        openai_api_key = ""
        openai_model = ""
    else:
        openai_api_key = st.text_input("OpenAI API key", type="password", key="openai_api_key",
                                       help="Paste your OpenAI API key. It is used only for this app session.")
        openai_model = st.selectbox("OpenAI model", ["gpt-5.5"], key="openai_model")
        api_key = ""
        model = ""
    st.caption("Select a provider and paste its matching API key. Keys are not saved to project files or sent to GitHub.")

if not upload:
    st.markdown("## Your business data, automatically understood")
    st.write(
        "BizInsight AI is a data analytics platform. It does not display made-up business numbers "
        "before you upload a file. Once you upload a CSV or Excel dataset, the workspace is built "
        "from that dataset's actual columns and records."
    )
    st.info("👈 Upload a CSV or Excel file from the Workspace panel to begin. No demo dataset is used.")
    st.markdown("### What changes automatically after upload?")
    overview_cols = st.columns(3)
    overview_items = [
        ("🧠 Data understanding", "Detects likely dates, amounts, quantities, products, customers, locations and other available fields."),
        ("📌 Dataset-based KPIs", "Shows only metrics that can be calculated from the uploaded data. Missing fields are not invented."),
        ("🎛️ Relevant filters", "Creates filters only for dimensions that actually exist in your dataset."),
        ("📊 Adaptive visualizations", "Selects charts and chart headings from the available dimensions and numeric measures."),
        ("🧹 Data quality", "Reports duplicate rows, missing values, data types and a cleaned-data export."),
        ("✨ AI business insights", "Gemini or OpenAI can explain computed summaries and limitations when the matching API key is supplied.")
    ]
    for i, (heading, body) in enumerate(overview_items):
        with overview_cols[i % 3]:
            st.markdown(f"#### {heading}")
            st.write(body)
    st.markdown("### Demo dashboard preview")
    st.caption("ILLUSTRATIVE DEMO DATA — these example charts explain the dashboard layout; they are not real business results.")
    demo1, demo2 = st.columns(2)
    with demo1:
        demo_months = pd.DataFrame({"Month": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"], "Illustrative revenue": [42, 48, 45, 57, 62, 68]})
        st.plotly_chart(px.line(demo_months, x="Month", y="Illustrative revenue", markers=True, title="Illustrative monthly revenue trend"), use_container_width=True)
    with demo2:
        demo_categories = pd.DataFrame({"Category": ["Electronics", "Fashion", "Home", "Beauty"], "Illustrative sales": [38, 30, 22, 10]})
        st.plotly_chart(px.bar(demo_categories, x="Category", y="Illustrative sales", title="Illustrative sales by category"), use_container_width=True)
    demo3, demo4 = st.columns(2)
    with demo3:
        demo_customers = pd.DataFrame({"Customer group": ["New", "Returning"], "Illustrative share": [65, 35]})
        st.plotly_chart(px.pie(demo_customers, names="Customer group", values="Illustrative share", hole=.45, title="Illustrative customer mix"), use_container_width=True)
    with demo4:
        demo_regions = pd.DataFrame({"Region": ["North", "South", "West", "East"], "Illustrative sales": [28, 34, 24, 14]})
        st.plotly_chart(px.bar(demo_regions, x="Region", y="Illustrative sales", title="Illustrative sales by region"), use_container_width=True)
    st.markdown("### How it works")
    st.markdown("**Upload dataset → Detect columns → Clean data → Calculate KPIs → Build relevant filters and charts → Generate insights**")
    st.info("Upload your CSV or Excel file to replace these illustrative previews with analysis calculated from your own data.")
    st.stop()

try:
    raw=read_file(upload)
    source=f"Uploaded file: {upload.name}"
except Exception as e:
    st.error(f"Could not read file: {e}")
    st.stop()

if raw.empty: st.error("The uploaded file has no data rows."); st.stop()
if len(raw.columns)==0: st.error("No columns were found in this file."); st.stop()
# Dataset-specific widget keys prevent stale selections when a different file is uploaded.
dataset_key = hashlib.md5((upload.name + str(upload.size)).encode("utf-8")).hexdigest()[:10]
raw.columns=[str(c).strip() for c in raw.columns]
# Remove completely empty columns and rows; preserve original column names for mapping.
raw=raw.dropna(axis=1,how="all").dropna(axis=0,how="all").copy()
if raw.empty: st.error("No usable rows remain after removing completely empty rows."); st.stop()

# ---------- Semantic field detection ----------
def norm(s): return re.sub(r"[^a-z0-9]+","",str(s).lower())
ALIASES={
 "date":["date","orderdate","transactiondate","purchasedate","invoicedate","createdat","timestamp","shipdate","datetime","invoicedateutc"],
 "order_id":["orderid","transactionid","invoiceid","invoiceno","orderno","ordernumber","receiptid","ordernumberid","billno","billnumber"],
 "revenue":["revenue","totalrevenue","sales","totalsales","salesamount","amount","totalamount","net sales","grosssales","lineamount","totalprice"],
 "profit":["profit","totalprofit","netprofit","grossprofit","earnings"],
 "cost":["cost","totalcost","makingcost","unitmakingcost","cogs","costofgoods","expenses","expense","totalexpense"],
 "quantity":["quantity","qty","units","unitssold","items sold","itemquantity","count","quantityordered","numberofitems"],
 "unit_price":["unitprice","sellingprice","unitsellingprice","price","saleprice","itemprice","priceeach","unitcostprice"],
 "product":["product","productname","item","itemname","sku","productid","description","stockcode","itemdescription"],
 "category":["category","itemtype","productcategory","department","type"],
 "customer":["customer","customerid","customername","client","clientid","buyer","userid","memberid","accountid"],
 "region":["region","country","state","city","location","area","market","countryname","shippingcountry"],
 "channel":["saleschannel","channel","ordermethod","platform","source"],
 "status":["status","orderstatus","paymentstatus","delivery status"],
 "payment":["paymentmethod","paymenttype","paymethod"],
}

def detect_field(field, columns, data):
    normalized={norm(c):c for c in columns}
    for alias in ALIASES[field]:
        if norm(alias) in normalized: return normalized[norm(alias)]
    # Conservative fuzzy matching only after exact aliases.
    for c in columns:
        nc=norm(c)
        if field=="revenue" and any(x in nc for x in ["revenue","salesamount","totalamount"]): return c
        if field=="cost" and ("cost" in nc or "expense" in nc): return c
        if field=="date" and (nc.endswith("date") or "timestamp" in nc): return c
        if field=="quantity" and ("quantity" in nc or nc.endswith("qty")): return c
    # infer date columns by parse success
    if field=="date":
        for c in columns:
            if "date" in norm(c): return c
    # numeric amount fallback is intentionally not automatic to avoid mapping IDs/years.
    return None

fields=list(ALIASES.keys()); detected={f:detect_field(f,list(raw.columns),raw) for f in fields}
# Numeric/date type hints
for f in ["revenue","profit","cost","quantity","unit_price"]:
    c=detected[f]
    if c is not None:
        vals=pd.to_numeric(raw[c].astype(str).str.replace(r"[₹$,]","",regex=True).str.replace(",","",regex=False),errors="coerce")
        if vals.notna().sum()==0: detected[f]=None

with st.expander("🧩 Automatic column detection — review only if needed", expanded=False):
    st.write("Columns are detected automatically. Open this section only if a field was mapped incorrectly or you want to change it.")
    options=["Not available"]+list(raw.columns)
    chosen={}
    labels={"date":"Date / time","order_id":"Order ID","revenue":"Revenue / sales amount","profit":"Profit (if already calculated)","cost":"Cost / expenses","quantity":"Quantity / units","unit_price":"Unit selling price","product":"Product / item","category":"Category / item type","customer":"Customer ID / name","region":"Region / country / city","channel":"Sales channel","status":"Order status","payment":"Payment method"}
    cols=st.columns(3)
    for i,f in enumerate(fields):
        default=detected[f] if detected[f] in raw.columns else None
        ix=options.index(default) if default else 0
        selected=cols[i%3].selectbox(labels[f],options,index=ix,key=f"map_{dataset_key}_{f}")
        chosen[f]=None if selected=="Not available" else selected

# ---------- Clean and prepare ----------
df, cleaning_report = clean_business_data(raw)
original_rows = cleaning_report["input_rows"]
duplicate_count = cleaning_report["duplicate_rows"]
missing_count = cleaning_report["missing_cells"]
for f in ["revenue","profit","cost","quantity","unit_price"]:
    c=chosen[f]
    if c:
        df[c]=pd.to_numeric(df[c].astype(str).str.replace(r"[₹$,]","",regex=True).str.replace(",","",regex=False),errors="coerce")
if chosen["date"]:
    df[chosen["date"]]=pd.to_datetime(df[chosen["date"]],errors="coerce",dayfirst=False)
# Resolve canonical working fields without overwriting source columns.
work=pd.DataFrame(index=df.index)
for f in ["date","order_id","revenue","profit","cost","quantity","unit_price","product","category","customer","region","channel","status","payment"]:
    c=chosen[f]
    if c: work[f]=df[c]
# Revenue can be derived only when both unit price and quantity exist.
if "revenue" not in work and {"unit_price","quantity"}.issubset(work.columns):
    work["revenue"]=work["unit_price"]*work["quantity"]; revenue_derived=True
else: revenue_derived=False
# Calculate profit only from an explicit profit field or revenue minus cost.
if "profit" not in work and {"revenue","cost"}.issubset(work.columns): work["profit"]=work["revenue"]-work["cost"]
profit_available="profit" in work
# Fill missing numeric values only for analysis; retain original missingness stats.
for c in work.select_dtypes(include="number").columns: work[c]=work[c].replace([np.inf,-np.inf],np.nan)

st.caption(f"**Source:** {source}  ·  **Rows:** {len(work):,} after duplicate removal  ·  **Columns:** {len(raw.columns)}")
# Some retail datasets encode cancellations in invoice/order IDs (for example, InvoiceNo values starting with C).
if "status" not in work and "order_id" in work:
    ids=work["order_id"].astype(str).str.strip()
    if ids.str.match(r"(?i)^C\\d+").mean() > 0.005:
        work["status"]=np.where(ids.str.match(r"(?i)^C\\d+"),"Cancelled / returned","Sale")
if revenue_derived: st.info("Revenue was derived as unit price × quantity because no total revenue column was mapped.")
if "revenue" not in work: st.warning("No reliable revenue field was detected. The dashboard will still analyse available numeric and categorical fields; revenue-specific KPIs and charts are unavailable.")

# Optional filters. By default the complete dataset is analysed.
filter_fields=[f for f in ["region","category","product","channel","status","payment"] if f in work]
filtered=work.copy()
filter_keys=[f"filter_{dataset_key}_{f}" for f in filter_fields]
if filter_fields:
    clear_col, hint_col = st.columns([1, 4])
    if clear_col.button("↺ Clear all filters", key=f"clear_filters_{dataset_key}"):
        for widget_key in filter_keys:
            st.session_state.pop(widget_key, None)
        st.rerun()
    hint_col.caption("All records are included by default. Expand filters only when you want to focus on a subset.")
    with st.expander("🔎 Optional filters — narrow your analysis", expanded=False):
        fcols=st.columns(min(3,len(filter_fields)))
        for i,f in enumerate(filter_fields):
            vals=sorted(work[f].dropna().astype(str).unique().tolist())
            selected=fcols[i%len(fcols)].multiselect(
                labels[f], vals, default=[], key=f"filter_{dataset_key}_{f}",
                placeholder="All values"
            )
            if selected:
                filtered=filtered[filtered[f].astype(str).isin(selected)]
if filtered.empty:
    st.warning("No rows match the selected filters. Use 'Clear all filters' to restore the full dataset.")
    st.stop()

# KPIs selected strictly from available fields
kpis=[]
if "revenue" in filtered: kpis.append(("Total revenue",f"{filtered.revenue.sum():,.2f}"))
if "order_id" in filtered: kpis.append(("Orders",f"{filtered.order_id.nunique():,}"))
else: kpis.append(("Records / transactions",f"{len(filtered):,}"))
if "quantity" in filtered: kpis.append(("Units / quantity",f"{filtered.quantity.sum():,.2f}"))
if "revenue" in filtered and "order_id" in filtered:
    norders=filtered.order_id.nunique(); kpis.append(("Average order value",f"{filtered.revenue.sum()/norders:,.2f}" if norders else "N/A"))
if "customer" in filtered: kpis.append(("Unique customers",f"{filtered.customer.nunique():,}"))
if profit_available: kpis.append(("Profit",f"{filtered.profit.sum():,.2f}"))
if "cost" in filtered: kpis.append(("Total cost",f"{filtered.cost.sum():,.2f}"))
for start in range(0,len(kpis),4):
    metric_cols=st.columns(min(4,len(kpis)-start))
    for col,(label,value) in zip(metric_cols,kpis[start:start+4]): col.metric(label,value)
if "revenue" in filtered and profit_available:
    rev=float(filtered.revenue.sum()); prof=float(filtered.profit.sum())
    st.metric("Profit margin",f"{(prof/rev*100):.2f}%" if rev else "N/A")

# ---------- Dataset-aware visualizations ----------
def chart_theme(fig):
    fig.update_layout(
        template="plotly_white", height=390, margin=dict(l=20,r=20,t=65,b=35),
        title_font=dict(size=18), legend_title_text=""
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#e8edf4", zeroline=False)
    return fig

def top_chart(data, field, metric, title, positive_only=False):
    if field not in data or metric not in data: return False
    plot_data=data.copy()
    if positive_only and "quantity" in plot_data:
        plot_data=plot_data[plot_data.quantity>0]
    plot_data=plot_data.dropna(subset=[field,metric])
    if plot_data.empty: return False
    agg=plot_data.groupby(field,dropna=False)[metric].sum().nlargest(12).reset_index()
    if agg.empty: return False
    fig=px.bar(agg.sort_values(metric),x=metric,y=field,orientation="h",title=title,
               labels={field:field.replace("_"," ").title(),metric:metric.replace("_"," ").title()},
               text_auto=".2s")
    st.plotly_chart(chart_theme(fig),use_container_width=True)
    return True

def show_time_chart(data, date_col, metric, title):
    tmp=data.dropna(subset=[date_col]).copy()
    if tmp.empty: return False
    span=(tmp[date_col].max()-tmp[date_col].min()).days
    freq="D" if span<=45 else "W" if span<=180 else "M"
    tmp["__period"]=tmp[date_col].dt.to_period(freq).astype(str)
    agg=tmp.groupby("__period",as_index=False)[metric].sum().sort_values("__period")
    if len(agg)<2: return False
    fig=px.line(agg,x="__period",y=metric,markers=True,title=title,
                labels={"__period":"Period",metric:metric.replace("_"," ").title()})
    st.plotly_chart(chart_theme(fig),use_container_width=True)
    return True

# Create the navigation tabs before rendering their content.
tab_over, tab_detail, tab_quality, tab_powerbi, tab_ai, tab_chat = st.tabs([
    "📈 Overview", "🔎 Insights & details", "🧹 Data quality", "📊 Power BI", "✨ AI advisor", "💬 Ask your data"
])

with tab_over:
    st.subheader(f"📊 {upload.name} — Dataset overview")
    st.success(f"Analysing **{upload.name}** · All metrics and charts are calculated from the uploaded dataset.")

    chart_count = 0
    rendered = set()
    sales_rows = filtered[filtered.quantity > 0].copy() if "quantity" in filtered else filtered.copy()

    def mark_chart(key):
        nonlocal_dummy = None
        return key not in rendered

    def add_time_chart(date_field, metric, title):
        nonlocal_chart = ("time", date_field, metric)
        if nonlocal_chart in rendered or date_field not in filtered or metric not in filtered:
            return False
        tmp = filtered.dropna(subset=[date_field, metric]).copy()
        if tmp.empty:
            return False
        span = (tmp[date_field].max() - tmp[date_field].min()).days
        freq = "D" if span <= 45 else "W" if span <= 180 else "M"
        tmp["__period"] = tmp[date_field].dt.to_period(freq).astype(str)
        agg = tmp.groupby("__period", as_index=False)[metric].sum().sort_values("__period")
        if len(agg) < 2:
            return False
        fig = px.line(agg, x="__period", y=metric, markers=True, title=title,
                      labels={"__period": "Period", metric: metric.replace("_", " ").title()})
        st.plotly_chart(chart_theme(fig), use_container_width=True)
        rendered.add(nonlocal_chart)
        return True

    def add_dimension_chart(dimension, metric, title):
        key = ("dimension", dimension, metric)
        if key in rendered or dimension not in filtered or metric not in filtered:
            return False
        data = sales_rows.dropna(subset=[dimension, metric]).copy()
        if data.empty or data[dimension].nunique() < 2:
            return False
        agg = data.groupby(dimension, dropna=False)[metric].sum().nlargest(12).sort_values().reset_index()
        if len(agg) < 2:
            return False
        fig = px.bar(agg, x=metric, y=dimension, orientation="h", title=title,
                     labels={dimension: dimension.replace("_", " ").title(), metric: metric.replace("_", " ").title()},
                     text_auto=".2s")
        st.plotly_chart(chart_theme(fig), use_container_width=True)
        rendered.add(key)
        return True

    def add_frequency_chart(dimension, title=None):
        key = ("frequency", dimension)
        if key in rendered or dimension not in filtered:
            return False
        vals = filtered[dimension].dropna().astype(str).value_counts().head(12)
        if len(vals) < 2:
            return False
        plot = vals.sort_values().rename_axis(dimension).reset_index(name="Records")
        fig = px.bar(plot, x="Records", y=dimension, orientation="h",
                     title=title or f"Records by {dimension.replace('_', ' ')}")
        st.plotly_chart(chart_theme(fig), use_container_width=True)
        rendered.add(key)
        return True

    def add_numeric_distribution(field):
        key = ("distribution", field)
        if key in rendered or field not in filtered:
            return False
        vals = pd.to_numeric(filtered[field], errors="coerce").dropna()
        if len(vals) < 2 or vals.nunique() < 2:
            return False
        fig = px.histogram(pd.DataFrame({field: vals}), x=field, nbins=25,
                           title=f"Distribution of {field.replace('_', ' ')}")
        st.plotly_chart(chart_theme(fig), use_container_width=True)
        rendered.add(key)
        return True

    def add_numeric_relationship(xfield, yfield):
        key = ("relationship", xfield, yfield)
        if key in rendered or xfield not in filtered or yfield not in filtered:
            return False
        rel = filtered[[xfield, yfield]].apply(pd.to_numeric, errors="coerce").dropna()
        if len(rel) < 3 or rel[xfield].nunique() < 2 or rel[yfield].nunique() < 2:
            return False
        if len(rel) > 2500:
            rel = rel.sample(2500, random_state=7)
        fig = px.scatter(rel, x=xfield, y=yfield, opacity=.55,
                         title=f"{xfield.replace('_', ' ').title()} vs {yfield.replace('_', ' ').title()}")
        st.plotly_chart(chart_theme(fig), use_container_width=True)
        rendered.add(key)
        return True

    # First create the strongest business-specific charts available.
    if "date" in filtered and "revenue" in filtered:
        chart_count += int(add_time_chart("date", "revenue", "Revenue trend over time"))
    if "date" in filtered and "quantity" in filtered:
        chart_count += int(add_time_chart("date", "quantity", "Quantity trend over time"))

    for dim, metric, title in [
        ("category", "revenue", "Revenue by category"),
        ("product", "revenue", "Top products by revenue"),
        ("region", "revenue", "Revenue by region"),
        ("channel", "revenue", "Revenue by sales channel"),
        ("status", "revenue", "Revenue by order status"),
        ("payment", "revenue", "Revenue by payment method"),
        ("category", "quantity", "Units sold by category"),
        ("product", "quantity", "Units sold by product"),
        ("region", "quantity", "Units sold by region"),
    ]:
        if chart_count >= 5:
            break
        chart_count += int(add_dimension_chart(dim, metric, title))

    # Customer mix / frequency is shown only when a customer field exists.
    if chart_count < 5 and "customer" in filtered:
        if "order_id" in filtered:
            freq = filtered.dropna(subset=["customer", "order_id"]).groupby("customer").order_id.nunique()
            if len(freq) >= 2:
                buckets = pd.cut(freq, [-1, 0, 1, 2, 5, 10, float("inf")],
                                 labels=["0 orders", "1 order", "2 orders", "3–5 orders", "6–10 orders", "11+ orders"])
                dist = buckets.value_counts().sort_index().dropna().rename_axis("Purchase frequency").reset_index(name="Customers")
                if len(dist) >= 2:
                    fig = px.bar(dist, x="Purchase frequency", y="Customers", title="Customer purchase frequency")
                    st.plotly_chart(chart_theme(fig), use_container_width=True)
                    rendered.add(("customer_frequency",)); chart_count += 1
        if chart_count < 5:
            chart_count += int(add_frequency_chart("customer", "Records by customer"))

    # Fill remaining slots with valid dataset-derived charts, never invented values.
    if chart_count < 5:
        for dim in ["region", "category", "product", "channel", "status", "payment", "customer", "order_id"]:
            if chart_count >= 5: break
            chart_count += int(add_frequency_chart(dim))
    if chart_count < 5:
        numeric_fields = [c for c in filtered.select_dtypes(include="number").columns if filtered[c].nunique(dropna=True) > 1]
        for field in numeric_fields:
            if chart_count >= 5: break
            chart_count += int(add_numeric_distribution(field))
        for i, xfield in enumerate(numeric_fields):
            if chart_count >= 5: break
            for yfield in numeric_fields[i+1:]:
                if chart_count >= 5: break
                chart_count += int(add_numeric_relationship(xfield, yfield))

    if chart_count == 0:
        st.info("This dataset does not contain enough variation or usable fields to create meaningful charts. Review the column mappings or upload a richer dataset.")
    elif chart_count < 5:
        st.info(f"This dataset supports {chart_count} meaningful charts. Five charts cannot be produced without inventing or duplicating information; add more relevant columns or records to unlock more visualizations.")
    st.caption(f"{chart_count} meaningful charts generated from {len(filtered):,} filtered records. Charts are selected from available fields; no missing business metrics are fabricated.")

with tab_detail:
    st.subheader(f"Automatic findings — {upload.name}")
    findings=[]
    if "revenue" in filtered:
        findings.append(f"Total revenue in the current selection is **{filtered.revenue.sum():,.2f}**.")
    if "profit" in filtered:
        findings.append(f"Calculated/observed profit totals **{filtered.profit.sum():,.2f}**.")
    if "product" in filtered and "revenue" in filtered:
        g=filtered.groupby("product").revenue.sum().sort_values(ascending=False)
        if len(g): findings.append(f"Highest-revenue product is **{g.index[0]}** ({g.iloc[0]:,.2f}).")
    if "category" in filtered and "revenue" in filtered:
        g=filtered.groupby("category").revenue.sum().sort_values(ascending=False)
        if len(g): findings.append(f"Highest-revenue category is **{g.index[0]}** ({g.iloc[0]:,.2f}).")
    if "customer" in filtered:
        findings.append(f"There are **{filtered.customer.nunique():,}** distinct customers in the current selection.")
    if "date" in filtered and filtered.date.notna().any():
        findings.append(f"Date coverage: **{filtered.date.min().date()}** to **{filtered.date.max().date()}**.")
    if not profit_available: findings.append("Profit is **not available** because neither a profit field nor both revenue and cost were provided.")
    if not findings: findings.append("No standard business metrics could be derived. Review the column mappings and inspect the raw data.")
    for item in findings: st.markdown("• "+item)
    st.subheader("Top categories / dimensions")
    dim=next((x for x in ["product","category","region","channel","payment","status"] if x in filtered),None)
    metric="revenue" if "revenue" in filtered else next(iter(filtered.select_dtypes(include="number").columns),None)
    if dim and metric: top_chart(filtered,dim,metric,f"Top {dim} by {metric}")
    st.subheader("Dataset preview")
    st.dataframe(df.head(1000),use_container_width=True,hide_index=True)

with tab_quality:
    q1,q2,q3=st.columns(3); q1.metric("Original rows",f"{original_rows:,}"); q2.metric("Duplicate rows removed",f"{duplicate_count:,}"); q3.metric("Missing cells before cleaning",f"{missing_count:,}")
    quality=pd.DataFrame({"Column":raw.columns,"Data type":raw.dtypes.astype(str).values,"Missing values":raw.isna().sum().values,"Unique values":raw.nunique(dropna=True).values})
    st.dataframe(quality,use_container_width=True,hide_index=True)
    st.download_button("⬇️ Download cleaned/mapped data",filtered.to_csv(index=False).encode("utf-8-sig"),"bizinsight_filtered_data.csv","text/csv")

with tab_powerbi:
    st.subheader("📊 Power BI-style Business Dashboard")
    st.caption("A compact executive dashboard built from the same cleaned and filtered dataset. This is rendered inside Streamlit; it is not a native .pbix file.")

    # Executive KPI strip
    pbi_kpis = []
    if "revenue" in filtered: pbi_kpis.append(("Total Revenue", f"₹ {filtered.revenue.sum():,.0f}"))
    if profit_available: pbi_kpis.append(("Total Profit", f"₹ {filtered.profit.sum():,.0f}"))
    if "order_id" in filtered: pbi_kpis.append(("Total Orders", f"{filtered.order_id.nunique():,}"))
    else: pbi_kpis.append(("Total Records", f"{len(filtered):,}"))
    if "quantity" in filtered: pbi_kpis.append(("Units Sold", f"{filtered.quantity.sum():,.0f}"))
    if pbi_kpis:
        kcols = st.columns(min(4, len(pbi_kpis)))
        for col, (label, value) in zip(kcols, pbi_kpis[:4]): col.metric(label, value)

    pbi_chart_count = 0
    pbi_left, pbi_right = st.columns(2)
    with pbi_left:
        if "date" in filtered and "revenue" in filtered:
            t = filtered.dropna(subset=["date", "revenue"]).copy()
            if not t.empty:
                t["Period"] = t["date"].dt.to_period("M").astype(str)
                a = t.groupby("Period", as_index=False)["revenue"].sum().sort_values("Period")
                if len(a) > 1:
                    f = px.line(a, x="Period", y="revenue", markers=True, title="Revenue Trend")
                    st.plotly_chart(chart_theme(f), use_container_width=True); pbi_chart_count += 1
        if "category" in filtered and "revenue" in filtered:
            a = filtered.groupby("category", as_index=False)["revenue"].sum().nlargest(10, "revenue")
            if not a.empty:
                f = px.bar(a, x="category", y="revenue", title="Revenue by Category", text_auto=".2s")
                st.plotly_chart(chart_theme(f), use_container_width=True); pbi_chart_count += 1
        elif "product" in filtered and "revenue" in filtered:
            a = filtered.groupby("product", as_index=False)["revenue"].sum().nlargest(10, "revenue")
            if not a.empty:
                f = px.bar(a, x="product", y="revenue", title="Top Products by Revenue", text_auto=".2s")
                st.plotly_chart(chart_theme(f), use_container_width=True); pbi_chart_count += 1
        elif "region" in filtered and "revenue" in filtered:
            a = filtered.groupby("region", as_index=False)["revenue"].sum().nlargest(10, "revenue")
            if not a.empty:
                f = px.bar(a, x="region", y="revenue", title="Revenue by Region", text_auto=".2s")
                st.plotly_chart(chart_theme(f), use_container_width=True); pbi_chart_count += 1
    with pbi_right:
        dimension = "region" if "region" in filtered else "channel" if "channel" in filtered else "status" if "status" in filtered else None
        if dimension and "revenue" in filtered:
            a = filtered.groupby(dimension, as_index=False)["revenue"].sum().nlargest(8, "revenue")
            if not a.empty:
                f = px.pie(a, names=dimension, values="revenue", hole=.48, title=f"Revenue Mix by {dimension.title()}")
                st.plotly_chart(chart_theme(f), use_container_width=True); pbi_chart_count += 1
        if "product" in filtered and "quantity" in filtered:
            a = filtered.groupby("product", as_index=False)["quantity"].sum().nlargest(10, "quantity")
            if not a.empty:
                f = px.bar(a.sort_values("quantity"), x="quantity", y="product", orientation="h", title="Top Products by Units", text_auto=".2s")
                st.plotly_chart(chart_theme(f), use_container_width=True); pbi_chart_count += 1
        elif "profit" in filtered and "category" in filtered:
            a = filtered.groupby("category", as_index=False)["profit"].sum().sort_values("profit")
            if not a.empty:
                f = px.bar(a, x="profit", y="category", orientation="h", title="Profit by Category", text_auto=".2s")
                st.plotly_chart(chart_theme(f), use_container_width=True); pbi_chart_count += 1
        elif "cost" in filtered and "region" in filtered:
            a = filtered.groupby("region", as_index=False)["cost"].sum().nlargest(10, "cost")
            if not a.empty:
                f = px.bar(a, x="region", y="cost", title="Cost by Region", text_auto=".2s")
                st.plotly_chart(chart_theme(f), use_container_width=True); pbi_chart_count += 1

    if pbi_chart_count == 0:
        st.warning("This dataset does not contain enough recognised fields for the dashboard visuals. Review the automatic column mapping above.")
    else:
        st.success(f"Generated {pbi_chart_count} dashboard visuals from the uploaded dataset. Charts depend on available columns.")

    st.divider()
    st.subheader("Power BI Desktop data export")
    st.write("Download the cleaned data and summary tables to import into Power BI Desktop. This export is not a .pbix report.")
    def csv_bytes(frame):
        return frame.to_csv(index=False).encode("utf-8-sig")
    pbi_tables = {"Transactions": filtered.copy()}
    if "date" in filtered and filtered["date"].notna().any():
        dated = filtered.dropna(subset=["date"]).copy(); dated["Month"] = dated["date"].dt.to_period("M").astype(str)
        for metric in [m for m in ["revenue", "profit", "cost", "quantity"] if m in dated]:
            pbi_tables[f"Monthly_{metric.title()}"] = dated.groupby("Month", as_index=False)[metric].sum()
    for dim in [d for d in ["category", "product", "region", "channel", "status", "payment"] if d in filtered]:
        metrics = [m for m in ["revenue", "profit", "quantity", "cost"] if m in filtered]
        pbi_tables[f"By_{dim.title()}"] = filtered.groupby(dim, dropna=False)[metrics].sum().reset_index() if metrics else filtered[dim].astype(str).value_counts().rename_axis(dim).reset_index(name="Records")
    package = io.BytesIO()
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as zf:
        for table_name, table in pbi_tables.items(): zf.writestr(f"PowerBI_Data/{table_name}.csv", csv_bytes(table))
        zf.writestr("PowerBI_Data/README_POWERBI.txt", "Import Transactions.csv into Power BI Desktop using Home > Get Data > Text/CSV. Additional summary tables are optional. This ZIP is a data export, not a PBIX file. Publishing and secure embedding require an authorised Power BI account and workspace.")
    st.download_button("⬇️ Download Power BI data package (ZIP)", data=package.getvalue(), file_name="powerbi_data_package.zip", mime="application/zip")
    st.dataframe(pd.DataFrame([{"Table": name, "Rows": len(table), "Columns": len(table.columns)} for name, table in pbi_tables.items()]), use_container_width=True, hide_index=True)
    embed_url = os.getenv("POWERBI_EMBED_URL", "").strip()
    if embed_url:
        st.markdown("#### Published Power BI report")
        st.components.v1.iframe(embed_url, height=650, scrolling=True)
    else:
        st.caption("Native Power BI Service embedding is not configured. Add an authorised report embed URL after publishing to your workspace.")

# Aggregated context only; raw uploaded rows are never sent to either AI provider.
summary={"rows":int(len(filtered)),"available_fields":list(filtered.columns)}
for c in filtered.select_dtypes(include="number").columns:
    summary[c]={"sum":round(float(filtered[c].sum(skipna=True)),2),"mean":round(float(filtered[c].mean(skipna=True)),2),"min":round(float(filtered[c].min(skipna=True)),2),"max":round(float(filtered[c].max(skipna=True)),2)}
for c in ["product","category","region","channel","status","payment"]:
    if c in filtered:
        summary[f"top_{c}"]=filtered.groupby(c,dropna=False).size().sort_values(ascending=False).head(8).to_dict()
if "date" in filtered and filtered.date.notna().any():
    t=filtered.dropna(subset=["date"]).copy(); t["month"]=t.date.dt.to_period("M").astype(str)
    summary["date_range"]=[str(t.date.min().date()),str(t.date.max().date())]
    if "revenue" in t: summary["monthly_revenue"]=t.groupby("month").revenue.sum().tail(18).round(2).to_dict()

def ai_answer(question):
    prompt=("You are a careful business data analyst. Use only this computed summary; do not invent unavailable metrics or infer causation. "
            "State limitations and give practical recommendations. Summary: "+json.dumps(summary,default=str)+"\nQuestion: "+question)

    if ai_provider == "Google Gemini":
        key=api_key.strip() or os.getenv("GEMINI_API_KEY","").strip()
        if not key: raise ValueError("Select Google Gemini and paste your Gemini API key in the sidebar.")
        if genai is None: raise ValueError("Gemini SDK is missing. Run: pip install -r requirements.txt")
        client=genai.Client(api_key=key)
        response=client.models.generate_content(model=model,contents=prompt)
        return response.text or "No response returned."

    key=openai_api_key.strip() or os.getenv("OPENAI_API_KEY","").strip()
    if not key: raise ValueError("Select OpenAI and paste your OpenAI API key in the sidebar.")
    if OpenAI is None: raise ValueError("OpenAI SDK is missing. Run: pip install -r requirements.txt")
    client=OpenAI(api_key=key)
    response=client.responses.create(model=openai_model, input=prompt)
    return response.output_text or "No response returned."
with tab_ai:
    st.write("The selected AI provider receives computed aggregate statistics only, not the raw uploaded rows.")
    if st.button("✨ Generate business analysis",type="primary"):
        with st.spinner("Analyzing calculated data..."):
            try: st.session_state["biz_ai_report"]=ai_answer("Give an executive summary, key findings, risks/data limitations, five prioritized actions, and KPIs to monitor.")
            except Exception as e: st.error(str(e))
    if st.session_state.get("biz_ai_report"): st.markdown(st.session_state["biz_ai_report"])
with tab_chat:
    st.caption("Ask questions about the uploaded dataset. A valid API key for the selected provider is required.")
    q=st.chat_input("Ask about your business data...")
    if q:
        with st.chat_message("user"): st.write(q)
        with st.chat_message("assistant"):
            try: answer=ai_answer(q); st.markdown(answer)
            except Exception as e: st.error(str(e))

st.divider(); st.caption(f"Academic prototype · Source: {upload.name} · Results are calculated from the uploaded dataset; verify mappings and financial calculations before business decisions.")
