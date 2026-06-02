import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Billing Software", layout="wide")
st.title("🧾 Smart Billing & Stock Management System")

# -----------------------------
# EXCEL DOWNLOAD FUNCTION
# -----------------------------
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

# -----------------------------
# FAST FILL FUNCTION
# -----------------------------
def fill_target_fast(stock_df, target):
    stock_df = stock_df.sort_values(by="PRICE", ascending=False)

    selected = []
    achieved = 0

    for i, row in stock_df.iterrows():
        price = int(row["PRICE"])
        qty = int(row["QTY"])

        while qty > 0 and achieved + price <= target:
            selected.append({
                "ITEM NAME": row["ITEM NAME"],
                "PRICE": price,
                "INDEX": i
            })
            achieved += price
            qty -= 1

        if achieved == target:
            break

    return selected, achieved

# -----------------------------
# COMBINE ITEMS
# -----------------------------
def combine_items(selected):
    combined = {}

    for item in selected:
        key = (item["ITEM NAME"], item["PRICE"])

        if key not in combined:
            combined[key] = {
                "ITEM NAME": item["ITEM NAME"],
                "PRICE": item["PRICE"],
                "QUANTITY": 0
            }

        combined[key]["QUANTITY"] += 1

    result = []
    for v in combined.values():
        v["AMOUNT"] = v["QUANTITY"] * v["PRICE"]
        result.append(v)

    return result

# -----------------------------
# UI TABS
# -----------------------------
tab1, tab2 = st.tabs(["📄 Generate Bills", "🔄 Update Items & Regenerate"])

# =========================================================
# TAB 1: GENERATE BILLS
# =========================================================
with tab1:

    st.header("📄 Generate Bills")

    bill_no = st.number_input("Starting Bill Number", min_value=1, value=1)
    bills_file = st.file_uploader("Upload Bills File", type=["xlsx"], key="bills")
    stock_file = st.file_uploader("Upload Stock File", type=["xlsx"], key="stock")

    if st.button("🚀 Generate Bills"):

        if bills_file and stock_file:

            bills = pd.read_excel(bills_file)
            stock = pd.read_excel(stock_file)

            bills.columns = bills.columns.str.strip().str.upper()
            stock.columns = stock.columns.str.strip().str.upper()

            stock["QTY"] = stock["QTY"].astype(float)
            stock["PRICE"] = stock["PRICE"].astype(float)

            output = []

            for _, bill in bills.iterrows():

                date = pd.to_datetime(bill["DATE"]).strftime("%d-%m-%Y")
                remaining = int(round(float(bill["AMOUNT"])))
                original_total = remaining

                used_rows = []

                # FILL LOGIC
                selected, achieved = fill_target_fast(stock, remaining)

                # UPDATE STOCK
                for item in selected:
                    stock.at[item["INDEX"], "QTY"] -= 1

                # COMBINE
                combined_items = combine_items(selected)

                for item in combined_items:
                    output.append({
                        "DATE": date,
                        "BILL NO": bill_no,
                        "ITEM NAME": item["ITEM NAME"],
                        "QUANTITY": item["QUANTITY"],
                        "PRICE": item["PRICE"],
                        "AMOUNT": item["AMOUNT"]
                    })

                if achieved != original_total:
                    output.append({
                        "DATE": date,
                        "BILL NO": bill_no,
                        "ITEM NAME": "UNMATCHED",
                        "QUANTITY": "",
                        "PRICE": "",
                        "AMOUNT": original_total - achieved
                    })

                output.append({"DATE":"","BILL NO":"","ITEM NAME":"","QUANTITY":"","PRICE":"","AMOUNT":""})
                bill_no += 1

            output_df = pd.DataFrame(output)
            remaining_stock = stock[stock["QTY"] > 0]

            st.success("✅ Bills Generated!")

            st.download_button("📥 Download Output", to_excel(output_df), "output.xlsx")
            st.download_button("📥 Download Remaining Stock", to_excel(remaining_stock), "remaining_stock.xlsx")

        else:
            st.error("Upload both files")

# =========================================================
# TAB 2: UPDATE ITEMS
# =========================================================
with tab2:

    st.header("🔄 Update & Regenerate Bills")

    output_file = st.file_uploader("Upload Output File", type=["xlsx"], key="output")
    stock_file2 = st.file_uploader("Upload Remaining Stock", type=["xlsx"], key="stock2")

    item_name = st.text_input("Item Name").strip().upper()
    old_price = st.number_input("Old Price", value=0.0)
    new_price = st.number_input("New Price", value=0.0)

    if st.button("🔄 Update & Regenerate"):

        if output_file and stock_file2:

            output_df = pd.read_excel(output_file)
            stock_df = pd.read_excel(stock_file2)

            output_df.columns = output_df.columns.str.strip().str.upper()
            stock_df.columns = stock_df.columns.str.strip().str.upper()

            output_df["ITEM NAME"] = output_df["ITEM NAME"].astype(str).str.upper()
            stock_df["ITEM NAME"] = stock_df["ITEM NAME"].astype(str).str.upper()

            stock_df["PRICE"] = stock_df["PRICE"].astype(float)
            stock_df["QTY"] = stock_df["QTY"].astype(float)

            final_output = []

            for bill_no, group in output_df.groupby("BILL NO"):

                group = group.dropna(subset=["ITEM NAME"])
                if group.empty:
                    continue

                date = group.iloc[0]["DATE"]
                original_total = int(group["AMOUNT"].sum())

                remaining_items = []

                # REMOVE OLD ITEM
                for _, row in group.iterrows():

                    if row["ITEM NAME"] == item_name and float(row["PRICE"]) == old_price:
                        qty = float(row["QUANTITY"])

                        stock_df.loc[len(stock_df)] = {
                            "ITEM NAME": item_name,
                            "QTY": qty,
                            "PRICE": new_price,
                            "UNIT": "PCS"
                        }
                    else:
                        remaining_items.append(row)

                # CALCULATE REMAINING
                current_total = sum([int(r["AMOUNT"]) for r in remaining_items])
                remaining_target = original_total - current_total

                # SAVE OLD ITEMS
                for r in remaining_items:
                    final_output.append(r.to_dict())

                # REFILL
                if remaining_target > 0:

                    selected, achieved = fill_target_fast(stock_df, remaining_target)

                    for item in selected:
                        stock_df.at[item["INDEX"], "QTY"] -= 1

                    combined_items = combine_items(selected)

                    for item in combined_items:
                        final_output.append({
                            "DATE": date,
                            "BILL NO": bill_no,
                            "ITEM NAME": item["ITEM NAME"],
                            "QUANTITY": item["QUANTITY"],
                            "PRICE": item["PRICE"],
                            "AMOUNT": item["AMOUNT"]
                        })

                    if achieved != remaining_target:
                        final_output.append({
                            "DATE": date,
                            "BILL NO": bill_no,
                            "ITEM NAME": "NOT EXACT MATCH",
                            "QUANTITY": "",
                            "PRICE": "",
                            "AMOUNT": remaining_target - achieved
                        })

                final_output.append({"DATE":"","BILL NO":"","ITEM NAME":"","QUANTITY":"","PRICE":"","AMOUNT":""})

            final_df = pd.DataFrame(final_output)

            st.success("✅ Updated Successfully!")

            # REMOVE ZERO QTY ITEMS
            updated_stock = stock_df[stock_df["QTY"] > 0]
            
            st.download_button(
                "📥 Download Updated Output",
                to_excel(final_df),
                "final_output.xlsx"
            )
            
            st.download_button(
                "📦 Download Updated Stock",
                to_excel(updated_stock),
                "updated_stock.xlsx"
            )

        else:
            st.error("Upload both files")