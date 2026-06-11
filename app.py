import streamlit as st
import pandas as pd

from utils.billing_logic import fill_target_fast, combine_items
from utils.file_handler import read_excel_safe, to_excel
from utils.validation import validate_columns, validate_positive, validate_not_empty

st.set_page_config(page_title="Billing System", layout="wide")

st.sidebar.title("📊 Smart Controls")
st.sidebar.info("Generate and update bills easily")

st.title("🧾 Smart Billing & Stock Management System")

tab1, tab2 = st.tabs(["📄 Generate Bills", "🔄 Update Items"])

# =========================================================
# TAB 1: GENERATE BILLS
# =========================================================
with tab1:

    st.header("📄 Generate Bills")

    bills_file = st.file_uploader("Upload Bills File", type=["xlsx"], key="bills_tab1")
    stock_file = st.file_uploader("Upload Stock File", type=["xlsx"], key="stock_tab1")

    if "bills_generated" not in st.session_state:
        st.session_state["bills_generated"] = False

    if st.button("🚀 Generate Bills"):

        if not bills_file or not stock_file:
            st.error("Upload both files")
            st.stop()

        bills = read_excel_safe(bills_file)
        stock = read_excel_safe(stock_file)

        # VALIDATION
        validate_columns(bills, ["DATE", "AMOUNT", "BILL NO", "PARTICULAR"])
        validate_columns(stock, ["ITEM NAME", "PRICE", "QTY"])

        # CLEAN DATA
        bills["AMOUNT"] = pd.to_numeric(bills["AMOUNT"], errors="coerce").fillna(0)

        stock["QTY"] = pd.to_numeric(stock["QTY"], errors="coerce").fillna(0)
        stock["PRICE"] = pd.to_numeric(stock["PRICE"], errors="coerce").fillna(0)

        if "BILL NO" not in bills.columns:
            st.warning("BILL NO not found, auto-generating...")
            bills["BILL NO"] = range(1, len(bills) + 1)

        if bills["BILL NO"].duplicated().any():
            st.error("Duplicate BILL NO found!")
            st.stop()

        output = []
        progress = st.progress(0)

        for idx, bill in bills.iterrows():

            date = pd.to_datetime(bill["DATE"]).strftime("%d-%m-%Y")
            total = int(round(bill["AMOUNT"]))
            bill_no = bill["BILL NO"]
            particular = bill.get("PARTICULAR", "")

            selected, achieved = fill_target_fast(stock, total)

            for item in selected:
                stock.at[item["INDEX"], "QTY"] -= 1

            combined = combine_items(selected)

            for item in combined:
                output.append({
                    "DATE": date,
                    "BILL NO": bill_no,
                    "PARTICULAR": particular,
                    "ITEM NAME": item["ITEM NAME"],
                    "QUANTITY": item["QUANTITY"],
                    "PRICE": item["PRICE"],
                    "AMOUNT": item["AMOUNT"]
                })

            if achieved != total:
                output.append({
                    "DATE": date,
                    "BILL NO": bill_no,
                    "PARTICULAR": particular,
                    "ITEM NAME": "UNMATCHED",
                    "QUANTITY": "",
                    "PRICE": "",
                    "AMOUNT": total - achieved
                })

            output.append({})
            progress.progress((idx + 1) / len(bills))

        output_df = pd.DataFrame(output)
        output_df["AMOUNT"] = pd.to_numeric(output_df["AMOUNT"], errors="coerce").fillna(0)

        # ACCOUNT TYPE
        output_df["ACCOUNT_TYPE"] = output_df["PARTICULAR"].apply(
            lambda x: "Cash" if "CASH" in str(x).upper()
            else "Sundry Debtors" if "DEBTOR" in str(x).upper() or "SUNDRY" in str(x).upper()
            else "Other"
        )

        remaining_stock = stock[stock["QTY"] > 0]

        st.session_state["output_df"] = output_df
        st.session_state["remaining_stock"] = remaining_stock
        st.session_state["bills_generated"] = True

    # DASHBOARD
    if st.session_state["bills_generated"]:

        st.success("✅ Bills Generated Successfully")

        output_df = st.session_state["output_df"]
        remaining_stock = st.session_state["remaining_stock"]

        st.subheader("📊 Dashboard")

        clean_df = output_df.copy()
        clean_df["AMOUNT"] = pd.to_numeric(clean_df["AMOUNT"], errors="coerce").fillna(0)
        clean_df["QUANTITY"] = pd.to_numeric(clean_df["QUANTITY"], errors="coerce").fillna(0)

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Revenue", f"₹ {int(clean_df['AMOUNT'].sum())}")
        col2.metric("Bills", clean_df["BILL NO"].nunique())
        col3.metric("Items", int(clean_df["QUANTITY"].sum()))
        col4.metric("Stock Left", int(remaining_stock["QTY"].sum()))

        st.dataframe(output_df)
        st.dataframe(remaining_stock)

        st.download_button("Download Bills", to_excel(output_df), "output.xlsx")
        st.download_button("Download Stock", to_excel(remaining_stock), "stock.xlsx")


# =========================================================
# TAB 2: UPDATE ITEMS (FIXED LOGIC)
# =========================================================
with tab2:

    st.header("🔄 Update Items & Regenerate")

    use_generated = st.checkbox("Use generated data from Tab 1")

    if use_generated:
        if "output_df" in st.session_state:
            output_df = st.session_state["output_df"]
            stock_df = st.session_state["remaining_stock"]
            st.success("Using generated data")
        else:
            st.error("Generate bills first")
            st.stop()
    else:
        output_file = st.file_uploader("Upload Output File", type=["xlsx"], key="output_tab2")
        stock_file2 = st.file_uploader("Upload Stock File", type=["xlsx"], key="stock_tab2")

        if not output_file or not stock_file2:
            st.warning("Upload both files")
            st.stop()

        output_df = read_excel_safe(output_file)
        stock_df = read_excel_safe(stock_file2)

    output_df["AMOUNT"] = pd.to_numeric(output_df["AMOUNT"], errors="coerce").fillna(0)

    item_name = st.text_input("Item Name").strip().upper()
    old_price = st.number_input("Old Price", value=0.0)
    new_price = st.number_input("New Price", value=0.0)

    if st.button("🔄 Update & Regenerate"):

        validate_not_empty(item_name, "Item Name")
        validate_positive(old_price, "Old Price")
        validate_positive(new_price, "New Price")

        final_output = []

        for bill_no, group in output_df.groupby("BILL NO"):

            group = group.dropna(subset=["ITEM NAME"])
            if group.empty:
                continue

            date = group.iloc[0]["DATE"]
            particular = group.iloc[0].get("PARTICULAR", "")
            original_total = int(group["AMOUNT"].sum())

            remaining_items = []

            for _, row in group.iterrows():

                # ✅ FIXED FLOAT COMPARISON (IMPORTANT FIX)
                if (
                    row["ITEM NAME"] == item_name
                    and abs(float(row["PRICE"]) - old_price) < 0.01
                ):
                    stock_df.loc[len(stock_df)] = {
                        "ITEM NAME": item_name,
                        "QTY": float(row.get("QUANTITY", 0)),
                        "PRICE": float(new_price)
                    }

                else:
                    remaining_items.append(row)

            current_total = sum(
                int(r["AMOUNT"]) for r in remaining_items if str(r["AMOUNT"]).strip() != ""
            )

            remaining_target = original_total - current_total

            for r in remaining_items:
                final_output.append(r.to_dict())

            if remaining_target > 0:

                selected, achieved = fill_target_fast(stock_df, remaining_target)

                for item in selected:
                    stock_df.at[item["INDEX"], "QTY"] -= 1

                combined = combine_items(selected)

                for item in combined:
                    final_output.append({
                        "DATE": date,
                        "BILL NO": bill_no,
                        "PARTICULAR": particular,
                        "ITEM NAME": item["ITEM NAME"],
                        "QUANTITY": item["QUANTITY"],
                        "PRICE": item["PRICE"],
                        "AMOUNT": item["AMOUNT"]
                    })

                if achieved != remaining_target:
                    final_output.append({
                        "DATE": date,
                        "BILL NO": bill_no,
                        "PARTICULAR": particular,
                        "ITEM NAME": "NOT EXACT MATCH",
                        "QUANTITY": "",
                        "PRICE": "",
                        "AMOUNT": remaining_target - achieved
                    })

            final_output.append({})

        final_df = pd.DataFrame(final_output)

        st.success("✅ Updated Successfully")

        st.dataframe(final_df)

        st.download_button(
            "📥 Download Updated File",
            to_excel(final_df),
            "updated.xlsx"
        )
