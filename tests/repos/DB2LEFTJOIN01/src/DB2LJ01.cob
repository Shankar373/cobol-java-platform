       IDENTIFICATION DIVISION.
       PROGRAM-ID. DB2LJ01.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SQLCA-VARIABLES.
           05  SQLCODE    PIC S9(9) COMP.
           05  SQLSTATE   PIC X(5).
       01  WS-RESULT.
           05  WS-CUST-NAME   PIC X(20) VALUE SPACES.
           05  WS-DEPT-NAME   PIC X(20) VALUE SPACES.
           05  WS-CUST-ID     PIC S9(9) COMP VALUE 101.
           05  WS-DEPT-IND    PIC S9(4) COMP VALUE 0.
       PROCEDURE DIVISION.
           EXEC SQL
               SELECT C.CUST_NAME, D.DEPT_NAME
               INTO :WS-CUST-NAME, :WS-DEPT-NAME :WS-DEPT-IND
               FROM CUSTOMER C LEFT OUTER JOIN DEPT D
               ON C.DEPT_ID = D.DEPT_ID
               WHERE C.CUST_ID = :WS-CUST-ID
           END-EXEC.
           DISPLAY "SQLCODE: " SQLCODE
           DISPLAY "CUST: " WS-CUST-NAME
           IF WS-DEPT-IND = -1
               DISPLAY "DEPT: NULL"
           ELSE
               DISPLAY "DEPT: " WS-DEPT-NAME
           END-IF.
           GOBACK.
