       IDENTIFICATION DIVISION.
       PROGRAM-ID. DB2SEL01.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           EXEC SQL INCLUDE SQLCA END-EXEC.
       01  DB-NAME PIC X(50)
           VALUE 'modernization_db@host.docker.internal'.
       01  DB-USER PIC X(10) VALUE 'modernize'.
       01  DB-PASS PIC X(10) VALUE 'modernize'.
       01  WS-CUSTOMER.
           05  WS-CUST-ID   PIC S9(9) VALUE 101.
           05  WS-CUST-NAME PIC X(20) VALUE SPACES.
       PROCEDURE DIVISION.
           EXEC SQL
               CONNECT :DB-USER IDENTIFIED BY :DB-PASS USING :DB-NAME
           END-EXEC.
           EXEC SQL
               SELECT CUST_NAME
               INTO :WS-CUST-NAME
               FROM CUSTOMER
               WHERE CUST_ID = :WS-CUST-ID
           END-EXEC.
           DISPLAY "SQLCODE: " SQLCODE
           DISPLAY "SQLSTATE: " SQLSTATE
           DISPLAY "CUST-NAME: " WS-CUST-NAME
           GOBACK.
