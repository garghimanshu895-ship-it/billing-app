import pandas as pd

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
