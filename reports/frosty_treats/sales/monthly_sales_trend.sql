/*
title: "Monthly Sales Trend"
description: "Month-by-month revenue, units and growth rates across products and flavour categories up to the selected date. Use to spot seasonal patterns and track growth against prior periods."
owner: "Sales Analytics"
tags: [sales, trend, monthly, time-series, growth]
params:
  as_of_date:
    type: date
    label: "As Of Date"
    default: "today"
mock:
  dimensions:
    PRODUCT:
      - Ice Cream
      - Iced Lolly
      - Soft Drink
    FLAVOUR_CATEGORY:
      - Classic
      - Premium
      - Low Sugar
      - Seasonal
    AS_OF_DATE:
      - "01-Jan-2024"
      - "01-Feb-2024"
      - "01-Mar-2024"
      - "01-Apr-2024"
      - "01-May-2024"
      - "01-Jun-2024"
      - "01-Jul-2024"
      - "01-Aug-2024"
      - "01-Sep-2024"
      - "01-Oct-2024"
      - "01-Nov-2024"
      - "01-Dec-2024"
      - "01-Jan-2025"
      - "01-Feb-2025"
      - "01-Mar-2025"
      - "01-Apr-2025"
      - "01-May-2025"
      - "01-Jun-2025"
      - "01-Jul-2025"
      - "01-Aug-2025"
      - "01-Sep-2025"
      - "01-Oct-2025"
      - "01-Nov-2025"
      - "01-Dec-2025"
      - "01-Jan-2026"
      - "01-Feb-2026"
      - "01-Mar-2026"
      - "01-Apr-2026"
      - "01-May-2026"
      - "today"
    REPORT_DATE:
      - "today"
  filters:
    as_of_date:
      column: AS_OF_DATE
      op: "<="
  numerics:
    UNITS_SOLD:
      min: 500
      max: 50000
      decimals: 0
    REVENUE:
      min: 250.00
      max: 25000.00
      decimals: 2
    GROWTH_PCT:
      min: -0.30
      max: 0.50
      decimals: 4
    MARKET_SHARE:
      min: 0.05
      max: 0.60
      decimals: 4
*/

SELECT
    t.PRODUCT,
    t.FLAVOUR_CATEGORY,
    TRUNC(t.SALE_MONTH, 'MM')                       AS AS_OF_DATE,
    t.REPORT_DATE,
    SUM(t.UNITS_SOLD)                               AS UNITS_SOLD,
    SUM(t.REVENUE)                                  AS REVENUE,
    (SUM(t.REVENUE) - LAG(SUM(t.REVENUE)) OVER (
        PARTITION BY t.PRODUCT, t.FLAVOUR_CATEGORY
        ORDER BY TRUNC(t.SALE_MONTH, 'MM')
    )) / NULLIF(LAG(SUM(t.REVENUE)) OVER (
        PARTITION BY t.PRODUCT, t.FLAVOUR_CATEGORY
        ORDER BY TRUNC(t.SALE_MONTH, 'MM')
    ), 0)                                           AS GROWTH_PCT,
    SUM(t.REVENUE) / SUM(SUM(t.REVENUE)) OVER (
        PARTITION BY TRUNC(t.SALE_MONTH, 'MM')
    )                                               AS MARKET_SHARE
FROM
    sales.monthly_totals    t
WHERE
    t.SALE_MONTH <= :as_of_date
GROUP BY
    t.PRODUCT, t.FLAVOUR_CATEGORY, TRUNC(t.SALE_MONTH, 'MM'), t.REPORT_DATE
ORDER BY
    t.PRODUCT, t.FLAVOUR_CATEGORY, AS_OF_DATE
