"""Inspector: calibration, anomaly, sizing, limits, and decide() gate."""

from inspector.anomaly import score as anomaly_score
from inspector.calibration import CalibrationMatrix, wilson_lower
from inspector.gate import decide, schema_ok
from inspector.limits import limits_hash, load as load_limits_file, pre_trade
from inspector.sizing import kelly, quarter_kelly, size_for_risk

__all__ = [
    "CalibrationMatrix",
    "anomaly_score",
    "decide",
    "kelly",
    "limits_hash",
    "load_limits_file",
    "pre_trade",
    "quarter_kelly",
    "schema_ok",
    "size_for_risk",
    "wilson_lower",
]
