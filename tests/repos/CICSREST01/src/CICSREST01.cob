       IDENTIFICATION DIVISION.
       PROGRAM-ID. CICSREST01.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-VARIABLES.
           05  WS-INPUT                PIC X(10) VALUE SPACES.
           05  WS-OUTPUT               PIC X(10) VALUE SPACES.
           05  WS-COM                  PIC X(10) VALUE "INITIALVAL".
       PROCEDURE DIVISION.
       MAIN-PARA.
           EXEC CICS RECEIVE
               MAP('INPUTMAP')
               MAPSET('MSET')
               INTO(WS-INPUT)
           END-EXEC.
           DISPLAY "RECEIVED INPUT: " WS-INPUT
           IF WS-INPUT = "LINK"
               EXEC CICS LINK
                   PROGRAM('LINKPROG')
                   COMMAREA(WS-COM)
                   LENGTH(10)
               END-EXEC
               DISPLAY "LINK EIBRESP: " EIBRESP
               DISPLAY "LINK COMMAREA: " WS-COM
           END-IF.
           IF WS-INPUT = "XCTL"
               EXEC CICS XCTL
                   PROGRAM('LINKPROG')
                   COMMAREA(WS-COM)
               END-EXEC
           END-IF.
           MOVE WS-COM TO WS-OUTPUT.
           EXEC CICS SEND
               MAP('OUTMAP')
               MAPSET('MSET')
               FROM(WS-OUTPUT)
           END-EXEC.
           GOBACK.
