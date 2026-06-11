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
  data_file: "data/mock/daily_close_prices.json"
  filters:
    as_of_date:
      column: CLOSE_DATE
      op: "<="
*/

SELECT
    p.TICKER,
    p.CLOSE_DATE,
    TRUNC(p.CLOSE_DATE, 'MM')  AS MONTH,
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
