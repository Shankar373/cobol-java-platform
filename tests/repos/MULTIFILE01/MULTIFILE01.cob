       IDENTIFICATION DIVISION.
       PROGRAM-ID. MULTIFILE01.
       
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT FILE-A ASSIGN TO "data/source/input-a.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT FILE-B ASSIGN TO "data/source/input-b.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT OUT-A ASSIGN TO "data/reports/report-a.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT OUT-B ASSIGN TO "data/reports/report-b.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
               
       DATA DIVISION.
       FILE SECTION.
       FD  FILE-A.
       01  REC-A.
           05  A-ID        PIC X(5).
           05  A-VAL       PIC X(10).
           
       FD  FILE-B.
       01  REC-B.
           05  B-ID        PIC X(5).
           05  B-VAL       PIC X(15).
           
       FD  OUT-A.
       01  OUT-REC-A.
           05  OA-ID       PIC X(5).
           05  OA-VAL      PIC X(10).
           
       FD  OUT-B.
       01  OUT-REC-B.
           05  OB-ID       PIC X(5).
           05  OB-VAL      PIC X(15).
           
       WORKING-STORAGE SECTION.
       01  WS-EOF-A        PIC X VALUE 'N'.
       01  WS-EOF-B        PIC X VALUE 'N'.
       
       PROCEDURE DIVISION.
           OPEN INPUT FILE-A FILE-B
           OPEN OUTPUT OUT-A OUT-B
           
           PERFORM UNTIL WS-EOF-A = 'Y'
               READ FILE-A
                   AT END MOVE 'Y' TO WS-EOF-A
                   NOT AT END
                       MOVE A-ID TO OA-ID
                       MOVE A-VAL TO OA-VAL
                       WRITE OUT-REC-A
               END-READ
           END-PERFORM
           
           PERFORM UNTIL WS-EOF-B = 'Y'
               READ FILE-B
                   AT END MOVE 'Y' TO WS-EOF-B
                   NOT AT END
                       MOVE B-ID TO OB-ID
                       MOVE B-VAL TO OB-VAL
                       WRITE OUT-REC-B
               END-READ
           END-PERFORM
           
           CLOSE FILE-A FILE-B OUT-A OUT-B
           STOP RUN.
