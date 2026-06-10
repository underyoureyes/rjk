/*
title: "Ice Cream Daily Sales"
description: "Units sold, revenue and margin by flavour and region across the last 14 days. Select a sales date to see all data up to and including that day."
owner: "Sales Analytics"
tags: [sales, daily, ice-cream]
params:
  sales_date:
    type: date
    label: "Sales Date"
    default: "today"
mock:
  dimensions:
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
  derived:
    MONTH:
      month_start_of: SALES_DATE
  numerics:
    UNITS_SOLD:
      min: 10
      max: 500
      decimals: 0
    REVENUE:
      min: 5.00
      max: 250.00
      decimals: 2
    AVG_UNIT_PRICE:
      min: 0.80
      max: 4.99
      decimals: 2
    GROSS_MARGIN_PCT:
      min: 0.10
      max: 0.65
      decimals: 4
*/

SELECT
    s.FLAVOUR,
    s.REGION,
    s.SALES_DATE,
    TRUNC(s.SALES_DATE, 'MM')  AS MONTH,
    s.REPORT_DATE,
    SUM(s.UNITS_SOLD)       AS UNITS_SOLD,
    SUM(s.REVENUE)          AS REVENUE,
    AVG(s.UNIT_PRICE)       AS AVG_UNIT_PRICE,
    AVG(s.GROSS_MARGIN_PCT) AS GROSS_MARGIN_PCT
FROM
    sales.daily_transactions s
WHERE
    s.SALES_DATE <= :sales_date
GROUP BY
    s.FLAVOUR, s.REGION, s.SALES_DATE, s.REPORT_DATE
ORDER BY
    s.SALES_DATE, s.FLAVOUR, s.REGION
