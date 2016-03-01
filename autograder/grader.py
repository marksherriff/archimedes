#!/usr/bin/env python

'''
Designed to run autograders in java or python (on our server...)

Mostly just a big code dump without functions... sorry.

Depends on https://pypi.python.org/pypi/python-dateutil
'''

import csv, re
import subprocess, os, sys, shutil, os.path
from glob import glob
import dateutil.parser, dateutil.relativedelta, datetime


#### Ensure we don't run two of these at the same time; it's not thread-safe
iam = os.readlink('/proc/self')
for proc in glob('/proc/*/cmdline'):
    if proc.split('/')[2] == iam: continue
    if proc.split('/')[2] == 'self': continue
    with open(proc) as c:
        full=c.read()
        if 'grader.py' in full:
            print('grader.py is already running')
            sys.exit(1)

def dictofdict(csvpath):
    '''Parse a csv file into a dict-of-dict
    result[1st column][1st row] = contents
    '''
    ans = {}
    with open(csvpath) as fp:
        r = csv.reader(fp)
        try:
            header = r.__next__()
        except:
            print('csv',csvpath,'had no header')
            return {}
        for row in r:
            ans[row[0]] = {}
            for i in range(1, len(header)):
                if len(row) > i:
                    ans[row[0]][header[i]] = row[i]
                else:
                    ans[row[0]][header[i]] = ""
    return ans

## A couple of JUnit/Java stack trace regexs; probably not very robust yet
packageAt = re.compile(r'\tat [a-z]')
exception = re.compile(r'[A-Z][a-zA-Z]*Exception')

## keep track of who we graded
updatedusers = []

def runAndCollect(*popenargs, maxtime=None, **kwargs):
    '''similar to check_output and getstatusoutput in the subprocess module
    returns status, stdout, stderr or raises an exception'''
    with subprocess.Popen(*popenargs, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True) as process:
        try:
            stdout, stderr = process.communicate(None, timeout=maxtime)
            return process.poll(), stdout, stderr
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            raise subprocess.TimeoutExpired(process.args, maxtime, output=(stdout, stderr))
        except:
            process.kill()
            process.wait()
            raise
    return -1, None, None    

def parseJunitOutput(output):
    '''An ad-hoc method for cleaning up JUnit output
    returns (what to show student, what to show grader)
    '''
    ans = []
    testout = ""
    exs = set()
    for line in output.split('\n'):
#       line = line.strip()
        if packageAt.search(line): continue
        testout += line + "\n"
        if 'AssertionError' in line:
            part = line[line.find(':')+1:].strip()
            if 'prompt' in part: continue
            if ' expected:' in line:
                part = part[0:part.find(' expected:')]
            ans.append(part)
        if 'ComparisonFailure' in line:
            part = line[line.find(':')+1:].strip()
            if ' expected:' in line:
                part = part[0:part.find(' expected:')]
            ans.append(part)
        if 'test timed out' in line:
            ans.append('timed out (requested too much input, looped forever, or network trouble)')
        for ex in exception.finditer(line):
            exs.add(ex.group(0))
        if 'OK (' in line: ans.append("passed all of our tests. Good job!")
        if 'Tests run' in line: ans.append(line)
    if len(exs) > 0: ans.append('generated exceptions: ' + ' '.join(exs))
    if len(ans) == 0:
        ans.append("could not run tests; code using JOptionPane or System.exit can cause this")
    return ans, testout

def parseJavacErrors(output):
    '''An ad-hoc method for cleaning up javac compiler error messages
    returns a list of messages to show the student
    '''
    lines = [line.strip() for line in output.split('\n') if line.strip()]
    ans = set()
    for i in range(len(lines)):
        line = lines[i]
        if 'symbol:' in line and i < len(lines)-1:
            symbol   = line[line.find(':'):].strip()
            line = lines[i+1]
            location = line[line.find(':'):].strip()
            if 'JUnit' in location or 'Test' in location:
                ans.add('failed to work with our test suite; check that you named things correctly')
            else:
                ans.add("didn't find "+symbol+' in '+location)
    return list(sorted(list(ans))) 



# get the current time and location
now = datetime.datetime.now()
root = os.getcwd()

# all paths are hard-coded...
for path in glob('../html/*/uploads/assignments.csv'): # for each course under the new system
    classdir = '/'.join(path.split('/')[:-2])
    if os.path.exists(classdir+'/.htNOGRADE'):
        print('skipping .htNOGRADE', classdir)
        continue
    if os.path.islink(classdir):
        print('skipping symlink', classdir)
        continue
    uploads = '/'.join(path.split('/')[:-1])
    respath = classdir+'/.htresults/'
    dod = dictofdict(path)
    for slug in sorted(dod.keys()): # for each assignment of that course
        rest = dod[slug]

        due = dateutil.parser.parse(rest['duedate'])
        close = due + dateutil.relativedelta.relativedelta(days=(len(rest['late'].split())+1))
        if 'unittests' not in rest or len(rest['unittests']) < 4:
            print(slug,'in',classdir,'has no unit tests')
            continue # does not specifiy unit tests
        if close < now:
            print(slug,'is closed')
            continue # has closed a day ago or more, so skip it
        if rest['opendate'] and dateutil.parser.parse(rest['opendate']) > now:
            print(slug,'is not yet open')
            continue # has not yet opened, so skip it
        print('doing', slug,'in',classdir)

        delay = dateutil.relativedelta.relativedelta(hours=0)
        if rest['fbdelay']: delay = dateutil.relativedelta.relativedelta(hours=float(rest['fbdelay']))

        for sendpath in glob(uploads+'/'+slug+'/*/*/'): # for each submitter
            try:
                sec=sendpath.split("/")[-3]
                uid=sendpath.split("/")[-2]
                mtime = datetime.datetime.fromtimestamp(os.stat(sendpath).st_mtime)
                if sec != 'staff' and mtime > now - delay: # ignore delay for staff submissions
                    continue # too new; skip it
                res = respath+slug+'-'+uid+'.txt'
                if os.path.exists(res):
                    lastres = datetime.datetime.fromtimestamp(os.stat(res).st_mtime)
                    if mtime <= lastres:
                        continue # already graded this one
                for old in glob('.work/*'):
                    if os.path.isdir(old): shutil.rmtree(old)
                    else: os.unlink(old)
                nothing=True
                for f in glob(sendpath+"*"):
                    if os.path.isfile(f):
                        shutil.copy2(f,".work/")
                    nothing=False
                if nothing: continue
                for f in rest['support'].split('|'):
                    if f:
                        shutil.copy2(classdir+"/.htsln/"+f, ".work/")
                if nothing: continue
                for f in rest['unittests'].split('|'):
                    shutil.copy2(classdir+"/.htsln/"+f, ".work/")
                if nothing: continue
                feedback = []
                
                if rest['unittests'][-3:] == '.py':
                    try:
                        # idea: student sees stdout, grader sees stderr
                        # implementation: student sees .htresults/slug-uid.txt; grader sees .htresults/slug-uid-testfile.testout
                        os.chdir(".work")
                        for testcase in rest['unittests'].split('|'):
                            tested = testcase[0:testcase.rfind('.')]
                            if tested[0:5] == 'test_': tested = tested[5:]
                            if tested[-5:0] == '_test': tested = tested[:-5]
                            print('running',testcase,'for',uid,'using',tested)
                            try:
                                status, output, errput = runAndCollect(['python3', testcase], maxtime=20)
                            except subprocess.TimeoutExpired as e:
                                output,errput = e.output
                                output += "\n[tests timed out; you might have an infinite loop?]"
                                errput += "\n[tests timed out after 20 seconds]"
                            except subprocess.CalledProcessError as e: 
                                output,errput = e.output
                            with open("../"+respath+slug+"-"+uid+"-"+tested+".testout", 'w') as f:
                                f.write(errput.strip())
                                updatedusers.append(uid+"-"+slug)
                            feedback.append(tested+": "+output)
                    finally:
                        os.chdir(root)          
                        with open(respath+slug+"-"+uid+'.txt', 'w') as f:
                            f.write('\n'.join(feedback))
                elif rest['unittests'][-5:] == '.java':
                    try:
                        os.chdir(".work")
                        classpath = '.:../hamcrest.jar:../junit.jar' # might need to change this path...
                        for f in rest['support'].split('|'):
                            if f.endswith('.jar'):
                                classpath += ":"+os.path.basename(f)
                        # print ['javac','-cp',classpath]+glob('*.java')
                        output = subprocess.check_output(['javac','-cp',classpath]+glob('*.java'), stderr=subprocess.STDOUT)
                        for testcase in rest['unittests'].split('|'):
                            print('running',testcase,'for',uid)
                            tested = testcase[0:testcase.rfind('.')]
                            if 'Test' in tested and tested[0:4] != 'Test': tested = tested[0:tested.rfind('Test')]
                            if 'Test' in tested and tested[0:4] == 'Test': tested = tested[4:]
                            if 'JUnit' in tested: tested = tested[0:tested.rfind('JUnit')]
                            try:
                                output = subprocess.check_output(['java','-cp',classpath, 'org.junit.runner.JUnitCore', testcase[0:testcase.rfind('.')]], stderr=subprocess.STDOUT)
                            except subprocess.CalledProcessError as e: 
                                output=e.output
                            msgs, testout = parseJunitOutput(output)
                            with open("../"+respath+slug+"-"+uid+"-"+tested+".testout", 'w') as f:
                                f.write(testout.strip())
                                updatedusers.append(uid+"-"+slug)
                            for f in glob(".ht-io-*"):
                                os.rename(f, "../"+respath+slug+"-"+uid+"-io-"+tested+".txt")
                            for line in msgs:
                                feedback.append(tested+": "+line)
                    except subprocess.CalledProcessError as e:
                        feedback.append('Unable to compile and run tests')
                        for line in parseJavacErrors(e.output):
                            feedback.append('  - '+line)
                    finally:
                        os.chdir(root)          
                        with open(respath+slug+"-"+uid+'.txt', 'w') as f:
                            f.write('\n'.join(feedback))
                else:
                    print("Unknown unittest type: "+rest['unittests'])
            except BaseException as e:
                print("grading system error for",sendpath,e)

# log that we did an update (in /tmp for now)
if len(updatedusers) > 0:
    with open("/tmp/query.txt","a") as f:
        f.write(now.ctime()+": updated feedback for ["+(", ".join(sorted(updatedusers)))+"]\n")
