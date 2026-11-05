import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from clinic_system import (
    AppointmentLog, AppointmentStatus, AuditLogError, Clinic, Doctor, Lecturer,
    ManualClock, MedicalLecturer, Nurse, Patient, Person, Pharmacist,
    StaffMemberPatient, StudentPatient, VisitorPatient,
)


class ClinicTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.log_path = Path(self.temp.name) / "audit.txt"
        self.clock = ManualClock(0)
        self.log = AppointmentLog(self.log_path)
        self.log.__enter__()
        self.p = 4
        self.clinic = self.build_clinic(self.p)

    def tearDown(self):
        self.log.__exit__(None, None, None)
        self.temp.cleanup()

    def build_clinic(self, p):
        clinic = Clinic(clock=self.clock, log=self.log, p=p)
        clinic.add_staff(Doctor(name="Doctor", person_id=1, p=p))
        clinic.add_staff(Nurse(name="Nurse", person_id=2, p=p))
        clinic.add_staff(Pharmacist(name="Pharmacist", person_id=3, p=p))
        for i in range(11, 17):
            clinic.add_patient(Patient(name=f"Patient {i}", person_id=i))
        return clinic

    def log_text(self):
        return self.log_path.read_text(encoding="utf-8")

    def test_people_validation(self):
        with self.assertRaises(ValueError):
            Patient(name="   ", person_id=13)
        with self.assertRaises(ValueError):
            Doctor(name="X", person_id=0, p=4)
        with self.assertRaises(ValueError):
            Nurse(name="N", person_id=True, p=4)
        with self.assertRaises(ValueError):
            Patient(name="X", person_id=1.5)

    def test_unique_person_ids_across_patient_and_staff(self):
        with self.assertRaisesRegex(ValueError, "person id already"):
            self.clinic.add_patient(Patient(name="Duplicate", person_id=1))
        self.assertIn("FAILED add patient #1", self.log_text())

    def test_fees(self):
        self.assertEqual(Doctor(name="D", person_id=99, p=9).fee(), 60)
        self.assertEqual(Nurse(name="N", person_id=99, p=8).fee(), 12)
        self.assertEqual(Pharmacist(name="P", person_id=99, p=2).fee(), 5)

    def test_one_person_for_medical_lecturer(self):
        before = Person.construction_count()
        lecturer = MedicalLecturer(name="ML", person_id=88, p=9, module="OOP")
        self.assertEqual(Person.construction_count() - before, 1)
        self.assertEqual(lecturer.role(), "Doctor and Lecturer")
        self.assertEqual(lecturer.fee(), 60)
        self.assertEqual(lecturer.module, "OOP")
        self.assertEqual(Lecturer(name="L", person_id=89, module="AI").role(), "Lecturer")

    def test_status_transitions_and_terminal(self):
        one = self.clinic.book(patient_id=11, staff_id=1, start_hour=10)
        confirmed = self.clinic.confirm(one.id)
        self.assertIs(one.status, AppointmentStatus.PENDING)  # Immutable snapshot.
        self.assertIs(confirmed.status, AppointmentStatus.CONFIRMED)
        self.clock.set(8)
        cancelled = self.clinic.cancel(one.id)
        self.assertIs(cancelled.status, AppointmentStatus.CANCELLED)
        with self.assertRaises(ValueError):
            self.clinic.confirm(one.id)
        with self.assertRaises(ValueError):
            self.clinic.cancel(one.id)

    def test_too_late_confirmed_cancellation(self):
        appt = self.clinic.book(patient_id=11, staff_id=1, start_hour=10)
        self.clinic.confirm(appt.id)
        self.clock.set(9)
        with self.assertRaisesRegex(ValueError, "too late"):
            self.clinic.cancel(appt.id)
        self.assertIs(self.clinic.appointment(appt.id).status, AppointmentStatus.CONFIRMED)
        self.assertIn(f"FAILED cancel #{appt.id}: too late", self.log_text())

    def test_cancelled_appointment_cannot_start_or_cancel_at_start(self):
        appt = self.clinic.book(patient_id=11, staff_id=1, start_hour=10)
        self.clock.set(10)
        with self.assertRaisesRegex(ValueError, "started"):
            self.clinic.cancel(appt.id)
        with self.assertRaisesRegex(ValueError, "started"):
            self.clinic.confirm(appt.id)

    def test_exact_two_hours_allows_confirmed_cancellation(self):
        appt = self.clinic.book(patient_id=11, staff_id=1, start_hour=10)
        self.clinic.confirm(appt.id)
        self.clock.set(8)
        self.assertIs(self.clinic.cancel(appt.id).status, AppointmentStatus.CANCELLED)

    def test_patient_and_staff_collision(self):
        self.clinic.book(patient_id=11, staff_id=1, start_hour=10)
        with self.assertRaisesRegex(ValueError, "patient already"):
            self.clinic.book(patient_id=11, staff_id=2, start_hour=10)
        with self.assertRaisesRegex(ValueError, "staff already"):
            self.clinic.book(patient_id=12, staff_id=1, start_hour=10)

    def test_bounds_and_clock(self):
        with self.assertRaises(ValueError):
            self.clinic.book(patient_id=11, staff_id=1, start_hour=168)
        with self.assertRaises(ValueError):
            self.clinic.book(patient_id=11, staff_id=1, start_hour=10.5)
        with self.assertRaises(ValueError):
            self.clinic.book(patient_id=11, staff_id=1, start_hour=True)
        appt = self.clinic.book(patient_id=11, staff_id=1, start_hour=167)
        self.assertEqual(appt.end_hour, 168)
        self.clock.set(168)
        with self.assertRaises(ValueError):
            self.clinic.book(patient_id=12, staff_id=1, start_hour=167)

    def test_defensive_views_and_immutable_appointment(self):
        appt = self.clinic.book(patient_id=11, staff_id=1, start_hour=10)
        self.assertEqual(len(self.clinic.appointments()), 1)
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            appt._Appointment__status = AppointmentStatus.CANCELLED
        with self.assertRaises(AttributeError):
            self.clinic.appointments().append(appt)
        with self.assertRaises(AttributeError):
            self.clinic.staff().clear()

    def test_waiting_list_fifo_skips_conflicts(self):
        # P=4, twist 0.
        self.clinic.join_waiting_list(patient_id=11, staff_id=2)
        self.clinic.join_waiting_list(patient_id=12, staff_id=2)
        self.clinic.book(patient_id=11, staff_id=1, start_hour=12)
        old = self.clinic.book(patient_id=13, staff_id=2, start_hour=12)
        self.clinic.cancel(old.id)
        offer = self.clinic.appointments()[-1]
        self.assertEqual(offer.patient.id, 12)
        self.assertIs(offer.status, AppointmentStatus.PENDING)
        self.assertEqual(self.clinic.waiting_ids(2), (11,))
        self.assertIn("WAITLIST OFFER", self.log_text())

    def test_waiting_list_duplicate_logged(self):
        self.clinic.join_waiting_list(patient_id=11, staff_id=2)
        with self.assertRaisesRegex(ValueError, "already"):
            self.clinic.join_waiting_list(patient_id=11, staff_id=2)
        self.assertIn("FAILED waitlist", self.log_text())

    def test_emergency_bump_only_pending(self):
        clinic = self.build_clinic(5)
        old = clinic.book(patient_id=11, staff_id=2, start_hour=12)
        clinic.flag_emergency(patient_id=12)
        fresh = clinic.book(patient_id=12, staff_id=2, start_hour=12)
        self.assertEqual(clinic.appointment(old.id).cancel_reason, "bumped")
        self.assertEqual(fresh.status, AppointmentStatus.PENDING)
        clinic.confirm(fresh.id)
        clinic.flag_emergency(patient_id=13)
        with self.assertRaisesRegex(ValueError, "CONFIRMED"):
            clinic.book(patient_id=13, staff_id=2, start_hour=12)

    def test_non_emergency_cannot_bump(self):
        clinic = self.build_clinic(5)
        clinic.book(patient_id=11, staff_id=2, start_hour=12)
        with self.assertRaises(ValueError):
            clinic.book(patient_id=12, staff_id=2, start_hour=12)

    def test_buffer_staff_specific(self):
        clinic = self.build_clinic(6)
        clinic.book(patient_id=11, staff_id=1, start_hour=10)
        with self.assertRaisesRegex(ValueError, "buffer"):
            clinic.book(patient_id=12, staff_id=1, start_hour=12)
        clinic.book(patient_id=12, staff_id=1, start_hour=13)
        clinic.book(patient_id=13, staff_id=2, start_hour=10)
        with self.assertRaisesRegex(ValueError, "buffer"):
            clinic.book(patient_id=14, staff_id=2, start_hour=11)
        clinic.book(patient_id=14, staff_id=2, start_hour=12)
        clinic.book(patient_id=15, staff_id=3, start_hour=10)
        clinic.book(patient_id=16, staff_id=3, start_hour=11)

    def test_discount_polymorphism(self):
        clinic = self.build_clinic(7)
        clinic.add_patient(StudentPatient(name="S", person_id=31))
        clinic.add_patient(StaffMemberPatient(name="E", person_id=32))
        clinic.add_patient(VisitorPatient(name="V", person_id=33))
        self.assertEqual(clinic.book(patient_id=31, staff_id=3, start_hour=10).price, 2.5)
        self.assertEqual(clinic.book(patient_id=32, staff_id=3, start_hour=11).price, 0)
        self.assertEqual(clinic.book(patient_id=33, staff_id=3, start_hour=12).price, 5)


    def test_staff_schedule_sorts_and_filters(self):
        
        self.clinic.book(patient_id = 11, staff_id = 3, start_hour =15)
        self.clinic.book(patient_id = 12, staff_id = 3, start_hour =10)
        
        cancelled = self.clinic.book(patient_id = 13, staff_id = 3, start_hour = 12)
        
        self.clinic.cancel(cancelled.id)
        
        self.assertEqual(
            [a.start_hour for a in self.clinic.staff_schedule(3)],[15]
        )
        self.assertIsInstance(self.clinic.staff_schedule(3), tuple)
        
        self.assertEqual('VIEW SCHEDULE staff = #3', self.log_text()
        )
        
        
    def test_staff_schedule_rejects_uknown_staff_and_logs(self):
        with self.assertRaisesRegex(ValueError, 'unknown staff'):
            self.clinic.staff_schedule(99)
            
        self.assertIn('FAILED view schedule staff #999: unknown staff', self.log_text())
        
        
    def test_no_state_mutation_if_audit_write_fails(self):
        class BrokenLog:
            def write_many(self, lines):
                raise OSError("disk failed")
        clinic = Clinic(clock=self.clock, log=BrokenLog(), p=4)
        with self.assertRaises(AuditLogError):
            clinic.add_patient(Patient(name="X", person_id=101))
        self.assertEqual(clinic.patients(), ())

    def test_no_booking_or_bump_if_audit_write_fails(self):
        class FailingLog:
            def write_many(self, lines):
                raise OSError("disk full")

        clinic = self.build_clinic(5)
        original = clinic.book(patient_id=11, staff_id=2, start_hour=12)
        clinic.flag_emergency(patient_id=12)
        # Swap in a log that fails every write, then attempt an emergency bump.
        clinic._Clinic__log = FailingLog()
        with self.assertRaises(AuditLogError):
            clinic.book(patient_id=12, staff_id=2, start_hour=12)
        self.assertIs(clinic.appointment(original.id).status, AppointmentStatus.PENDING)
        self.assertEqual(len(clinic.appointments()), 1)

    def test_no_confirm_or_cancel_if_audit_write_fails(self):
        class FailingLog:
            def write_many(self, lines):
                raise OSError("disk full")

        appointment = self.clinic.book(patient_id=11, staff_id=1, start_hour=12)
        self.clinic._Clinic__log = FailingLog()
        with self.assertRaises(AuditLogError):
            self.clinic.confirm(appointment.id)
        self.assertIs(self.clinic.appointment(appointment.id).status, AppointmentStatus.PENDING)
        with self.assertRaises(AuditLogError):
            self.clinic.cancel(appointment.id)
        self.assertIs(self.clinic.appointment(appointment.id).status, AppointmentStatus.PENDING)


class LoggingTests(unittest.TestCase):
    def test_exactly_one_open_close_despite_exception(self):
        from contextlib import redirect_stdout
        from io import StringIO
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "log.txt"
            output = StringIO()
            with self.assertRaisesRegex(RuntimeError, "deliberate"):
                with redirect_stdout(output):
                    with AppointmentLog(destination) as log:
                        log.write_many(["about to fail"])
                        raise RuntimeError("deliberate")
            self.assertEqual(output.getvalue().count("[log] opened"), 1)
            self.assertEqual(output.getvalue().count("[log] closed"), 1)
            self.assertIn("about to fail", destination.read_text())


if __name__ == "__main__":
    unittest.main()
