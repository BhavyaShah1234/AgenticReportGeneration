# Data: DEMO_CORP.SALES (Snowflake)

Real (not synthetic) order-line data for a model-car wholesaler that sells to 92 named B2B clients, January 2003 to May 2005.

- **Source:** Kaggle, [`kyanyoga/sample-sales-data`](https://www.kaggle.com/datasets/kyanyoga/sample-sales-data) (`sales_data_sample.csv`, latin-1, 2,823 rows). See the dataset page for its licence terms.
- **Loaded into:** `DEMO_CORP.SALES` as a star schema: `CLIENTS`, `PRODUCTS`, `ORDER_LINES`, plus the view `V_SALES`.

## How to run

```bash
cd data
python3.14 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python load_sample_sales.py
```

- **Kaggle:** credentials come from `~/.kaggle/kaggle.json`.
- **Snowflake:** needs `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_API` (a Programmatic Access Token), `SNOWFLAKE_WAREHOUSE` and `SNOWFLAKE_ROLE`. If they are not in the environment, the script reads the `export SNOWFLAKE_*=` lines from `~/.bashrc`. The token is never printed.
- **Rerunning:** the script is safe to run again. The database and schema use `IF NOT EXISTS`; the tables and view use `CREATE OR REPLACE`. It prints the row count of each table at the end.

## Cleaning applied

- **ORDER_DATE:** `ORDERDATE` (`m/d/yyyy 0:00`) is parsed to `DATE`.
- **TERRITORY:** the CSV is read with `keep_default_na=False`, so `TERRITORY = 'NA'` (North America: USA and Canada) stays a string. Values are `NA`, `EMEA`, `APAC` and `Japan`.
- **Strings:** trimmed and internal whitespace collapsed. The original casing is kept, because the source is already properly cased and its all-caps values are acronyms (`USA`, `UK`, `NYC`, `NY`).
- **STATE:** `NULL` becomes `'N/A'` (46 of the 92 clients, all outside the USA, Australia and Canada). `ADDRESS_LINE2` and `POSTAL_CODE` stay `NULL` when missing.
- **SALES:** taken from the source as-is. In the source, `PRICEEACH` is capped at 100, so `SALES` does not always equal `QUANTITY_ORDERED * PRICE_EACH`. Use `SALES` for revenue.

## Schema

**CLIENTS** (92 rows)

| column | type |
|---|---|
| CLIENT_ID | INT, surrogate PK (1..92, by name) |
| CLIENT_NAME | VARCHAR |
| CONTACT_FIRST_NAME, CONTACT_LAST_NAME | VARCHAR |
| PHONE | VARCHAR |
| ADDRESS_LINE1, ADDRESS_LINE2 | VARCHAR |
| CITY, STATE, POSTAL_CODE, COUNTRY | VARCHAR |
| TERRITORY | VARCHAR (`NA`, `EMEA`, `APAC`, `Japan`) |

**PRODUCTS** (109 rows)

| column | type |
|---|---|
| PRODUCT_CODE | VARCHAR PK |
| PRODUCT_LINE | VARCHAR |
| MSRP | NUMBER(10,2) |

**ORDER_LINES** (2,823 rows; PK `ORDER_NUMBER, ORDER_LINE_NUMBER`)

| column | type |
|---|---|
| ORDER_NUMBER, ORDER_LINE_NUMBER | INT |
| ORDER_DATE | DATE |
| QUARTER, MONTH, YEAR | INT |
| STATUS | VARCHAR (`Shipped`, `In Process`, `On Hold`, `Disputed`, `Resolved`, `Cancelled`) |
| CLIENT_ID | INT, FK to CLIENTS |
| PRODUCT_CODE | VARCHAR, FK to PRODUCTS |
| QUANTITY_ORDERED | INT |
| PRICE_EACH | NUMBER(10,2) |
| SALES | NUMBER(12,2) |
| DEAL_SIZE | VARCHAR (`Small`, `Medium`, `Large`) |

**V_SALES**: one row per order line. It is `ORDER_LINES` joined to `CLIENTS` and `PRODUCTS` (2,823 rows).

| column | type |
|---|---|
| ORDER_NUMBER, ORDER_LINE_NUMBER | NUMBER |
| ORDER_DATE | DATE |
| YEAR, QUARTER, MONTH | NUMBER |
| STATUS, DEAL_SIZE | VARCHAR |
| QUANTITY_ORDERED | NUMBER |
| PRICE_EACH | NUMBER(10,2) |
| SALES | NUMBER(12,2) |
| CLIENT_ID | NUMBER |
| CLIENT_NAME, CONTACT_FIRST_NAME, CONTACT_LAST_NAME, PHONE | VARCHAR |
| CITY, STATE, POSTAL_CODE, COUNTRY, TERRITORY | VARCHAR |
| PRODUCT_CODE, PRODUCT_LINE | VARCHAR |
| MSRP | NUMBER(10,2) |

The product lines are Classic Cars, Vintage Cars, Motorcycles, Trucks and Buses, Planes, Ships and Trains.

## Example analytic questions

The examples assume `USE SCHEMA DEMO_CORP.SALES;`.

**1. How did revenue trend by quarter, excluding cancelled orders?**

```sql
SELECT YEAR, QUARTER, SUM(SALES) AS REVENUE
FROM V_SALES
WHERE STATUS <> 'Cancelled'
GROUP BY 1, 2
ORDER BY 1, 2;
```

**2. Which product lines drive revenue, and what share does each have?**

```sql
SELECT PRODUCT_LINE, SUM(SALES) AS REVENUE,
       ROUND(100 * RATIO_TO_REPORT(SUM(SALES)) OVER (), 1) AS PCT_OF_TOTAL
FROM V_SALES
GROUP BY 1
ORDER BY 2 DESC;
```

**3. Who are the top 10 clients, and how many orders has each placed?**

```sql
SELECT CLIENT_NAME, COUNTRY, SUM(SALES) AS REVENUE,
       COUNT(DISTINCT ORDER_NUMBER) AS ORDERS
FROM V_SALES
GROUP BY 1, 2
ORDER BY REVENUE DESC
LIMIT 10;
```

**4. What is one client's monthly spend history (an account review)?**

```sql
SELECT DATE_TRUNC('month', ORDER_DATE) AS MONTH_START,
       SUM(SALES) AS REVENUE,
       COUNT(DISTINCT ORDER_NUMBER) AS ORDERS
FROM V_SALES
WHERE CLIENT_NAME = 'Euro Shopping Channel'
GROUP BY 1
ORDER BY 1;
```

**5. How much revenue is at risk (on hold, disputed or cancelled), and with which clients?**

```sql
SELECT STATUS, CLIENT_NAME,
       COUNT(DISTINCT ORDER_NUMBER) AS ORDERS,
       SUM(SALES) AS SALES_AT_RISK
FROM V_SALES
WHERE STATUS IN ('On Hold', 'Disputed', 'Cancelled')
GROUP BY 1, 2
ORDER BY SALES_AT_RISK DESC;
```
