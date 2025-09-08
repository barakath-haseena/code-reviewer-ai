# bad python code for testing

def  bad_func( x ,y ):return x+ y  # too many spaces, inline return, no formatting

def another_one(  a,b):   print(  a+b) # print instead of logging, spacing issues

def calc(a,b,c): result=a+b*c; return(result) # semicolon, spacing, complexity

for  i  in range(0,10):print( i )  # one-liner loop, print statement

password = "12345"   # hardcoded password (bad practice)

if True:print("Hello")  # inline if with print

# TODO: optimize this function
def  bad_complex(x): 
     if x>0: 
        if x<10: 
           if x%2==0: return "even"
           else:return "odd"
     else:return "negative"
