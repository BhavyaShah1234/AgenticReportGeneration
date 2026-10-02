"""Load the Kaggle `kyanyoga/sample-sales-data` dataset into Snowflake as a star schema.

Idempotent: database/schema are CREATE ... IF NOT EXISTS, tables/view are CREATE OR REPLACE.

Credentials (env): SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_API (PAT),
SNOWFLAKE_WAREHOUSE, SNOWFLAKE_ROLE. Kaggle creds: ~/.kaggle/kaggle.json.
"""
import os
import sys

import kagglehub
import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas

DATASET = "kyanyoga/sample-sales-data"
CSV_NAME = "sales_data_sample.csv"
DATABASE = "DEMO_CORP"
SCHEMA = "SALES"


# --------------------------------------------------------------------------- extract
def download_csv() -> str:
    path = kagglehub.dataset_download(DATASET)
    csv = os.path.join(path, CSV_NAME)
    if not os.path.exists(csv):
        sys.exit(f"{CSV_NAME} not found in {path}")
    return csv


def _clean_str(s: pd.Series) -> pd.Series:
    """Trim and collapse internal whitespace; keep NaN as NaN."""
    return s.where(s.isna(), s.astype(str).str.strip().str.replace(r"\s+", " ", regex=True))


# --------------------------------------------------------------------------- transform
def load_and_clean(csv: str) -> pd.DataFrame:
    # keep_default_na=False so TERRITORY='NA' (North America) is not read as NaN.
    df = pd.read_csv(csv, encoding="latin-1", keep_default_na=False, na_values=[""])

    str_cols = df.select_dtypes(include="object").columns.drop("ORDERDATE")
    for c in str_cols:
        df[c] = _clean_str(df[c])
    # NOTE: no title-casing. The source is already properly cased; every all-caps value
    # is an acronym (USA, UK, NYC, NY, NSW) and title-casing would corrupt it ('Usa').

    df["ORDERDATE"] = pd.to_datetime(df["ORDERDATE"], format="%m/%d/%Y %H:%M").dt.date

    # Non-US/AU/CA addresses have no state/province -> explicit 'N/A' rather than NULL.
    df["STATE"] = df["STATE"].fillna("N/A")
    # Territory is fully populated in the source ('NA' = North America); guard anyway.
    df["TERRITORY"] = df["TERRITORY"].fillna(
        df["COUNTRY"].map({"USA": "NA", "Canada": "NA"})
    ).fillna("Unknown")
    df["POSTALCODE"] = df["POSTALCODE"].astype("string")
    return df


def build_star(df: pd.DataFrame):
    client_cols = {
        "CUSTOMERNAME": "CLIENT_NAME",
        "CONTACTFIRSTNAME": "CONTACT_FIRST_NAME",
        "CONTACTLASTNAME": "CONTACT_LAST_NAME",
        "PHONE": "PHONE",
        "ADDRESSLINE1": "ADDRESS_LINE1",
        "ADDRESSLINE2": "ADDRESS_LINE2",
        "CITY": "CITY",
        "STATE": "STATE",
        "POSTALCODE": "POSTAL_CODE",
        "COUNTRY": "COUNTRY",
        "TERRITORY": "TERRITORY",
    }
    clients = (
        df[list(client_cols)]
        .drop_duplicates(subset=["CUSTOMERNAME"])
        .rename(columns=client_cols)
        .sort_values("CLIENT_NAME")
        .reset_index(drop=True)
    )
    clients.insert(0, "CLIENT_ID", range(1, len(clients) + 1))

    products = (
        df[["PRODUCTCODE", "PRODUCTLINE", "MSRP"]]
        .drop_duplicates(subset=["PRODUCTCODE"])
        .rename(columns={"PRODUCTCODE": "PRODUCT_CODE", "PRODUCTLINE": "PRODUCT_LINE"})
        .sort_values("PRODUCT_CODE")
        .reset_index(drop=True)
    )

    id_map = dict(zip(clients["CLIENT_NAME"], clients["CLIENT_ID"]))
    lines = pd.DataFrame({
        "ORDER_NUMBER": df["ORDERNUMBER"],
        "ORDER_LINE_NUMBER": df["ORDERLINENUMBER"],
        "ORDER_DATE": df["ORDERDATE"],
        "QUARTER": df["QTR_ID"],
        "MONTH": df["MONTH_ID"],
        "YEAR": df["YEAR_ID"],
        "STATUS": df["STATUS"],
        "CLIENT_ID": df["CUSTOMERNAME"].map(id_map),
        "PRODUCT_CODE": df["PRODUCTCODE"],
        "QUANTITY_ORDERED": df["QUANTITYORDERED"],
        "PRICE_EACH": df["PRICEEACH"].round(2),
        "SALES": df["SALES"].round(2),
        "DEAL_SIZE": df["DEALSIZE"],
    })
    assert lines["CLIENT_ID"].notna().all()
    return clients, products, lines


# --------------------------------------------------------------------------- load
DDL = [
    f"CREATE DATABASE IF NOT EXISTS {DATABASE}",
    f"CREATE SCHEMA IF NOT EXISTS {DATABASE}.{SCHEMA}",
    f"USE SCHEMA {DATABASE}.{SCHEMA}",
    """CREATE OR REPLACE TABLE CLIENTS (
        CLIENT_ID INT NOT NULL PRIMARY KEY,
        CLIENT_NAME VARCHAR NOT NULL,
        CONTACT_FIRST_NAME VARCHAR,
        CONTACT_LAST_NAME VARCHAR,
        PHONE VARCHAR,
        ADDRESS_LINE1 VARCHAR,
        ADDRESS_LINE2 VARCHAR,
        CITY VARCHAR,
        STATE VARCHAR,
        POSTAL_CODE VARCHAR,
        COUNTRY VARCHAR,
        TERRITORY VARCHAR
    )""",
    """CREATE OR REPLACE TABLE PRODUCTS (
        PRODUCT_CODE VARCHAR NOT NULL PRIMARY KEY,
        PRODUCT_LINE VARCHAR,
        MSRP NUMBER(10,2)
    )""",
    """CREATE OR REPLACE TABLE ORDER_LINES (
        ORDER_NUMBER INT NOT NULL,
        ORDER_LINE_NUMBER INT NOT NULL,
        ORDER_DATE DATE,
        QUARTER INT,
        MONTH INT,
        YEAR INT,
        STATUS VARCHAR,
        CLIENT_ID INT REFERENCES CLIENTS(CLIENT_ID),
        PRODUCT_CODE VARCHAR REFERENCES PRODUCTS(PRODUCT_CODE),
        QUANTITY_ORDERED INT,
        PRICE_EACH NUMBER(10,2),
        SALES NUMBER(12,2),
        DEAL_SIZE VARCHAR,
        PRIMARY KEY (ORDER_NUMBER, ORDER_LINE_NUMBER)
    )""",
]

VIEW = """CREATE OR REPLACE VIEW V_SALES AS
SELECT
    o.ORDER_NUMBER,
    o.ORDER_LINE_NUMBER,
    o.ORDER_DATE,
    o.YEAR,
    o.QUARTER,
    o.MONTH,
    o.STATUS,
    o.DEAL_SIZE,
    o.QUANTITY_ORDERED,
    o.PRICE_EACH,
    o.SALES,
    o.CLIENT_ID,
    c.CLIENT_NAME,
    c.CONTACT_FIRST_NAME,
    c.CONTACT_LAST_NAME,
    c.PHONE,
    c.CITY,
    c.STATE,
    c.POSTAL_CODE,
    c.COUNTRY,
    c.TERRITORY,
    o.PRODUCT_CODE,
    p.PRODUCT_LINE,
    p.MSRP
FROM ORDER_LINES o
JOIN CLIENTS  c ON c.CLIENT_ID = o.CLIENT_ID
JOIN PRODUCTS p ON p.PRODUCT_CODE = o.PRODUCT_CODE"""


def _env_from_bashrc():
    """Fallback: pick up `export SNOWFLAKE_*=...` lines from ~/.bashrc (non-interactive
    shells skip them). Values are only placed in os.environ, never printed."""
    import re
    import shlex
    rc = os.path.expanduser("~/.bashrc")
    if not os.path.exists(rc):
        return
    pat = re.compile(r"^\s*export\s+(SNOWFLAKE_[A-Z_]+)=(.*)$")
    with open(rc) as fh:
        for line in fh:
            m = pat.match(line)
            if m and not os.environ.get(m.group(1)):
                parts = shlex.split(m.group(2), comments=True)
                os.environ[m.group(1)] = parts[0] if parts else ""


def connect():
    _env_from_bashrc()
    missing = [v for v in ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_API",
                           "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_ROLE") if not os.environ.get(v)]
    if missing:
        sys.exit(f"Missing env vars: {', '.join(missing)}")
    common = dict(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        role=os.environ["SNOWFLAKE_ROLE"],
    )
    try:
        return snowflake.connector.connect(
            authenticator="PROGRAMMATIC_ACCESS_TOKEN", token=os.environ["SNOWFLAKE_API"], **common
        )
    except snowflake.connector.errors.Error as e:
        print(f"PAT authenticator failed ({type(e).__name__}); retrying with password=PAT")
        return snowflake.connector.connect(password=os.environ["SNOWFLAKE_API"], **common)


def main():
    csv = download_csv()
    df = load_and_clean(csv)
    clients, products, lines = build_star(df)
    print(f"Source rows: {len(df)}  clients: {len(clients)}  products: {len(products)}")

    conn = connect()
    try:
        cur = conn.cursor()
        for stmt in DDL:
            cur.execute(stmt)
        for name, frame in (("CLIENTS", clients), ("PRODUCTS", products), ("ORDER_LINES", lines)):
            ok, _, nrows, _ = write_pandas(
                conn, frame, name, database=DATABASE, schema=SCHEMA,
                quote_identifiers=False, use_logical_type=True,
            )
            if not ok:
                sys.exit(f"write_pandas failed for {name}")
        cur.execute(VIEW)

        print("\nRow counts:")
        for t in ("CLIENTS", "PRODUCTS", "ORDER_LINES", "V_SALES"):
            n = cur.execute(f"SELECT COUNT(*) FROM {DATABASE}.{SCHEMA}.{t}").fetchone()[0]
            print(f"  {DATABASE}.{SCHEMA}.{t:<12} {n}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
