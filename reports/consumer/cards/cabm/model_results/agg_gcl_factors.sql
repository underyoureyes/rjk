/*
title: "Aggregate GCL Factors"
description: "Aggregated Good Credit Loss factor weights and scores across customer segments, risk bands and product types. Used by CABM to validate factor stability before model deployment."
owner: "CABM Analytics"
tags: [gcl, factors, model-results, cabm]
params:
  run_date:
    type: date
    label: "Run Date"
    default: "today"
  segment:
    type: select
    label: "Segment"
    options: [ALL, PRIME, NEAR_PRIME, SUB_PRIME]
    default: ALL
mock:
  dimensions:
    SEGMENT:
      - PRIME
      - NEAR_PRIME
      - SUB_PRIME
    RISK_BAND:
      - BAND_1
      - BAND_2
      - BAND_3
      - BAND_4
      - BAND_5
    FACTOR_NAME:
      - UTILISATION
      - INCOME
      - TENURE
      - PAYMENT_HISTORY
      - BALANCE
      - CREDIT_LIMIT
      - DELINQUENCY
      - BUREAU_SCORE
      - AGE_AT_BOOKING
      - EMPLOYMENT
    PRODUCT_TYPE:
      - STANDARD
      - REWARDS
      - SECURED
      - PREMIUM
      - BASIC
    ACCOUNT_AGE_BAND:
      - 0_6M
      - 6_12M
      - 12_24M
      - 24_60M
      - 60_120M
      - 120M_PLUS
    CHANNEL:
      - DIRECT
      - BROKER
      - ONLINE
      - BRANCH
      - MOBILE
      - TELEPHONY
  numerics:
    FACTOR_VALUE:
      min: -2.0
      max: 2.0
      decimals: 4
    WEIGHT:
      min: 0.0
      max: 1.0
      decimals: 4
    N_ACCOUNTS:
      min: 100
      max: 50000
      decimals: 0
    GINI:
      min: 0.2
      max: 0.8
      decimals: 4
*/

SELECT
    f.SEGMENT,
    f.RISK_BAND,
    f.FACTOR_NAME,
    f.PRODUCT_TYPE,
    f.ACCOUNT_AGE_BAND,
    f.CHANNEL,
    SUM(f.FACTOR_VALUE * w.WEIGHT)          AS FACTOR_VALUE,
    AVG(w.WEIGHT)                           AS WEIGHT,
    COUNT(a.ACCOUNT_ID)                     AS N_ACCOUNTS,
    f.GINI_COEFFICIENT                      AS GINI
FROM
    cabm.gcl_factors          f
    JOIN cabm.factor_weights  w ON w.FACTOR_NAME = f.FACTOR_NAME
                                AND w.MODEL_VERSION = f.MODEL_VERSION
    JOIN cards.accounts       a ON a.SEGMENT      = f.SEGMENT
                                AND a.RISK_BAND   = f.RISK_BAND
                                AND a.PRODUCT_TYPE = f.PRODUCT_TYPE
WHERE
    f.RUN_DATE  = :run_date
    AND (f.SEGMENT = :segment OR :segment = 'ALL')
GROUP BY
    f.SEGMENT, f.RISK_BAND, f.FACTOR_NAME,
    f.PRODUCT_TYPE, f.ACCOUNT_AGE_BAND, f.CHANNEL,
    f.GINI_COEFFICIENT
ORDER BY
    f.SEGMENT, f.RISK_BAND, f.FACTOR_NAME
