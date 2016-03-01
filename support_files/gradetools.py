import timeout, runpy, sys, re


def student(*args, **kwargs):
    '''Provides a message the student will see as feedback'''
    kwargs['file'] = sys.stdout
    print(*args, **kwargs)

def grader(*args, **kwargs):
    '''Provides a message only the grader will see'''
    kwargs['file'] = sys.stderr
    print(*args, **kwargs)

def expect(module, inputs, expected, message, maxtime=0.5, showOtherErrors=True):
    '''A testing harness for console I/O programs.  Parameters are:
    module: the string name of a modeul to run (e.g. "hello" will run hello.py)
    inputs: a list of inputs to simulate the user typing
    expected: a list of expected outputs.  Should be 1 longer than inputs.  The
        first will be matched against things printed before requesting input,
        the second against things between the first and second input, etc.,
        with the last matched against things printed after the last input.
        May contains strings (matched with ==), re.compile(...) objects (matched
        with search), or None (meaning no checks on this piece of input).'''
    timedOut, outputs = timeout.wrapModuleIO(maxtime, module, inputs)
    if timedOut:
        student("File took too long; did you have an infinite loop?")
        grader("Given",inputs,"timed out after",maxtime,"seconds")
        return False
    if type(outputs) is EOFError:
        student("Your program tried to read more inputs than is should have needed.")
        grader("Given",inputs,"tried to read at least",len(inputs)+1,"inputs.")
        return False
    elif isinstance(outputs, BaseException):
        if showOtherErrors:
            student(message, '\n    your program failed with an exception:\n   ',repr(outputs))
        else:
            student(message)
        grader("Given",inputs,"threw exception",outputs)
        return False
    if len(expected) != len(outputs):
        student(message)
        grader("Given",inputs,"got",outputs)
        return False
    cnt=0
    for want,got in zip(expected, outputs):
        cnt += 1
        if want is None: continue
        if 'search' in dir(want):
            if want.search(got): continue
            student(message)
            grader("Given",inputs,"expected output",cnt,"to match regular expression",want.pattern,"but it was",repr(got),"instead")
            return False
        if callable(want):
            if want(got): continue
            student(message)
            grader("Given",inputs,"output",cnt,"should not be",got)
            return False
        if got == want: continue
        student(message)
        grader("Given",inputs,"expected output",cnt,"to be",repr(want),"but it was",repr(got),"instead")
        return False
    return True

def getSource(module):
    if not module.endswith(".py"): module += ".py"
    with open(module) as f:
        txt = f.read()
    return txt

def checkSource(module, *restrings):
    '''Checks one or more regular expression strings or re.compile(...) objects 
    against the .py file of the specified module and returns which ones are 
    satisfied (as a bool or tuple of bools).  If expressions use /text/gim type 
    syntax, the flags will be honored; g will mean use search and no g will mean 
    use fullmatch. Otherwise, re.search is used with no flags.'''
    txt = getSource(module)
    ans = [False for f in restrings]
    for i in range(len(restrings)):
        want = restrings[i]
        if 'search' in dir(want):
            if want.search(txt) is not None: ans[i] = True
        elif type(want) is str:
            if len(want) > 2 and want[0] == '/' and want.rfind('/') != 0:
                end = want.rfind('/')
                want, end = want[1:end], want[end+1:]
                flags = 0
                if 'i' in end: flags |= re.IGNORECASE
                if 'm' in end: flags |= re.MULTILINE
                if 's' in end: flags |= re.DOTALL
                if 'g' in end:
                    if re.search(want, txt, flags) is not None: ans[i] = True
                else:
                    if re.fullmatch(want, txt, flags) is not None: ans[i] = True
            else:
                if re.search(want, txt) is not None: ans[i] = True
        else:
            raise Exception("unexpected type "+str(type(want)))
    if len(ans) == 1: return ans[0]
    else: return tuple(ans)

