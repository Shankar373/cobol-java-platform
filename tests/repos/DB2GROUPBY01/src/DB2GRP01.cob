       IDENTIFICATION DIVISION.
       PROGRAM-ID. DB2GRP01.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SQLCA-VARIABLES.
           05  SQLCODE    PIC S9(9) COMP.
           05  SQLSTATE   PIC X(5).
       01  WS-DEPT-COUNT.
           05  WS-DEPT-ID     PIC S9(9) COMP VALUE 0.
           05  WS-COUNT       PIC S9(9) COMP VALUE 0.
           05  WS-MIN-COUNT   PIC S9(9) COMP VALUE 1.
       PROCEDURE DIVISION.
           EXEC SQL
               DECLARE C1 CURSOR FOR
               SELECT DEPT_ID, COUNT(*)
               FROM CUSTOMER
               GROUP BY DEPT_ID
               HAVING COUNT(*) > :WS-MIN-COUNT
               ORDER BY DEPT_ID
           END-EXEC.
           EXEC SQL OPEN C1 END-EXEC.
           DISPLAY "OPEN SQLCODE: " SQLCODE
           IF SQLCODE < 0
               DISPLAY "CURSOR OPEN FAILED SQLCODE: " SQLCODE
               DISPLAY "CURSOR OPEN FAILED SQLSTATE: " SQLSTATE
               GOBACK
           END-IF.
           PERFORM UNTIL SQLCODE NOT EQUAL 0
               EXEC SQL
                   FETCH C1 INTO :WS-DEPT-ID, :WS-COUNT
               END-EXEC
               EVALUATE TRUE
                   WHEN SQLCODE EQUAL 0
                       DISPLAY "DEPT: " WS-DEPT-ID " COUNT: " WS-COUNT
                   WHEN SQLCODE EQUAL 100
                       CONTINUE
                   WHEN OTHER
                       DISPLAY "FETCH ERROR SQLCODE: " SQLCODE
                       DISPLAY "FETCH ERROR SQLSTATE: " SQLSTATE
               END-EVALUATE
           END-PERFORM.
           EXEC SQL CLOSE C1 END-EXEC.
           GOBACK.

