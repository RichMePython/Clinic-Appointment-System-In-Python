"""People and immutable appointment records for the clinic mini-project."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from operator import index


def whole_hour(value, *, last=168, field="hour"):
    """Reject fractions, booleans and hours outside the specified week."""
    if value is True or value is False:
        raise ValueError(f"{field} must be a whole number")
    try:
        number = index(value)
    except (TypeError, AttributeError) as exc:
        raise ValueError(f"{field} must be a whole number") from exc
    if not 0 <= number <= last:
        raise ValueError(f"{field} must be between 0 and {last}")
    return number


def positive_id(value, *, field="id"):
    if value is True or value is False:
        raise ValueError(f"{field} must be a positive integer")
    try:
        number = index(value)
    except (TypeError, AttributeError) as exc:
        raise ValueError(f"{field} must be a positive integer") from exc
    if number <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return number


def nonempty(value, *, field="name"):
    # Deliberately rely on the value's string behaviour instead of type tags.
    try:
        cleaned = value.strip()
    except AttributeError as exc:
        raise ValueError(f"{field} must be non-empty text") from exc
    if not cleaned:
        raise ValueError(f"{field} must be non-empty text")
    return cleaned


class Person(ABC):
    """Abstract common base. Cooperative initialization supports diamond MRO."""

    __constructed = 0

    def __init__(self, *, name, person_id, **kwargs):
        super().__init__(**kwargs)
        self.__name = nonempty(name)
        self.__id = positive_id(person_id)
        Person.__constructed += 1

    @property
    def name(self):
        return self.__name

    @property
    def id(self):
        return self.__id

    @classmethod
    def construction_count(cls):
        return Person.__constructed

    @abstractmethod
    def role(self):
        """Describe the person without external type checks."""


class Patient(Person):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__emergency = False

    def role(self):
        return "Patient"

    def payment_multiplier(self):
        """Polymorphic discount hook; a regular patient pays full price."""
        return 1.0

    @property
    def is_emergency(self):
        return self.__emergency

    def _set_emergency(self, flagged):
        """Clinic-only convention: a flag never changes the appointment directly."""
        self.__emergency = flagged


class StudentPatient(Patient):
    def payment_multiplier(self):
        return 0.5


class StaffMemberPatient(Patient):
    def payment_multiplier(self):
        return 0.0


class VisitorPatient(Patient):
    def payment_multiplier(self):
        return 1.0


class Staff(Person, ABC):
    def __init__(self, *, p, **kwargs):
        self.__p = whole_hour(p, last=10**12, field="P")
        super().__init__(**kwargs)

    @property
    def p(self):
        return self.__p

    @abstractmethod
    def fee(self):
        """Return the staff member's fee."""

    def buffer_hours(self):
        """Subclasses can override; Clinic never checks the staff's type."""
        return 0


class Doctor(Staff):
    def role(self):
        return "Doctor"

    def fee(self):
        return 40 + 5 * (self.p % 5)

    def buffer_hours(self):
        return 2


class Nurse(Staff):
    def role(self):
        return "Nurse"

    def fee(self):
        return 10 + (self.p % 3)

    def buffer_hours(self):
        return 1


class Pharmacist(Staff):
    def role(self):
        return "Pharmacist"

    def fee(self):
        return 5


class Lecturer(Person):
    def __init__(self, *, module, **kwargs):
        self.__module = nonempty(module, field="module")
        super().__init__(**kwargs)

    @property
    def module(self):
        return self.__module

    def role(self):
        return "Lecturer"


class MedicalLecturer(Doctor, Lecturer):
    """Diamond: Doctor -> Staff -> Lecturer -> Person (Person once)."""

    def __init__(self, *, module, **kwargs):
        super().__init__(module=module, **kwargs)

    def role(self):
        return "Doctor and Lecturer"

    # Inherits Doctor.fee(): medical work uses the doctor's charge.


class AppointmentStatus(Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


# Appointment invariants:
# - ID is positive; patient and staff references are fixed after creation.
# - Start is an integer in [0, 167] and end = start + 1 <= 168.
# - Status is exactly PENDING, CONFIRMED, or CANCELLED.
# - CANCELLED is terminal. A confirmed appointment can only be cancelled
#   at least 2 hours before the start; no cancellation at/after start.
# - Cancellation reason exists iff status is CANCELLED.
# - Objects are immutable; transitions produce a new snapshot.
@dataclass(frozen=True, slots=True, init=False)
class Appointment:
    __id: int
    __patient: Patient
    __staff: Staff
    __start_hour: int
    __status: AppointmentStatus
    __cancel_reason: str | None

    def __init__(self, *, appointment_id, patient, staff, start_hour,
                 status=AppointmentStatus.PENDING, cancel_reason=None):
        object.__setattr__(self, "_Appointment__id", positive_id(appointment_id, field="appointment id"))
        object.__setattr__(self, "_Appointment__patient", patient)
        object.__setattr__(self, "_Appointment__staff", staff)
        object.__setattr__(self, "_Appointment__start_hour", whole_hour(start_hour, last=167, field="start hour"))
        if status not in (AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED, AppointmentStatus.CANCELLED):
            raise ValueError("invalid appointment status")
        if (status is AppointmentStatus.CANCELLED) != (cancel_reason is not None):
            raise ValueError("a cancellation reason is required iff cancelled")
        object.__setattr__(self, "_Appointment__status", status)
        object.__setattr__(self, "_Appointment__cancel_reason", cancel_reason)

    @property
    def id(self):
        return self.__id

    @property
    def patient(self):
        return self.__patient

    @property
    def staff(self):
        return self.__staff

    @property
    def start_hour(self):
        return self.__start_hour

    @property
    def end_hour(self):
        return self.__start_hour + 1

    @property
    def status(self):
        return self.__status

    @property
    def cancel_reason(self):
        return self.__cancel_reason

    @property
    def price(self):
        return self.__staff.fee() * self.__patient.payment_multiplier()

    def confirm(self, now):
        if self.__status is not AppointmentStatus.PENDING:
            raise ValueError("only PENDING appointments can be confirmed")
        if now >= self.__start_hour:
            raise ValueError("appointment has already started")
        return self._with_status(AppointmentStatus.CONFIRMED)

    def cancel(self, now, *, reason):
        if self.__status is AppointmentStatus.CANCELLED:
            raise ValueError("cancelled appointments cannot return")
        if now >= self.__start_hour:
            raise ValueError("appointment has already started")
        if self.__status is AppointmentStatus.CONFIRMED and self.__start_hour - now < 2:
            raise ValueError("too late")
        return self._with_status(AppointmentStatus.CANCELLED,
                                 reason=nonempty(reason, field="cancellation reason"))

    def _with_status(self, status, *, reason=None):
        """Construct an updated snapshot without duplicating the field arguments."""
        return Appointment(appointment_id=self.__id, patient=self.__patient,
                           staff=self.__staff, start_hour=self.__start_hour,
                           status=status, cancel_reason=reason)
