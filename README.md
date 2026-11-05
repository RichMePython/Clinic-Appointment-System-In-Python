JULIUS MARANDURE
R2420392
HCS

TADIWANASHE CHINYAMA
R2420423
HCS

# Clinic Appointment System (Python)

This project is a simple clinic appointment management system built using Python and Object-Oriented Programming. It allows patients to book appointments with different staff members, checks for scheduling conflicts, calculates fees, and handles appointment cancellations.

The project also includes four additional features: waiting lists, emergency bookings, buffer hours, and patient discounts.

## How to Run

The project requires Python 3.10 or newer.

To run the program with P = 7:
```
python main.py --p 7
```

To run the tests:
```
python -m unittest discover -s tests -v
```

You can also run the program with different values of P to demonstrate the four features:
```
python main.py --p 8  # Waiting list
python main.py --p 9  # Emergency
python main.py --p 6  # Buffer hours
python main.py --p 7  # Discounts
```

The appointment log is saved in `appointments.log` by default.

## Project Files

| File             | Purpose                                                           |
| ---------------- | ----------------------------------------------------------------- |
| `domain.py`      | Contains Person, Patient, Staff, Appointment and their subclasses |
| `clinic.py`      | Handles bookings, cancellations, conflicts and the four features  |
| `clock.py`       | Provides the current time used by the system                      |
| `audit.py`       | Handles appointment logging                                       |
| `main.py`        | Demonstrates the system                                           |
| `test_clinic.py` | Contains the unit tests                                           |

The domain, clinic, clock and audit files are inside the `clinic_system` folder.

## 1. Class Diagram
```
classDiagram
    class Person {
       <<abstract>>
       -name
       -id
       +role()*
    }
    class Patient {
       -emergency
       +payment_multiplier()
    }
    class Staff {
       <<abstract>>
       -p
       +fee()*
       +buffer_hours()
    }
    class Appointment {
       -id
       -patient
       -staff
       -start_hour
       -status
       +confirm(now)
       +cancel(now, reason)
    }
    class Clinic {
       -patients
       -staff
       -appointments
       +book()
       +confirm()
       +cancel()
    }
    class Lecturer { -module +role() }
    class MedicalLecturer { +role() }
    Person <|-- Patient
    Patient <|-- StudentPatient
    Patient <|-- StaffMemberPatient
    Patient <|-- VisitorPatient
    Person <|-- Staff
    Staff <|-- Doctor
    Staff <|-- Nurse
    Staff <|-- Pharmacist
    Person <|-- Lecturer
    Doctor <|-- MedicalLecturer
    Lecturer <|-- MedicalLecturer
    Clinic o-- Appointment
    Appointment --> Patient
    Appointment --> Staff
    Clinic --> Staff
    Clinic --> Patient
    Clinic --> Clock
    Clinic --> AppointmentLog
    Clock <|-- ManualClock
```

## 2. Encapsulation and Appointment Rules

We used private attributes to prevent other parts of the program from changing important information directly. Where the Clinic needs to return a collection of records, it returns a tuple instead of exposing its internal collection.

Appointments are immutable, meaning their details cannot be changed directly. The `confirm()` and `cancel()` methods create updated appointment records after checking that the requested change is allowed.

An appointment starts as PENDING and can be confirmed or cancelled. Once cancelled, it cannot become active again.

Confirmed appointments can only be cancelled at least two hours before they start. No appointment can be cancelled after its starting time has been reached.

The constructors also check for invalid names, IDs and appointment hours.

## 3. Staff Fees and Polymorphism

Each staff member has a `fee()` method, but the calculation depends on their role.

| Staff      | Fee                |
| ---------- | ------------------ |
| Doctor     | `40 + 5 * (P % 5)` |
| Nurse      | `10 + (P % 3)`     |
| Pharmacist | `5`                |

We used polymorphism so that the program can calculate everyone's fee using the same method call, without checking whether the staff member is a Doctor, Nurse or Pharmacist.

This also makes it easier to add new staff types later.

## 4. Appointment Logging

The system records successful and failed operations in an appointment log.

We used a context manager to handle opening and closing the log file. This ensures that the file is closed even if an operation raises an error.

The Clinic also checks whether an operation is valid before changing appointment records. If writing the audit entry fails, the intended change is not applied to the Clinic's in-memory records.

## 5. Multiple Inheritance

The `MedicalLecturer` class inherits from both `Doctor` and `Lecturer`.

Its `role()` method returns `"Doctor and Lecturer"`, while its fee is calculated using the Doctor's formula.

We used `super()` and Python's Method Resolution Order (MRO) so that the `Person` constructor is called only once, even though both inheritance paths lead to Person.

In Java, Lecturer would have to be an interface because Java does not allow a class to extend two classes.

## 6. Additional Features

The system supports four features, selected using `P % 4`.

**Waiting List (P % 4 = 0)**

Patients can join a staff member's waiting list. When an appointment is cancelled, the Clinic offers the available slot to the first patient in the queue who has no scheduling conflict.

**Emergency (P % 4 = 1)**

Emergency patients can take the place of pending appointments. Confirmed appointments cannot be displaced.

**Buffer Hours (P % 4 = 2)**

Staff members need different amounts of time between appointments. Doctors need two free hours, nurses need one, and pharmacists don't require a gap.

**Discounts (P % 4 = 3)**

Patients pay different percentages depending on their category. Students pay 50%, staff-member patients pay nothing, and visitors pay the full amount.

The patient classes provide these percentages through `payment_multiplier()`.

## 7. Design Decisions

### D1. Why is the two-hour rule in Appointment?

We placed the cancellation rule in `Appointment` because it controls when an appointment is allowed to change its status.

We considered placing it in Clinic, but that would make Clinic responsible for rules that belong to individual appointments. A separate policy class would allow more flexibility, but we felt it would add unnecessary complexity to this project.

### D2. Why use a separate Clock?

We used a separate Clock so that we could control the time during testing.

For example, we can set the clock to exactly two hours before an appointment and test whether cancellation is allowed. We can also test what happens one hour before or after the appointment starts.

Using the computer's actual time would make these tests difficult to repeat.

### D3. What changed when Pharmacist was added?

We only needed to create the Pharmacist subclass and add its objects to the demonstration.

The existing staff loop and Clinic methods did not need to change because they already work with the common Staff methods.

### D4. Why does MedicalLecturer use the Doctor's fee?

MedicalLecturer inherits from Doctor, so it automatically uses the Doctor's `fee()` method.

Python's MRO and cooperative `super()` calls also ensure that the Person constructor runs once.

Without this approach, manually calling both parent constructors could cause Person to be initialized twice.

### D5. What happens if logging fails?

If the system cannot write to the log, it raises an `AuditLogError` and does not apply the intended in-memory change.

The context manager also attempts to close the file when an error occurs. If closing fails, that error is reported.

This approach is suitable for the project, although a larger system would need stronger storage mechanisms to protect records against crashes or power failures.

### D6. Why were the four features implemented this way?

For the waiting list, we placed the responsibility in Clinic because it already manages appointments and can check whether patients are available.

For emergencies, confirmed appointments cannot be displaced because the assignment only allows pending appointments to be bumped.

For buffer hours, each Staff subclass provides its own required gap through `buffer_hours()`. This avoids checking staff types in Clinic.

For discounts, we placed the payment percentages in the Patient subclasses because the amount paid depends on the patient's category.

## 8. Testing and Demonstration

The `main.py` file demonstrates the main system features, including booking appointments, calculating fees, multiple inheritance, the four additional features, and deliberate failures.

The demonstration includes attempts to double-book a patient and cancel a confirmed appointment too late. Both operations are rejected and logged.

We also included unit tests to check that the different classes and methods behave as expected.

The tests can be run using:
```
python -m unittest discover -s tests -v
```
#   C l i n i c - A p p o i n t m e n t - S y s t e m - I n - P y t h o n  
 