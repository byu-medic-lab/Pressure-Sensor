from datetime import datetime, timedelta, timezone
from math import exp

from app.analysis import fit_exponential_settling
from app.calibration import CalibrationStore, fit_linear, nearest_neighbor_merge


def test_linear_fit() -> None:
    fit = fit_linear([0, 10, 20], [1, 21, 41])
    assert round(fit.slope, 6) == 2
    assert round(fit.intercept, 6) == 1


def test_calibration_store_pressure_conversion() -> None:
    store = CalibrationStore()
    now = datetime.now(timezone.utc)
    store.add_manometer_window(now, 0, [100, 100, 100])
    store.add_manometer_window(now, 10, [200, 200, 200])
    store.fit_pressure()
    pressure = store.convert_raw_pressure(200)
    assert pressure is not None
    assert round(pressure, 6) == round(10 * 0.735559, 6)


def test_syringe_movement_calibration_fits_delta_pressure() -> None:
    store = CalibrationStore()
    now = datetime.now(timezone.utc)
    store.add_manometer_window(now, 0, [100, 100])
    store.add_manometer_window(now, 10, [200, 200])
    store.fit_pressure()

    store.add_syringe_movement_point(now, 10.0, "INF", 1.0, [100, 100], [150, 150], cumulative_motion_seconds=10.0)
    store.add_syringe_movement_point(now, 10.0, "INF", 1.0, [150, 150], [200, 200], cumulative_motion_seconds=20.0)
    fit = store.fit_syringe()

    assert fit.slope > 0
    motion_seconds = store.motion_seconds_for_pressure_delta(fit.slope * 15.0)
    assert motion_seconds is not None
    assert round(motion_seconds, 6) == 15.0


def test_syringe_calibration_keeps_directional_fits() -> None:
    store = CalibrationStore()
    now = datetime.now(timezone.utc)
    store.add_manometer_window(now, 0, [100, 100])
    store.add_manometer_window(now, 100, [1100, 1100])
    store.fit_pressure()

    store.add_syringe_movement_point(now, 5.0, "INF", 60.0, [100, 100], [200, 200], cumulative_motion_seconds=5.0)
    store.add_syringe_movement_point(now, 5.0, "INF", 60.0, [200, 200], [300, 300], cumulative_motion_seconds=10.0)
    store.add_syringe_movement_point(now, 5.0, "WDR", 60.0, [300, 300], [220, 220], cumulative_motion_seconds=5.0)
    store.add_syringe_movement_point(now, 5.0, "WDR", 60.0, [220, 220], [140, 140], cumulative_motion_seconds=0.0)

    store.fit_syringe()

    assert store.syringe_increasing_fit is not None
    assert store.syringe_decreasing_fit is not None
    assert store.motion_seconds_for_pressure_delta(1.0) is not None
    decreasing_motion = store.motion_seconds_for_pressure_delta(-1.0)
    assert decreasing_motion is not None
    assert decreasing_motion < 0


def test_nearest_neighbor_merge() -> None:
    base = datetime.now(timezone.utc)
    pressure = [(base, 10.0), (base + timedelta(seconds=2), 20.0)]
    resistance = [(base + timedelta(milliseconds=200), 350.1), (base + timedelta(seconds=3), 350.5)]
    assert nearest_neighbor_merge(pressure, resistance) == [
        (base, 10.0, 350.1),
        (base + timedelta(seconds=2), 20.0, 350.5),
    ]


def test_exponential_settling_fit_predicts_final_value() -> None:
    samples = [(float(second), 100.0 + 20.0 * exp(-second / 4.0)) for second in range(20)]
    fit = fit_exponential_settling(samples)
    assert fit is not None
    assert abs(fit.final_value - 100.0) < 1.0
    assert fit.tau_seconds > 0
