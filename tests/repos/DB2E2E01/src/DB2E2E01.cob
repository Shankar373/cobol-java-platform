       IDENTIFICATION DIVISION.
       PROGRAM-ID. DB2E2E01.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SQLCA-VARIABLES.
           05  SQLCODE    PIC S9(9) COMP.
           05  SQLSTATE   PIC X(5).
       01  WS-TEST-DATA.
           05  WS-ID      PIC S9(9) COMP VALUE 5001.
           05  WS-NAME    PIC X(20) VALUE "INITIAL VAL".
           05  WS-NAME-UP PIC X(20) VALUE "UPDATED VAL".
           05  WS-OUT     PIC X(20) VALUE SPACES.
       PROCEDURE DIVISION.
      * 1. INSERT Row
           EXEC SQL
               INSERT INTO DB2_TEST_E2E (ID, NAME)
               VALUES (:WS-ID, :WS-NAME)
           END-EXEC.
           DISPLAY "INSERT SQLCODE: " SQLCODE.

      * 2. SELECT Row
           EXEC SQL
               SELECT NAME INTO :WS-OUT
               FROM DB2_TEST_E2E
               WHERE ID = :WS-ID
           END-EXEC.
           DISPLAY "SELECT-1 SQLCODE: " SQLCODE.
           DISPLAY "SELECT-1 NAME: " WS-OUT.

      * 3. UPDATE Row
           EXEC SQL
               UPDATE DB2_TEST_E2E
               SET NAME = :WS-NAME-UP
               WHERE ID = :WS-ID
           END-EXEC.
           DISPLAY "UPDATE SQLCODE: " SQLCODE.

      * 4. SELECT Row Again
           EXEC SQL
               SELECT NAME INTO :WS-OUT
               FROM DB2_TEST_E2E
               WHERE ID = :WS-ID
           END-EXEC.
           DISPLAY "SELECT-2 SQLCODE: " SQLCODE.
           DISPLAY "SELECT-2 NAME: " WS-OUT.

      * 5. DELETE Row
           EXEC SQL
               DELETE FROM DB2_TEST_E2E
               WHERE ID = :WS-ID
           END-EXEC.
           DISPLAY "DELETE SQLCODE: " SQLCODE.
           GOBACK.
