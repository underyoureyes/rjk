/*
title: "VMX GCL Rates — Ratio Metrics"
description: "Monthly time-series of key ratio metrics (A/E ratio, Gini, KS, PSI, CSI, IV) across product types and regions. Used to monitor model drift and trigger re-calibration alerts."
owner: "CABM Analytics"
tags: [gcl, rates, vmx, ratios, model-results, cabm, monitoring]
params:
  run_date:
    type: date
    label: "As Of Date"
    default: "today"
mock:
  dimensions:
    RATIO_TYPE:
      - A_E_RATIO
      - LORENZ_RATIO
      - GINI_COEFF
      - KS_STAT
      - PSI
      - CSI
      - IV
    SEGMENT:
      - PRIME
      - NEAR_PRIME
      - SUB_PRIME
    PRODUCT_TYPE:
      - STANDARD
      - REWARDS
      - SECURED
      - PREMIUM
      - BASIC
      - PREMIUM_PLUS
    REGION:
      - NORTH
      - SOUTH
      - EAST
      - WEST
      - MIDLANDS
      - SCOTLAND
    AS_OF_DATE:
      - "01-Jan-2023"
      - "01-Feb-2023"
      - "01-Mar-2023"
      - "01-Apr-2023"
      - "01-May-2023"
      - "01-Jun-2023"
      - "01-Jul-2023"
      - "01-Aug-2023"
      - "01-Sep-2023"
      - "01-Oct-2023"
      - "01-Nov-2023"
      - "01-Dec-2023"
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
      - "today"
  filters:
    run_date:
      column: AS_OF_DATE
      op: "<="
  numerics:
    GCL_RATE:
      min: 0.0001
      max: 0.9999
      decimals_min: 1
      decimals_max: 8
    RATIO_VALUE:
      min: 0.0
      max: 2.0
      decimals: 5
    THRESHOLD_AMBER:
      min: 0.1
      max: 0.5
      decimals: 3
    THRESHOLD_RED:
      min: 0.5
      max: 1.0
      decimals: 3
    N_ACCOUNTS:
      min: 100
      max: 100000
      decimals: 0
*/

SELECT
    r.RATIO_TYPE,
    r.SEGMENT,
    r.PRODUCT_TYPE,
    br.REGION,
    TRUNC(r.AS_OF_DATE, 'MM')                               AS AS_OF_DATE,
    r.GCL_RATE,
    r.RATIO_VALUE,
    t.THRESHOLD_AMBER,
    t.THRESHOLD_RED,
    COUNT(DISTINCT a.ACCOUNT_ID)                            AS N_ACCOUNTS
FROM
    cabm.vmx_ratio_metrics        r
    JOIN cards.branch_region      br ON br.PRODUCT_TYPE  = r.PRODUCT_TYPE
    JOIN cabm.ratio_thresholds    t  ON t.RATIO_TYPE     = r.RATIO_TYPE
                                    AND t.SEGMENT        = r.SEGMENT
    JOIN cards.accounts           a  ON a.SEGMENT        = r.SEGMENT
                                    AND a.PRODUCT_TYPE   = r.PRODUCT_TYPE
WHERE
    r.AS_OF_DATE <= :run_date
GROUP BY
    r.RATIO_TYPE, r.SEGMENT, r.PRODUCT_TYPE,
    br.REGION, TRUNC(r.AS_OF_DATE, 'MM'),
    r.RATIO_VALUE, t.THRESHOLD_AMBER, t.THRESHOLD_RED
ORDER BY
    r.RATIO_TYPE, r.SEGMENT, AS_OF_DATE
