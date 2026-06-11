import streamlit as st


def validate_columns(df, required_cols):
    for col in required_cols:
        if col not in df.columns:
            st.error(f"❌ Missing column: {col}")
            st.stop()


def validate_positive(value, name):
    if value <= 0:
        st.warning(f"{name} must be greater than 0")
        st.stop()


def validate_not_empty(value, name):
    if not value:
        st.warning(f"{name} cannot be empty")
        st.stop()
