"""Robust dynamic-palm state machine for one-shot page turns."""

from collections import deque
from enum import Enum, auto
from typing import Deque, Optional


class PageAction(Enum):
    NONE = auto()
    PREVIOUS = auto()
    NEXT = auto()


class PageTurnState(Enum):
    WAITING = auto()
    ARMING = auto()
    TRACKING = auto()
    COOLDOWN = auto()
    PAUSED = auto()


class PageTurnFSM:
    def __init__(
        self,
        arm_duration_ms: float = 150,
        min_swipe_distance: float = 0.18,
        max_vertical_drift: float = 0.10,
        max_swipe_duration_ms: float = 700,
        cooldown_ms: float = 600,
        fist_hold_ms: float = 700,
        arm_stability_radius: float = 0.04,
        min_swipe_duration_ms: float = 120,
        min_swipe_speed: float = 0.35,
        direction_consistency: float = 0.75,
    ) -> None:
        self.arm_duration_ms = arm_duration_ms
        self.min_swipe_distance = min_swipe_distance
        self.max_vertical_drift = max_vertical_drift
        self.max_swipe_duration_ms = max_swipe_duration_ms
        self.cooldown_ms = cooldown_ms
        self.fist_hold_ms = fist_hold_ms
        self.arm_stability_radius = arm_stability_radius
        self.min_swipe_duration_ms = min_swipe_duration_ms
        self.min_swipe_speed = min_swipe_speed
        self.direction_consistency = direction_consistency
        self._state = PageTurnState.WAITING
        self._started_at: Optional[float] = None
        self._anchor_x: Optional[float] = None
        self._anchor_y: Optional[float] = None
        self._active_hand = ""
        self._samples: Deque[tuple[float, float, float]] = deque(maxlen=64)
        self._cooldown_until = 0.0
        self._fist_started_at: Optional[float] = None
        self._fist_latched = False

    def update(
        self,
        gesture: str,
        palm_x: Optional[float],
        palm_y: Optional[float],
        timestamp: float,
        handedness: str = "",
    ) -> PageAction:
        if self._handle_fist(gesture, timestamp):
            return PageAction.NONE
        if self._state == PageTurnState.PAUSED:
            return PageAction.NONE

        is_open = gesture == "Open_Palm" and palm_x is not None and palm_y is not None
        if self._state == PageTurnState.COOLDOWN:
            if timestamp >= self._cooldown_until and not is_open:
                self._reset()
            return PageAction.NONE
        if not is_open:
            self._reset()
            return PageAction.NONE

        if self._state == PageTurnState.WAITING:
            self._start_arming(palm_x, palm_y, timestamp, handedness)
            return PageAction.NONE

        if self._active_hand and handedness and handedness != self._active_hand:
            self._start_arming(palm_x, palm_y, timestamp, handedness)
            return PageAction.NONE

        if self._state == PageTurnState.ARMING:
            if (
                abs(palm_x - self._anchor_x) > self.arm_stability_radius
                or abs(palm_y - self._anchor_y) > self.arm_stability_radius
            ):
                self._start_arming(palm_x, palm_y, timestamp, handedness)
                return PageAction.NONE
            if (timestamp - self._started_at) * 1000 < self.arm_duration_ms:
                return PageAction.NONE
            self._state = PageTurnState.TRACKING
            self._started_at = timestamp
            self._anchor_x = palm_x
            self._anchor_y = palm_y
            self._samples.clear()
            self._samples.append((timestamp, palm_x, palm_y))
            return PageAction.NONE

        elapsed_ms = (timestamp - self._started_at) * 1000
        if elapsed_ms > self.max_swipe_duration_ms:
            self._start_arming(palm_x, palm_y, timestamp, handedness)
            return PageAction.NONE

        self._samples.append((timestamp, palm_x, palm_y))
        y_values = [sample[2] for sample in self._samples]
        if max(y_values) - min(y_values) > self.max_vertical_drift:
            self._start_arming(palm_x, palm_y, timestamp, handedness)
            return PageAction.NONE

        dx = palm_x - self._anchor_x
        if abs(dx) < self.min_swipe_distance:
            return PageAction.NONE

        duration = timestamp - self._started_at
        if duration * 1000 < self.min_swipe_duration_ms:
            self._start_arming(palm_x, palm_y, timestamp, handedness)
            return PageAction.NONE
        if abs(dx) / duration < self.min_swipe_speed:
            self._start_arming(palm_x, palm_y, timestamp, handedness)
            return PageAction.NONE
        if self._trajectory_consistency(dx) < self.direction_consistency:
            self._start_arming(palm_x, palm_y, timestamp, handedness)
            return PageAction.NONE

        self._state = PageTurnState.COOLDOWN
        self._cooldown_until = timestamp + self.cooldown_ms / 1000
        self._clear_tracking()
        return PageAction.NEXT if dx < 0 else PageAction.PREVIOUS

    def _trajectory_consistency(self, total_dx: float) -> float:
        direction = 1.0 if total_dx > 0 else -1.0
        movement = 0.0
        aligned = 0.0
        samples = list(self._samples)
        for previous, current in zip(samples, samples[1:]):
            segment = current[1] - previous[1]
            movement += abs(segment)
            aligned += max(0.0, segment * direction)
        return aligned / movement if movement else 0.0

    def _handle_fist(self, gesture: str, timestamp: float) -> bool:
        if gesture != "Closed_Fist":
            self._fist_started_at = None
            self._fist_latched = False
            return False
        if self._fist_started_at is None:
            self._fist_started_at = timestamp
        elif (
            not self._fist_latched
            and (timestamp - self._fist_started_at) * 1000 >= self.fist_hold_ms
        ):
            self.toggle_pause()
            self._fist_latched = True
        return True

    def _start_arming(
        self, palm_x: float, palm_y: float, timestamp: float, handedness: str
    ) -> None:
        self._state = PageTurnState.ARMING
        self._started_at = timestamp
        self._anchor_x = palm_x
        self._anchor_y = palm_y
        self._active_hand = handedness
        self._samples.clear()

    def pause(self) -> None:
        self._state = PageTurnState.PAUSED
        self._clear_tracking()

    def resume(self) -> None:
        self._reset()

    def toggle_pause(self) -> None:
        if self._state == PageTurnState.PAUSED:
            self.resume()
        else:
            self.pause()

    def _reset(self) -> None:
        self._state = PageTurnState.WAITING
        self._clear_tracking()

    def _clear_tracking(self) -> None:
        self._started_at = None
        self._anchor_x = None
        self._anchor_y = None
        self._active_hand = ""
        self._samples.clear()

    @property
    def state(self) -> PageTurnState:
        return self._state

    @property
    def is_paused(self) -> bool:
        return self._state == PageTurnState.PAUSED
