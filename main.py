"""Five-minute demonstration. Example: python main.py --p 8"""

import argparse
from pathlib import Path

from clinic_system import (
    AppointmentLog, Clinic, Doctor, Lecturer, ManualClock, MedicalLecturer,
    Nurse, Patient, Person, Pharmacist, StaffMemberPatient, StudentPatient,
    VisitorPatient,
)


def show_twist(clinic):
    """Demonstrate whichever one of the four twists P activates."""
    if clinic.twist == 0:  # Waiting list
        clinic.join_waiting_list(patient_id=202, staff_id=102)
        booked = clinic.book(patient_id=203, staff_id=102, start_hour=15)
        clinic.cancel(booked.id)
        offered = clinic.appointments()[-1]
        print(f"WAITLIST: offered #{offered.id} to patient #{offered.patient.id}")

    elif clinic.twist == 1:  # Emergency
        old = clinic.book(patient_id=203, staff_id=102, start_hour=15)
        clinic.flag_emergency(patient_id=202)
        new = clinic.book(patient_id=202, staff_id=102, start_hour=15)
        print(f"EMERGENCY: #{old.id} was bumped; new booking #{new.id}")
        clinic.confirm(new.id)
        clinic.flag_emergency(patient_id=204)
        try:
            clinic.book(patient_id=204, staff_id=102, start_hour=15)
        except ValueError as error:
            print("EXPECTED FAILURE (confirmed cannot be bumped):", error)

    elif clinic.twist == 2:  # Buffer hours
        clinic.book(patient_id=203, staff_id=101, start_hour=15)
        try:
            clinic.book(patient_id=202, staff_id=101, start_hour=17)
        except ValueError as error:
            print("EXPECTED FAILURE (doctor needs 2-hour buffer):", error)
        appointment = clinic.book(patient_id=202, staff_id=101, start_hour=18)
        print(f"BUFFER: hour 18 accepted, appointment #{appointment.id}")

    else:  # Discounts
        for hour, patient_id in enumerate((201, 202, 203), start=13):
            appointment = clinic.book(patient_id=patient_id, staff_id=103,
                                      start_hour=hour)
            print(f"DISCOUNT: patient #{patient_id} pays {appointment.price:.2f}")


def demonstrate(p, log_path):
    clock = ManualClock(0)
    with AppointmentLog(log_path) as log:
        clinic = Clinic(clock=clock, log=log, p=p)
        for staff in (
            Doctor(name="Dr Ncube", person_id=101, p=p),
            Nurse(name="Nurse Dube", person_id=102, p=p),
            Pharmacist(name="Pharmacist Moyo", person_id=103, p=p),
        ):
            clinic.add_staff(staff)

        for patient in (
            StudentPatient(name="Tariro", person_id=201),
            StaffMemberPatient(name="Rudo", person_id=202),
            VisitorPatient(name="Tendai", person_id=203),
            Patient(name="Simba", person_id=204),
        ):
            clinic.add_patient(patient)

        print(f"P={p}; twist={clinic.twist}; current hour={clock.now()}")
        print("FEES (one polymorphic loop):")
        for staff in clinic.staff():
            print(f"  {staff.role()}: {staff.fee()}")

        before = Person.construction_count()
        medical = MedicalLecturer(name="Dr Prof Chirwa", person_id=104,
                                  p=p, module="Computer Networks")
        clinic.add_staff(medical)
        print("MEDICAL LECTURER:", medical.role(), "module:", medical.module,
              "fee:", medical.fee(),
              "Person constructor calls:", Person.construction_count() - before)
        print("LECTURER:", Lecturer(name="Prof M", person_id=105,
                                    module="AI").role())

        first = clinic.book(patient_id=201, staff_id=101, start_hour=10)
        clinic.confirm(first.id)
        try:
            clinic.book(patient_id=201, staff_id=102, start_hour=10)
        except ValueError as error:
            print("EXPECTED FAILURE (patient double booking):", error)

        show_twist(clinic)
        
        if clinic.twist == 3:
            print('PHARMACIST UPCMING SCHEDULE:')
            
            for appointment in clinic.staff_schedule(103):
                print(
                    f'Hour {appointment.start_hour}:'
                    f'patient #{appointment.patient.id}'
                )
                
            try:
                clinic.staff_schedule(999)
            except ValueError as error:
                print('EXPECTED FAILURE (unknown staff schedule):',error)
                
                
                
        clock.set(9)
        try:
            clinic.cancel(first.id)
        except ValueError as error:
            print("EXPECTED FAILURE (too-late cancellation):", error)

        print("FINAL APPOINTMENTS:")
        for appointment in clinic.appointments():
            print(f"  #{appointment.id} {appointment.status.value} "
                  f"at {appointment.start_hour} for patient #{appointment.patient.id}")
        print("Audit file:", Path(log_path))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clinic Appointment System demo")
    parser.add_argument("--p", type=int, required=True,
                        help="Your assigned P: determines fees and P %% 4 twist")
    parser.add_argument("--log", default="appointments.log", help="Audit log filename")
    options = parser.parse_args()
    demonstrate(options.p, options.log)
