from app.state_machine import AppMode, AppState, SafetyContext, StateMachine


def test_valid_transition_to_recording_and_idle() -> None:
    sm = StateMachine()
    sm.transition(AppState.RECORDING)
    sm.transition(AppState.IDLE)
    assert sm.state == AppState.IDLE


def test_closed_loop_requires_calibrations_and_pump() -> None:
    sm = StateMachine()
    errors = sm.validate_start(
        AppMode.CLOSED_LOOP_TEST,
        SafetyContext(
            pressure_connected=True,
            fluke_connected=True,
            pump_connected=False,
            logging_path_selected=True,
            pressure_calibration_available=False,
            syringe_calibration_available=False,
        ),
    )
    assert "Pressure calibration" in " ".join(errors)
    assert "Syringe calibration" in " ".join(errors)
    assert "Pump" in " ".join(errors)

