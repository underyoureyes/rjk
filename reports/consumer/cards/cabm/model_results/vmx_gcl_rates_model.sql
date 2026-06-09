/*
title: "VMX GCL Rates — Model Output"
description: "Good Credit Loss rates per model version, showing predicted vs actual loss across score bands. Primary validation output for the VMX model suite. Compare across MODEL_VERSION to assess champion/challenger performance."
owner: "CABM Analytics"
tags: [gcl, rates, vmx, model-results, cabm, champion-challenger]
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
    MODEL_VERSION:
      - v1.0
      - v1.1
      - v2.0
    SEGMENT:
      - PRIME
      - NEAR_PRIME
      - SUB_PRIME
    SCORE_BAND:
      - BAND_01
      - BAND_02
      - BAND_03
      - BAND_04
      - BAND_05
      - BAND_06
      - BAND_07
      - BAND_08
      - BAND_09
      - BAND_10
    PRODUCT_TYPE:
      - STANDARD
      - REWARDS
      - SECURED
      - PREMIUM
      - BASIC
    CHANNEL:
      - DIRECT
      - BROKER
      - ONLINE
      - BRANCH
      - MOBILE
      - TELEPHONY
    RUN_DATE:
      - "2024-01-01"
      - "2024-04-01"
      - "2024-07-01"
      - "2024-10-01"
  numerics:
    GCL_RATE:
      min: 0.001
      max: 0.15
      decimals: 5
    PREDICTED_LOSS:
      min: 0.0
      max: 0.20
      decimals: 5
    ACTUAL_LOSS:
      min: 0.0
      max: 0.18
      decimals: 5
    LIFT:
      min: 0.5
      max: 3.0
      decimals: 3
    N_ACCOUNTS:
      min: 50
      max: 10000
      decimals: 0
*/

SELECT
    m.MODEL_VERSION,
    m.SEGMENT,
    m.SCORE_BAND,
    m.PRODUCT_TYPE,
    m.CHANNEL,
    CAST(m.RUN_DATE AS DATE)                        AS RUN_DATE,
    m.GCL_RATE,
    m.PREDICTED_LOSS,
    NVL(a.ACTUAL_LOSS, 0)                          AS ACTUAL_LOSS,
    m.GCL_RATE / NULLIF(a.ACTUAL_LOSS, 0)          AS LIFT,
    COUNT(ac.ACCOUNT_ID)                            AS N_ACCOUNTS
FROM
    cabm.vmx_model_output      m
    LEFT JOIN cabm.actual_loss a ON a.SCORE_BAND    = m.SCORE_BAND
                                 AND a.SEGMENT      = m.SEGMENT
                                 AND a.RUN_DATE     = m.RUN_DATE
    JOIN cards.accounts       ac ON ac.SCORE_BAND   = m.SCORE_BAND
                                 AND ac.SEGMENT     = m.SEGMENT
                                 AND ac.PRODUCT_TYPE = m.PRODUCT_TYPE
WHERE
    m.RUN_DATE  = :run_date
    AND (m.SEGMENT = :segment OR :segment = 'ALL')
GROUP BY
    m.MODEL_VERSION, m.SEGMENT, m.SCORE_BAND,
    m.PRODUCT_TYPE, m.CHANNEL, m.RUN_DATE,
    m.GCL_RATE, m.PREDICTED_LOSS, a.ACTUAL_LOSS
ORDER BY
    m.MODEL_VERSION, m.SEGMENT, m.SCORE_BAND
