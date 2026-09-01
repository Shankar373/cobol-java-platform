       IDENTIFICATION DIVISION.
       PROGRAM-ID. FILESTAT01.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT SEQ-FILE ASSIGN TO "ws-output-file.txt"
               FILE STATUS IS WS-FILE-STATUS.
       DATA DIVISION.
       FILE SECTION.
       FD  SEQ-FILE.
       01  FILE-REC PIC X(30).
       WORKING-STORAGE SECTION.
       01  WS-FILE-STATUS PIC XX.
       01  WS-EOF-FLAG PIC X VALUE 'N'.
       01  WS-COUNT PIC 9(3) VALUE 0.
       PROCEDURE DIVISION.
       MAIN-PARA.
      * Open for OUTPUT and write 3 records
           OPEN OUTPUT SEQ-FILE
           PERFORM VARYING WS-COUNT FROM 1 BY 1 UNTIL WS-COUNT > 3
               MOVE 'RECORD_' TO FILE-REC
               MOVE WS-COUNT TO FILE-REC(11:2)
               WRITE FILE-REC
               DISPLAY 'Write ' WS-COUNT ': FILE_STATUS = ' WS-FILE-STATUS
           END-PERFORM
           CLOSE SEQ-FILE
           DISPLAY 'After close: FILE_STATUS = ' WS-FILE-STATUS
      * Reopen for INPUT and read the records back
           OPEN INPUT SEQ-FILE
           DISPLAY 'After reopen INPUT: FILE_STATUS = ' WS-FILE-STATUS
           MOVE 'N' TO WS-EOF-FLAG
           PERFORM UNTIL WS-EOF-FLAG = 'Y'
               READ SEQ-FILE
               AT END
                   DISPLAY 'EOF reached, FILE_STATUS = ' WS-FILE-STATUS
                   MOVE 'Y' TO WS-EOF-FLAG
               NOT AT END
                   DISPLAY 'Read record: ' FILE-REC
                   DISPLAY 'FILE_STATUS after read = ' WS-FILE-STATUS
               END-READ
           END-PERFORM
      * Attempt one more read past EOF (expected status 10)
           READ SEQ-FILE
           AT END
               DISPLAY 'Past EOF read: FILE_STATUS = ' WS-FILE-STATUS ' (expected 10)'
           NOT AT END
               DISPLAY 'Should not reach here'
           END-READ
           CLOSE SEQ-FILE
           STOP RUN.
