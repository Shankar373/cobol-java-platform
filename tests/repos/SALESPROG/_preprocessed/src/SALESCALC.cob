       IDENTIFICATION DIVISION.
       PROGRAM-ID. SALESCALC.
       DATA DIVISION.
       LINKAGE SECTION.
       COPY CALCLNK.
       PROCEDURE DIVISION USING CALC-LINKAGE.
       CALC-LOGIC.
           COMPUTE LK-TOTAL =
               LK-QTY * LK-UNIT-PRICE * (1 - LK-DISCOUNT)
           EVALUATE TRUE
               WHEN LK-TOTAL > 50000
                   MOVE "PLATINUM" TO LK-TIER
               WHEN LK-TOTAL > 10000
                   MOVE "GOLD"     TO LK-TIER
               WHEN LK-TOTAL > 1000
                   MOVE "SILVER"   TO LK-TIER
               WHEN OTHER
                   MOVE "BRONZE"   TO LK-TIER
           END-EVALUATE
           GOBACK.
