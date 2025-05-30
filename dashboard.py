import streamlit as st
import pandas as pd
import altair as alt
import gspread
from google.oauth2 import service_account

# === Google Sheets Authentication using Streamlit Secrets ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = st.secrets["gcp_service_account"]
creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(creds)

# === Load Sheets ===
summary_sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1h1kYv7ffSS1tJ3GCn2UTzEuK12Nw_Jq7s17gV3x8QAE").worksheet("Summary")
satisfaction_sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1NwQmL6JlD5AdsScnGcqvfx1-jlC6syQWZxhZ0mRMmfA").sheet1
wildspotter_sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1lutxDE5-9mvywh6zhGUCsImkGO0USor05lBsTgRXJ3s").sheet1
strategic_sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1S-g238RAuZk4ZSa-gUoQNonHlAv6KXCXQDRS88tIzwE").sheet1

# === Volunteer Summary Processing ===
summary_df = pd.DataFrame(summary_sheet.get_all_records())
summary_df = summary_df.set_index("Metric")
value_row = summary_df.loc["Value"]

# KPI Values
kpi_cards = {
    "Total Volunteers": float(summary_df.loc["Volunteers"]["Total"]),
    "Total Hours": float(summary_df.loc["Hours"]["Total"]),
    "RTF Volunteers": float(summary_df.loc["RTF Volunteers"]["Total"]),
    "RTF Hours": float(summary_df.loc["RTF Hours"]["Total"]),
    "RTF Acreage": float(summary_df.loc["RTF Acreage"]["Total"]),
    "Total Value ($)": float(summary_df.loc["Value"]["Total"])
}

monthly_value = {str(i): float(value_row.get(str(i), 0.0)) for i in range(1, 13)}
month_map = {str(i): pd.Timestamp(f"2025-{i:02d}-01").strftime('%b') for i in range(1, 13)}
monthly_value = {month_map[k]: v for k, v in monthly_value.items()}

# === WildSpotter Summary ===
wildspotter_df = pd.DataFrame(wildspotter_sheet.get_all_records())
total_sightings = len(wildspotter_df)
most_common_species = wildspotter_df["Species Name"].value_counts().idxmax()
top_species_count = wildspotter_df["Species Name"].value_counts().max()

# === Satisfaction Summary ===
satisfaction_df = pd.DataFrame(satisfaction_sheet.get_all_records())
satisfaction_df['Timestamp'] = pd.to_datetime(satisfaction_df['Timestamp'], errors='coerce')
satisfaction_df['Month'] = satisfaction_df['Timestamp'].dt.to_period('M').astype(str)
likert_columns = [col for col in satisfaction_df.columns if col.startswith("I") or "positively" in col]
satisfaction_long = satisfaction_df.melt(
    id_vars=["Timestamp", "Event Title", "Month"],
    value_vars=likert_columns,
    var_name="Statement",
    value_name="Score"
)
score_map = {"Strongly Disagree": 1, "Disagree": 2, "Neutral": 3, "Agree": 4, "Strongly Agree": 5}
satisfaction_long['Score'] = satisfaction_long['Score'].map(score_map)
satisfaction_by_event = satisfaction_long.groupby(["Event Title", "Statement"]).Score.mean().reset_index()
satisfaction_by_month = satisfaction_long.groupby(["Month", "Statement"]).Score.mean().reset_index()

# === Strategic Plan Summary ===
strategic_df = pd.DataFrame(strategic_sheet.get_all_records())
strategic_kpis = {
    "Total Responses": len(strategic_df),
    "% Facing Barriers": round(100 * strategic_df["Do you face any barriers to accessing the park?"].str.lower().eq("yes").mean(), 2),
    "Accessibility Score": round(strategic_df["Rate the accessibility of the park (1-5)"].astype(float).mean(), 2),
    "Visit Frequency Score": round(strategic_df["Rate how often you visit the park (1-5)"].astype(float).mean(), 2),
}
strategic_by_zip = strategic_df.groupby("Zip Code")["Rate the accessibility of the park (1-5)"].mean().reset_index()
strategic_by_age = strategic_df.groupby("Age Range")["Rate how often you visit the park (1-5)"].mean().reset_index()

# === Streamlit Layout ===
st.set_page_config(page_title="Volunteer Dashboard", layout="wide")

st.sidebar.title("Dashboard Pages")
page = st.sidebar.radio("Select a Page", ["Volunteer Programs", "Invasive Plant Removal", "Strategic Plan", "Milestones and Summary"])

st.title(page)

if page == "Volunteer Programs":
    st.subheader("Key Performance Indicators")
    kpi_cols = st.columns(len(kpi_cards))
    for idx, (label, value) in enumerate(kpi_cards.items()):
        kpi_cols[idx].metric(label, f"{value:,.2f}")

    st.subheader("Monthly Volunteer Time Value ($)")
    monthly_df = pd.DataFrame({"Month": list(monthly_value.keys()), "Total Value ($)": list(monthly_value.values())})
    bar_chart = alt.Chart(monthly_df).mark_bar().encode(
        x=alt.X("Month", sort=list(monthly_value.keys())),
        y="Total Value ($)",
        tooltip=["Month", "Total Value ($)"]
    ).properties(height=300)
    st.altair_chart(bar_chart, use_container_width=True)

    st.subheader("Volunteer Satisfaction by Event Title")
    st.dataframe(satisfaction_by_event)

    st.subheader("Volunteer Satisfaction by Month")
    st.dataframe(satisfaction_by_month)

elif page == "Invasive Plant Removal":
    st.subheader("Invasive Plant Removal KPIs")
    invasive_kpis = {
        "RTF Volunteer Count": float(summary_df.loc["RTF Volunteers"]["Total"]),
        "RTF Volunteer Hours": float(summary_df.loc["RTF Hours"]["Total"]),
        "RTF Acreage Removed": float(summary_df.loc["RTF Acreage"]["Total"]),
        "RTF Value ($)": float(summary_df.loc["RTF Value"]["Total"] if "RTF Value" in summary_df.index else 0.0),
    }
    kpi_cols = st.columns(len(invasive_kpis))
    for idx, (label, value) in enumerate(invasive_kpis.items()):
        kpi_cols[idx].metric(label, f"{value:,.2f}")

    st.subheader("WildSpotter Summary")
    st.metric("Total Sightings", total_sightings)
    st.metric("Most Common Species", f"{most_common_species} ({top_species_count})")

    st.subheader("Most Common Species Chart")
    species_chart = wildspotter_df["Species Name"].value_counts().reset_index()
    species_chart.columns = ["Species", "Count"]
    bar_chart = alt.Chart(species_chart.head(10)).mark_bar().encode(
        x=alt.X("Species", sort="-y"),
        y="Count",
        tooltip=["Species", "Count"]
    ).properties(height=300)
    st.altair_chart(bar_chart, use_container_width=True)

    st.subheader("WildSpotter Sightings Table")
    st.dataframe(wildspotter_df)

elif page == "Strategic Plan":
    st.subheader("Strategic Plan Pillar 1 KPIs")
    cols = st.columns(len(strategic_kpis))
    for idx, (label, value) in enumerate(strategic_kpis.items()):
        suffix = "%" if "%" in label else ""
        cols[idx].metric(label, f"{value}{suffix}")

    st.subheader("Accessibility by Zip Code")
    st.bar_chart(strategic_by_zip.rename(columns={"Rate the accessibility of the park (1-5)": "Accessibility"}).set_index("Zip Code"))

    st.subheader("Visit Frequency by Age Range")
    st.bar_chart(strategic_by_age.rename(columns={"Rate how often you visit the park (1-5)": "Visit Frequency"}).set_index("Age Range"))

elif page == "Milestones and Summary":
    st.subheader("Milestone Summary")
    st.write("Milestone tracking, progress toward goals, and downloadable reports")
    st.download_button("Download Summary Report (CSV)", data=summary_df.reset_index().to_csv(index=False), file_name="summary_report.csv")
    st.download_button("Download WildSpotter Data", data=wildspotter_df.to_csv(index=False), file_name="wildspotter_data.csv")
