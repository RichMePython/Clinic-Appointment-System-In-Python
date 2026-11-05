"""Injectable clock: never consults the machine's system time."""
from abc import ABC, abstractmethod
from .domain import whole_hour


class Clock(ABC):
    @abstractmethod
    def now(self):
        """Return the current whole hour in [0, 168]."""


class ManualClock(Clock):
    def __init__(self, hour=0):
        self.__hour = whole_hour(hour)

    def now(self):
        return self.__hour

    def set(self, hour):
        self.__hour = whole_hour(hour)
