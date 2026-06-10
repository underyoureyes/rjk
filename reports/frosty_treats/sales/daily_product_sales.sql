/*
title: "Daily Product Sales"
description: "Units sold and revenue by product, flavour and region for the selected sales date. Use to monitor day-on-day performance across the full product range."
owner: "Sales Analytics"
tags: [sales, daily, ice-cream, iced-lolly, soft-drink]
params:
  sales_date:
    type: date
    label: "Sales Date"
    default: "today"
mock:
  dimensions:
    PRODUCT:
      - Ice Cream
      - Iced Lolly
      - Soft Drink
    FLAVOUR:
      - Vanilla
      - Chocolate
      - Strawberry
      - Mango
      - Raspberry
      - Lemon
      - Mint Choc Chip
      - Toffee Crunch
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
      min: 10
      max: 5000
      decimals: 0
    REVENUE:
      min: 5.00
      max: 2500.00
      decimals: 2
    AVG_UNIT_PRICE:
      min: 0.50
      max: 4.99
      decimals: 2
    GROSS_MARGIN_PCT:
      min: 0.10
      max: 0.65
      decimals: 4
*/

SELECT
    s.PRODUCT,
    s.FLAVOUR,
    s.REGION,
    s.SALES_DATE,
    SUM(s.UNITS_SOLD)                               AS UNITS_SOLD,
    SUM(s.REVENUE)                                  AS REVENUE,
    AVG(s.UNIT_PRICE)                               AS AVG_UNIT_PRICE,
    AVG(s.GROSS_MARGIN_PCT)                         AS GROSS_MARGIN_PCT
FROM
    sales.daily_transactions    s
WHERE
    s.SALES_DATE = :sales_date
GROUP BY
    s.PRODUCT, s.FLAVOUR, s.REGION, s.SALES_DATE
ORDER BY
    s.PRODUCT, s.FLAVOUR, s.REGION
