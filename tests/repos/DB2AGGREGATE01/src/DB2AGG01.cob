       IDENTIFICATION DIVISION.
       PROGRAM-ID. DB2AGG01.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SQLCA-VARIABLES.
           05  SQLCODE    PIC S9(9) COMP.
           05  SQLSTATE   PIC X(5).
       01  WS-RESULT.
           05  WS-COUNT       PIC S9(9) COMP VALUE 0.
           05  WS-STATUS      PIC X(10) VALUE "ACTIVE    ".
       PROCEDURE DIVISION.
           EXEC SQL
               SELECT COUNT(*)
               INTO :WS-COUNT
               FROM CUSTOMER
               WHERE STATUS = :WS-STATUS
           END-EXEC.
           DISPLAY "SQLCODE: " SQLCODE
           DISPLAY "COUNT: " WS-COUNT.
           GOBACK.
