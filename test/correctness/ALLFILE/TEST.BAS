10 FOR I=1 TO 3
20   OPEN "DATA"+CHR$(48+I) FOR RANDOM AS I
30   FIELD#I, 128 AS A$(I)
40   LSET A$(I) = "test" + STR$(I)
50   PUT#I
60 NEXT
