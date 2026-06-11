import pandas as pd
from io import BytesIO
import streamlit as st


def read_excel_safe(file):
    try:
        df = pd.read_excel(file)
        df.columns = df.columns.str.strip().str.upper()
        return df
    except Exception:
        st.error("❌ Invalid Excel file")
        st.stop()


def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()
