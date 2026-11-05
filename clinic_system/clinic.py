"""Clinic coordination: bookings, auditing, and all four P % 4 twists."""

from collections import deque
from contextlib import contextmanager

from .audit import AuditLogError
from .domain import Appointment, AppointmentStatus, positive_id, whole_hour


# Clinic invariants:
# - Patients and staff have unique Person IDs across both registers.
# - Appointment IDs are never reused; cancelled appointments stay in history.
# - No patient/staff member has two active bookings at the same start hour.
# - Every appointment is one hour long within hours 0..168.
# - Appointment state changes are validated by Appointment.
# - Twist 2 enforces each staff member's own buffer_hours() policy.
# - Waiting lists contain registered patient IDs without duplicates per staff.
# - A successful audit write happens before every change to Clinic state.
class Clinic:
    def __init__(self, *, clock, log, p):
        self.__clock = clock
        self.__log = log
        self.__p = whole_hour(p, last=10**12, field="P")
        self.__patients = {}
        self.__staff = {}
        self.__appointments = {}
        self.__next_id = 1
        self.__waiting = {}

    @property
    def twist(self):
        return self.__p % 4

    # Return immutable outer collections, never the internal dictionaries.
    def patients(self):
        return tuple(self.__patients.values())

    def staff(self):
        return tuple(self.__staff.values())

    def appointments(self):
        return tuple(self.__appointments.values())

    def waiting_ids(self, staff_id):
        return tuple(self.__waiting.get(staff_id, ()))

    def appointment(self, appointment_id):
        return self._appointment(appointment_id)

    def _write(self, messages):
        """Turn any audit I/O failure into one clear error."""
        try:
            self.__log.write_many(messages)
        except Exception as exc:
            raise AuditLogError("cannot record appointment action") from exc

    @contextmanager
    def _action(self, label):
        """Log failed actions once; callers write success *before* updating data.

        This removes the nested plan()/commit() closures from every method.
        """
        try:
            yield
        except AuditLogError:
            raise  # Don't try to write again to a broken audit log.
        except Exception as exc:
            self._write([f"FAILED {label}: {exc}"])
            raise

    def add_patient(self, patient):
        with self._action(f"add patient #{patient.id}"):
            if patient.id in self.__patients or patient.id in self.__staff:
                raise ValueError("person id already registered")
            self._write([f"REGISTER patient #{patient.id} {patient.name}"])
            self.__patients[patient.id] = patient
        return patient

    def add_staff(self, staff):
        with self._action(f"add staff #{staff.id}"):
            if staff.id in self.__patients or staff.id in self.__staff:
                raise ValueError("person id already registered")
            if staff.p != self.__p:
                raise ValueError("staff P must match Clinic P")
            self._write([f"REGISTER staff #{staff.id} {staff.role()}"])
            self.__staff[staff.id] = staff
        return staff

    def _patient(self, patient_id):
        try:
            return self.__patients[positive_id(patient_id)]
        except KeyError as exc:
            raise ValueError("unknown patient") from exc

    def _staff_member(self, staff_id):
        try:
            return self.__staff[positive_id(staff_id)]
        except KeyError as exc:
            raise ValueError("unknown staff") from exc

    def _appointment(self, appointment_id):
        try:
            return self.__appointments[positive_id(appointment_id)]
        except KeyError as exc:
            raise ValueError("unknown appointment") from exc

    def _active(self, *, excluding=None):
        for appointment in self.__appointments.values():
            if (appointment.id != excluding
                    and appointment.status is not AppointmentStatus.CANCELLED):
                yield appointment

    def _check_free(self, patient, staff, hour, *, excluding=None):
        for existing in self._active(excluding=excluding):
            if existing.patient.id == patient.id and existing.start_hour == hour:
                raise ValueError("patient already has an appointment at this hour")
            if existing.staff.id != staff.id:
                continue
            if existing.start_hour == hour:
                raise ValueError("staff already has an appointment at this hour")
            if self.twist == 2 and abs(existing.start_hour - hour) <= staff.buffer_hours():
                # Each appointment lasts one hour, so a 2h buffer means starts
                # must differ by at least 3 hours (e.g., 10 then 13).
                raise ValueError("staff buffer gap would be violated")

    def book(self, *, patient_id, staff_id, start_hour):
        label = f"book patient #{patient_id} staff #{staff_id} hour {start_hour}"
        with self._action(label):
            patient = self._patient(patient_id)
            staff = self._staff_member(staff_id)
            hour = whole_hour(start_hour, last=167, field="start hour")
            now = self.__clock.now()
            if hour <= now:
                raise ValueError("bookings must be in the future")

            # Twist 1: an emergency may replace a PENDING booking, never CONFIRMED.
            bumped = None
            if self.twist == 1 and patient.is_emergency:
                for existing in self._active():
                    if existing.staff.id == staff.id and existing.start_hour == hour:
                        if existing.status is AppointmentStatus.CONFIRMED:
                            raise ValueError("cannot bump a CONFIRMED appointment")
                        bumped = existing
                        break
            self._check_free(patient, staff, hour,
                             excluding=bumped.id if bumped else None)

            new = Appointment(appointment_id=self.__next_id, patient=patient,
                              staff=staff, start_hour=hour)
            entries = []
            if bumped is not None:
                replacement = bumped.cancel(now, reason="bumped")
                entries.append(f"BUMP #{bumped.id} reason=bumped by emergency patient #{patient.id}")
            entries.append(f"BOOK #{new.id} patient=#{patient.id} staff=#{staff.id} hour={hour} PENDING")

            self._write(entries)
            if bumped is not None:
                self.__appointments[bumped.id] = replacement
            self.__appointments[new.id] = new
            self.__next_id += 1
        return new

    def confirm(self, appointment_id):
        with self._action(f"confirm #{appointment_id}"):
            updated = self._appointment(appointment_id).confirm(self.__clock.now())
            self._write([f"CONFIRM #{updated.id}"])
            self.__appointments[updated.id] = updated
        return updated

    def cancel(self, appointment_id, *, reason="requested"):
        with self._action(f"cancel #{appointment_id}"):
            previous = self._appointment(appointment_id)
            updated = previous.cancel(self.__clock.now(), reason=reason)
            entries = [f"CANCEL #{updated.id} reason={updated.cancel_reason}"]

            # Twist 0: offer the cancelled slot to the first eligible person.
            offer = None
            chosen_id = None
            if self.twist == 0:
                for candidate_id in self.__waiting.get(previous.staff.id, ()):
                    candidate = self._patient(candidate_id)
                    try:
                        self._check_free(candidate, previous.staff,
                                         previous.start_hour, excluding=previous.id)
                    except ValueError:  # This candidate is busy; try the next.
                        continue
                    chosen_id = candidate_id
                    offer = Appointment(appointment_id=self.__next_id,
                                        patient=candidate, staff=previous.staff,
                                        start_hour=previous.start_hour)
                    entries.append(f"WAITLIST OFFER #{offer.id} to patient #{candidate_id} "
                                   f"staff=#{previous.staff.id} hour={previous.start_hour} PENDING")
                    break

            self._write(entries)
            self.__appointments[updated.id] = updated
            if offer is not None:
                self.__appointments[offer.id] = offer
                self.__next_id += 1
                self.__waiting[previous.staff.id].remove(chosen_id)
        return updated
    
    
    def staff_schedule(self, staff_id):
        with self._action('fview schedule staff #{staff_id}'):
            
            staff = self._staff_member(staff_id)
            now = self.__clock.now()
            
            upcoming = sorted(
                (appointment for appointment in self._active()
                 if appointment.staff.id == staff.id and appointment.start_hour >= now
                 ),
                
                key = lambda appointment: appointment.start_hour
                )
            
            self._write([f'VIEW SCHEDULE staff = #{staff.id}'])
            
        return tuple(upcoming)
    
    
            
            

    def join_waiting_list(self, *, patient_id, staff_id):
        label = f"waitlist patient #{patient_id} staff #{staff_id}"
        with self._action(label):
            if self.twist != 0:
                raise ValueError("waiting lists only apply when P mod 4 = 0")
            patient = self._patient(patient_id)
            staff = self._staff_member(staff_id)
            if patient.id in self.__waiting.get(staff.id, ()):
                raise ValueError("already on waiting list")
            self._write([f"WAITLIST JOIN patient=#{patient.id} staff=#{staff.id}"])
            self.__waiting.setdefault(staff.id, deque()).append(patient.id)

    def flag_emergency(self, *, patient_id, flagged=True):
        label = f"emergency patient #{patient_id}"
        with self._action(label):
            if self.twist != 1:
                raise ValueError("emergency rules only apply when P mod 4 = 1")
            patient = self._patient(patient_id)
            if flagged is not True and flagged is not False:
                raise ValueError("flagged must be true or false")
            self._write([f"EMERGENCY patient=#{patient.id} flagged={flagged}"])
            patient._set_emergency(flagged)
