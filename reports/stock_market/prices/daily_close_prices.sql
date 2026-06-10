/*
title: "Daily Close Prices"
description: "Daily closing prices for Palantir Technologies (PLTR) and Alphabet / Google (GOOGL) over the last 2 years. Select an as-of date to see all trading days up to that point."
owner: "Market Data"
tags: [stocks, prices, PLTR, GOOGL, equities]
params:
  as_of_date:
    type: date
    label: "As Of Date"
    default: "today"
mock:
  dimensions:
    TICKER:
      - PLTR
      - GOOGL
    CLOSE_DATE:
      date_range:
        start: "today-730"
        end: "today"
        freq: "weekday"
    REPORT_DATE:
      - "today"
  filters:
    as_of_date:
      column: CLOSE_DATE
      op: "<="
  numerics:
    OPEN_PRICE:
      min: 5.00
      max: 210.00
      decimals: 2
    HIGH_PRICE:
      min: 5.00
      max: 215.00
      decimals: 2
    LOW_PRICE:
      min: 5.00
      max: 205.00
      decimals: 2
    CLOSE_PRICE:
      min: 5.00
      max: 210.00
      decimals: 2
    VOLUME:
      min: 8000000
      max: 120000000
      decimals: 0
*/

SELECT
    p.TICKER,
    p.CLOSE_DATE,
    p.REPORT_DATE,
    p.OPEN_PRICE,
    p.HIGH_PRICE,
    p.LOW_PRICE,
    p.CLOSE_PRICE,
    p.VOLUME
FROM
    market.daily_prices p
WHERE
    p.CLOSE_DATE <= :as_of_date
ORDER BY
    p.TICKER, p.CLOSE_DATE
