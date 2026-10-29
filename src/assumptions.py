"""Sovereign wealth fund assets (USD bn). These are third-party estimates, NOT audited figures.

Source: aggregator pages citing Global SWF / SWFI rankings (mid-2025 and mid-2026 estimates):
PIF about 925-1,150; ADIA about 1,100; KIA about 1,000-1,070; QIA 500+.
No figure was found for Oman Investment Authority or Mumtalakat (Bahrain), so they are set to 0
and those two countries are tested on central bank reserves only. Abu Dhabi's other vehicles
(Mubadala, ADQ) are excluded, which is conservative for the UAE.
Much of PIF is illiquid Saudi holdings, so liquid shares below 100% are shown as variants.
"""
SWF_BN = {"SAU": 1000.0, "ARE": 1100.0, "QAT": 500.0, "KWT": 1000.0, "OMN": 0.0, "BHR": 0.0}
LIQUID_SHARES = {"reserves only": 0.0, "reserves + 25% of fund assets": 0.25, "reserves + 100% of fund assets": 1.0}
