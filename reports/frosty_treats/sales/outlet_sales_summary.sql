/*
title: "Outlet Sales Summary"
description: "Sales by outlet type and region across the last 14 days. Select a sales date to see all data up to and including that day. Useful for comparing channel performance over time."
owner: "Sales Analytics"
tags: [sales, outlets, channels, daily]
params:
  sales_date:
    type: date
    label: "Sales Date"
    default: "today"
mock:
  dimensions:
    OUTLET_TYPE:
      - Kiosk
      - Ice Cream Van
      - Corner Shop
      - Supermarket
      - Cafe
      - Beach Hut
    PRODUCT:
      - Ice Cream
      - Iced Lolly
      - Soft Drink
    REGION:
      - North
      - South
      - East
      - West
      - Midlands
      - Scotland
    SALES_DATE:
      - "today-13"
      - "today-12"
      - "today-11"
      - "today-10"
      - "today-9"
      - "today-8"
      - "today-7"
      - "today-6"
      - "today-5"
      - "today-4"
      - "today-3"
      - "today-2"
      - "today-1"
      - "today"
    REPORT_DATE:
      - "today"
  filters:
    sales_date:
      column: SALES_DATE
      op: "<="
  numerics:
    UNITS_SOLD:
      min: 5
      max: 300
      decimals: 0
    REVENUE:
      min: 3.00
      max: 150.00
      decimals: 2
    TRANSACTIONS:
      min: 2
      max: 100
      decimals: 0
    AVG_BASKET_VALUE:
      min: 1.20
      max: 12.50
      decimals: 2
*/

SELECT
    o.OUTLET_TYPE,
    o.PRODUCT,
    o.REGION,
    o.SALES_DATE,
    o.REPORT_DATE,
    SUM(o.UNITS_SOLD)                                       AS UNITS_SOLD,
    SUM(o.REVENUE)                                          AS REVENUE,
    COUNT(o.TRANSACTION_ID)                                 AS TRANSACTIONS,
    SUM(o.REVENUE) / NULLIF(COUNT(o.TRANSACTION_ID), 0)    AS AVG_BASKET_VALUE
FROM
    sales.outlet_transactions   o
WHERE
    o.SALES_DATE <= :sales_date
GROUP BY
    o.OUTLET_TYPE, o.PRODUCT, o.REGION, o.SALES_DATE, o.REPORT_DATE
ORDER BY
    o.SALES_DATE, o.OUTLET_TYPE, o.PRODUCT, o.REGION
