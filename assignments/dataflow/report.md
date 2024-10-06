# First pass notes on constant prop and elimination

- The outputs are correct for everything ecept for mem and long. Long results in timeouts and mem results in pointer malloc errors
-> bug had nothing to do with memory, just binary search had reassining to variable i. This was not saved in the constants table in my code

