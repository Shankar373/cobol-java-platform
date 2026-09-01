       IDENTIFICATION DIVISION.
       PROGRAM-ID. DB2SUB01.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SQLCA-VARIABLES.
           05  SQLCODE    PIC S9(9) COMP.
           05  SQLSTATE   PIC X(5).
       01  WS-RESULT.
           05  WS-NAME        PIC X(20) VALUE SPACES.
           05  WS-AMT         PIC S9(9) COMP VALUE 500.
       PROCEDURE DIVISION.
           EXEC SQL
               SELECT CUST_NAME
               INTO :WS-NAME
               FROM CUSTOMER
               WHERE CUST_ID IN (
                   SELECT CUSTOMER_ID
                   FROM ORDERS
                   WHERE AMOUNT > :WS-AMT
               )
           END-EXEC.
           DISPLAY "SQLCODE: " SQLCODE
           DISPLAY "FOUND: " WS-NAME.
           GOBACK.
