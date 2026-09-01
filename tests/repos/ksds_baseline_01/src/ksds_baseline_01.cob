       IDENTIFICATION DIVISION.
       PROGRAM-ID. KSDSBASE.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT CUST-FILE ASSIGN TO "CUSTOMER"
               ORGANIZATION IS INDEXED
               ACCESS MODE IS DYNAMIC
               RECORD KEY IS WS-CUST-ID
               FILE STATUS IS WS-FS.
       DATA DIVISION.
       FILE SECTION.
       FD  CUST-FILE.
       01  CUST-RECORD.
           05  WS-CUST-ID     PIC 9(6).
           05  WS-CUST-NAME   PIC X(20).
       WORKING-STORAGE SECTION.
       01  WS-FS              PIC X(2).
       PROCEDURE DIVISION.
       MAIN-PARA.
      * 1. Open Output to write initial records
           OPEN OUTPUT CUST-FILE.
           DISPLAY "OPEN OUTPUT FS: " WS-FS.
           
           MOVE 100001 TO WS-CUST-ID.
           MOVE "ALICE               " TO WS-CUST-NAME.
           WRITE CUST-RECORD.
           DISPLAY "WRITE 1 FS: " WS-FS.

           MOVE 100002 TO WS-CUST-ID.
           MOVE "BOB                 " TO WS-CUST-NAME.
           WRITE CUST-RECORD.
           DISPLAY "WRITE 2 FS: " WS-FS.

           CLOSE CUST-FILE.

      * 2. Open I-O to test start, read, rewrite, delete
           OPEN I-O CUST-FILE.
           DISPLAY "OPEN I-O FS: " WS-FS.

      * Read Bob
           MOVE 100002 TO WS-CUST-ID.
           READ CUST-FILE KEY IS WS-CUST-ID.
           DISPLAY "READ BOB FS: " WS-FS " | " WS-CUST-NAME.

      * Rewrite Bob to Robert
           MOVE "ROBERT              " TO WS-CUST-NAME.
           REWRITE CUST-RECORD.
           DISPLAY "REWRITE BOB FS: " WS-FS.

      * Start at 100001 and read next
           MOVE 100001 TO WS-CUST-ID.
           START CUST-FILE KEY IS NOT < WS-CUST-ID.
           DISPLAY "START FS: " WS-FS.

           PERFORM UNTIL WS-FS NOT = "00"
               READ CUST-FILE NEXT RECORD
               IF WS-FS = "00"
                   DISPLAY "READ NEXT: " WS-CUST-ID " | " WS-CUST-NAME
               END-IF
           END-PERFORM.

      * Delete Alice
           MOVE 100001 TO WS-CUST-ID.
           DELETE CUST-FILE.
           DISPLAY "DELETE ALICE FS: " WS-FS.

           CLOSE CUST-FILE.
           GOBACK.
