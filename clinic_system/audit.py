"""A single-context, exception-safe audit log."""


class AuditLogError(RuntimeError):
    pass


class AppointmentLog:
    def __init__(self, filepath):
        self.__filepath = filepath
        self.__handle = None
        self.__used = False

    def __enter__(self):
        if self.__used:
            raise AuditLogError("log context cannot be reopened")
        self.__used = True
        try:
            self.__handle = open(self.__filepath, "a", encoding="utf-8")
        except OSError as exc:
            raise AuditLogError("cannot open appointment log") from exc
        print("[log] opened")
        return self

    def write_many(self, lines):
        if self.__handle is None:
            raise AuditLogError("log is not open")
        try:
            # One write and flush per action, before the associated state change.
            self.__handle.write("".join(line + "\n" for line in lines))
            self.__handle.flush()
        except OSError as exc:
            raise AuditLogError("cannot write appointment log") from exc

    def __exit__(self, exc_type, exc, traceback):
        handle, self.__handle = self.__handle, None
        if handle is not None:
            try:
                handle.close()
            except OSError as close_exc:
                print("[log] close FAILED")
                raise AuditLogError("cannot close appointment log") from close_exc
            print("[log] closed")
        return False  # Never swallow an error in the clinic operation.
