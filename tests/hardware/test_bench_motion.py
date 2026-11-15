"""Powered floor checks must arm explicitly and brake before measurements."""
import os
import sys
from unittest.mock import patch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools import bench_test
from hal import drive
import config


def test_floor_checks_require_confirmation():
    registered = [check for _, check in bench_test.ORDERED_CHECKS]
    assert bench_test.bt9_straight_drive in registered
    assert bench_test.bt10_single_pivot in registered
    for check in (bench_test.bt9_straight_drive, bench_test.bt10_single_pivot):
        answers = ['r', 'n'] if check is bench_test.bt10_single_pivot else ['n']
        with patch('builtins.input', side_effect=answers), patch.object(bench_test.motion, 'execute') as execute:
            check()
            execute.assert_not_called()
    print('✓ floor confirmation prevents movement')


def test_floor_checks_brake_on_interrupt():
    for check in (bench_test.bt9_straight_drive, bench_test.bt10_single_pivot):
        with patch('builtins.input', side_effect=['r', 'y', '']), patch.object(
                bench_test, '_ask', return_value=True), patch.object(
                bench_test, '_pause'), patch.object(bench_test.motion, 'execute', side_effect=KeyboardInterrupt), patch.object(
                drive, 'stop_motors') as stop:
            try:
                check()
            except KeyboardInterrupt:
                pass
            else:
                assert False, 'interrupt was swallowed'
            stop.assert_called()
    print('✓ interrupted floor motion brakes')


def test_checks_isolate_motion_and_measure_after_braking():
    for check, verb in ((bench_test.bt9_straight_drive, 'F 2'),
                        (bench_test.bt10_single_pivot, 'R'),
                        (bench_test.bt10_single_pivot, 'L')):
        events = []
        def execute(verbs, **kwargs):
            assert verbs == [verb, 'H'], verbs
            assert kwargs['drive_power'] == config.SOAK_DRIVE_POWER
            assert kwargs['turn_power'] == config.SOAK_TURN_POWER
            events.append('move')
        def measure(question):
            assert events[-1] == 'brake', events
            return 85.0
        with patch('builtins.input', return_value='l' if verb == 'L' else 'r'), patch.object(bench_test, '_ask', return_value=True), patch.object(
                bench_test, '_pause'), patch.object(bench_test.motion, 'execute', side_effect=execute), patch.object(
                drive, 'stop_motors', side_effect=lambda: events.append('brake')), patch.object(
                bench_test, '_ask_number', side_effect=measure):
            check()
        assert events == ['move', 'brake'], events
    print('✓ isolated motions brake before measurement')


if __name__ == '__main__':
    test_floor_checks_require_confirmation()
    test_floor_checks_brake_on_interrupt()
    test_checks_isolate_motion_and_measure_after_braking()
    print('ALL 3 BENCH MOTION TESTS PASSED')
