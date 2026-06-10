/*
title: "Outlet Sales Summary"
description: "Sales performance by outlet type and region for the selected date. Identify which outlet channels are driving volume and where upsell opportunities exist."
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
      - "today"
  filters:
    sales_date:
      column: SALES_DATE
      op: "="
  numerics:
    UNITS_SOLD:
      min: 5
      max: 3000
      decimals: 0
    REVENUE:
      min: 3.00
      max: 1500.00
      decimals: 2
    TRANSACTIONS:
      min: 2
      max: 500
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
    SUM(o.UNITS_SOLD)                               AS UNITS_SOLD,
    SUM(o.REVENUE)                                  AS REVENUE,
    COUNT(o.TRANSACTION_ID)                         AS TRANSACTIONS,
    SUM(o.REVENUE) / NULLIF(COUNT(o.TRANSACTION_ID), 0) AS AVG_BASKET_VALUE
FROM
    sales.outlet_transactions   o
WHERE
    o.SALES_DATE = :sales_date
GROUP BY
    o.OUTLET_TYPE, o.PRODUCT, o.REGION, o.SALES_DATE
ORDER BY
    o.OUTLET_TYPE, o.PRODUCT, o.REGION
