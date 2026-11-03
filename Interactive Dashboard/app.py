import os, io, json, re, hashlib, sys
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
    st.divider(); st.subheader("✨ Gemini AI (optional)")
    api_key=st.text_input("Gemini API key", type="password")
    model=st.selectbox("Model",["gemini-2.5-flash","gemini-2.0-flash"])

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
        ("✨ AI business insights", "Gemini can explain computed summaries and limitations when an API key is supplied.")
    ]
    for i, (heading, body) in enumerate(overview_items):
        with overview_cols[i % 3]:
            st.markdown(f"#### {heading}")
            st.write(body)
    st.markdown("### How it works")
    st.markdown("**Upload dataset → Detect columns → Prepare data → Calculate KPIs → Build relevant filters and charts → Generate insights**")
    st.caption("No sample figures are shown here. All business results will come from the file you upload.")
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
tab_over, tab_detail, tab_quality, tab_ai, tab_chat = st.tabs([
    "📈 Overview", "🔎 Insights & details", "🧹 Data quality", "✨ AI advisor", "💬 Ask your data"
])

with tab_over:
    st.subheader(f"📊 {upload.name} — Dataset overview")
    st.success(f"Analysing **{upload.name}** · KPIs, filters, chart choices and headings are based on the detected fields in this dataset.")

    chart_count=0
    # Split sales and returns when quantity is available; retain the full filtered set for net calculations.
    sales_rows=filtered[filtered.quantity>0].copy() if "quantity" in filtered else filtered.copy()
    return_rows=filtered[filtered.quantity<0].copy() if "quantity" in filtered else filtered.iloc[0:0].copy()

    # The most informative time trend comes first.
    if "date" in filtered and "revenue" in filtered:
        chart_count += int(show_time_chart(sales_rows,"date","revenue","Sales revenue over time"))

    # Pick product/category/region charts only when those dimensions genuinely exist.
    left,right=st.columns(2)
    with left:
        if "product" in filtered and "revenue" in filtered:
            chart_count += int(top_chart(sales_rows,"product","revenue","Top products by sales revenue"))
        elif "category" in filtered and "revenue" in filtered:
            chart_count += int(top_chart(sales_rows,"category","revenue","Revenue by category"))
        elif "region" in filtered and "revenue" in filtered:
            chart_count += int(top_chart(sales_rows,"region","revenue","Revenue by region"))
        elif "category" in filtered and "quantity" in filtered:
            chart_count += int(top_chart(filtered,"category","quantity","Units sold by category"))
    with right:
        if "region" in filtered and "revenue" in filtered and not ("product" not in filtered and "category" not in filtered):
            chart_count += int(top_chart(sales_rows,"region","revenue","Revenue by country / region"))
        elif "category" in filtered and "revenue" in filtered and "product" in filtered:
            chart_count += int(top_chart(sales_rows,"category","revenue","Revenue by category"))
        elif "status" in filtered:
            status_counts=filtered.status.astype(str).value_counts().rename_axis("Status").reset_index(name="Records")
            fig=px.pie(status_counts,names="Status",values="Records",hole=.48,title="Order / transaction status mix")
            st.plotly_chart(chart_theme(fig),use_container_width=True); chart_count+=1
        elif "payment" in filtered:
            pay=filtered.payment.astype(str).value_counts().head(10).rename_axis("Payment").reset_index(name="Transactions")
            fig=px.bar(pay.sort_values("Transactions"),x="Transactions",y="Payment",orientation="h",title="Transactions by payment method")
            st.plotly_chart(chart_theme(fig),use_container_width=True); chart_count+=1

    # Customer, order and returns charts are conditional on the fields actually available.
    extra_left,extra_right=st.columns(2)
    with extra_left:
        if "customer" in filtered and "order_id" in filtered:
            freq=filtered.dropna(subset=["customer","order_id"]).groupby("customer").order_id.nunique()
            buckets=pd.cut(freq,[0,1,2,5,10,100000],labels=["1 order","2 orders","3–5 orders","6–10 orders","10+ orders"])
            dist=buckets.value_counts().sort_index().rename_axis("Purchase frequency").reset_index(name="Customers")
            fig=px.bar(dist,x="Purchase frequency",y="Customers",title="Customer purchase frequency")
            st.plotly_chart(chart_theme(fig),use_container_width=True); chart_count+=1
        elif "quantity" in filtered and "unit_price" in filtered:
            rel=sales_rows.dropna(subset=["quantity","unit_price"])
            if len(rel)>1:
                fig=px.scatter(rel.sample(min(2500,len(rel)),random_state=7),x="unit_price",y="quantity",
                               title="Unit price vs quantity",opacity=.55)
                st.plotly_chart(chart_theme(fig),use_container_width=True); chart_count+=1
    with extra_right:
        if len(return_rows) and "revenue" in return_rows:
            ret=return_rows.copy()
            dim="product" if "product" in ret else "region" if "region" in ret else None
            if dim:
                chart_count += int(top_chart(ret,dim,"revenue","Largest return / negative-sales values"))
            else:
                st.metric("Return / negative-quantity records",f"{len(ret):,}")
                chart_count+=1
        elif "status" in filtered and "revenue" in filtered:
            status_rev=filtered.groupby("status",dropna=False).revenue.sum().reset_index()
            fig=px.bar(status_rev,x="status",y="revenue",title="Revenue by order status")
            st.plotly_chart(chart_theme(fig),use_container_width=True); chart_count+=1
        elif "date" in filtered:
            dates=filtered.dropna(subset=["date"]).copy()
            if len(dates):
                dates["__weekday"]=dates.date.dt.day_name()
                weekday=dates.groupby("__weekday").size().reindex(["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]).dropna().rename("Records").reset_index()
                fig=px.bar(weekday,x="__weekday",y="Records",title="Transactions by weekday")
                st.plotly_chart(chart_theme(fig),use_container_width=True); chart_count+=1

    # Generic numeric distribution only as a fallback when semantic charts are not possible.
    if chart_count==0:
        nums=filtered.select_dtypes(include="number").columns.tolist()
        if nums:
            fig=px.histogram(filtered,x=nums[0],title=f"Distribution of {nums[0]}",nbins=30)
            st.plotly_chart(chart_theme(fig),use_container_width=True)
        else:
            st.info("This dataset does not contain enough usable numeric or date fields for a chart. Open column detection to review the mapping.")

    st.caption(f"Showing charts derived from {len(filtered):,} filtered records and the fields available in this dataset. No unavailable metric is fabricated.")

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

# Aggregated context only; raw rows are never sent to Gemini.
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

def gemini_answer(question):
    key=api_key.strip() or os.getenv("GEMINI_API_KEY","").strip()
    if not key: raise ValueError("Add your Gemini API key in the sidebar or set GEMINI_API_KEY.")
    if genai is None: raise ValueError("Install google-genai: pip install google-genai")
    client=genai.Client(api_key=key)
    prompt=("You are a careful business data analyst. Use only this computed summary; do not invent unavailable metrics or infer causation. "
            "State limitations and give practical recommendations. Summary: "+json.dumps(summary,default=str)+"\nQuestion: "+question)
    response=client.models.generate_content(model=model,contents=prompt)
    return response.text or "No response returned."
with tab_ai:
    st.write("Gemini receives computed aggregate statistics only, not the raw uploaded rows.")
    if st.button("✨ Generate business analysis",type="primary"):
        with st.spinner("Analyzing calculated data..."):
            try: st.session_state["biz_ai_report"]=gemini_answer("Give an executive summary, key findings, risks/data limitations, five prioritized actions, and KPIs to monitor.")
            except Exception as e: st.error(str(e))
    if st.session_state.get("biz_ai_report"): st.markdown(st.session_state["biz_ai_report"])
with tab_chat:
    st.caption("Ask questions about the uploaded dataset. Gemini API key is required.")
    q=st.chat_input("Ask about your business data...")
    if q:
        with st.chat_message("user"): st.write(q)
        with st.chat_message("assistant"):
            try: answer=gemini_answer(q); st.markdown(answer)
            except Exception as e: st.error(str(e))

st.divider(); st.caption(f"Academic prototype · Source: {upload.name} · Results are calculated from the uploaded dataset; verify mappings and financial calculations before business decisions.")
