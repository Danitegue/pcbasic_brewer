5 OPEN "OUTPUT" FOR OUTPUT AS 2
10 OPEN "r",1,"test"
20 PRINT #1,"Hello"
30 PUT 1,1
40 GET 1,1
50 INPUT #1,a$
60 PRINT #2, a$
70 CLOSE
