#!/usr/bin/env python3
"""Controller-owned unittest lifecycle receipt; stdout is never a verdict."""
import json
import os
from pathlib import Path
import runpy
import sys
import types
import traceback
import unittest


def run(source, destination):
    receipt=dict(version=1,complete=False,tests=[],error=None)
    def save():
        encoded=json.dumps(receipt,sort_keys=True).encode()
        if len(encoded)>1000000:raise ValueError('typed_receipt_too_large')
        temporary=destination.with_suffix('.pending')
        with temporary.open('wb') as stream:
            stream.write(encoded);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,destination)
    skipped_parents=set();passed_subtests=set()
    class Result(unittest.TestResult):
        def startTest(self,test):
            super().startTest(test)
            if len(receipt['tests'])>=10000 or any(row['id']==test.id() for row in receipt['tests']):raise ValueError('duplicate_or_excessive_test_identity')
            receipt['tests'].append(dict(id=test.id(),status='running'));save()
        def outcome(self,test,status):
            row=next(row for row in receipt['tests'] if row['id']==test.id())
            if row['status'] not in ('running','failed'):raise ValueError('duplicate_test_outcome')
            row['status']=status;save()
        def addSuccess(self,test):super().addSuccess(test);self.outcome(test,'passed')
        def addFailure(self,test,err):super().addFailure(test,err);traceback.print_exception(*err);self.outcome(test,'failed')
        def addError(self,test,err):super().addError(test,err);traceback.print_exception(*err);self.outcome(test,'failed')
        def addSkip(self,test,reason):
            super().addSkip(test,reason)
            if hasattr(test,'test_case'):skipped_parents.add(test.test_case.id());save()
            else:self.outcome(test,'skipped')
        def addExpectedFailure(self,test,err):super().addExpectedFailure(test,err);self.outcome(test,'expected_failure')
        def addUnexpectedSuccess(self,test):super().addUnexpectedSuccess(test);self.outcome(test,'unexpected_success')
        def addSubTest(self,test,subtest,err):
            super().addSubTest(test,subtest,err)
            if err is not None:traceback.print_exception(*err);self.outcome(test,'failed')
            else:passed_subtests.add(test.id())
        def stopTest(self,test):
            super().stopTest(test)
            row=next(row for row in receipt['tests'] if row['id']==test.id())
            if test.id() in skipped_parents and row['status'] in ('running','passed'):row['status']='passed' if test.id() in passed_subtests else 'skipped'
            save()
    save()
    try:
        sys.path.insert(0,str(Path.cwd()))
        module=types.ModuleType('__nightshift_test__');sys.modules[module.__name__]=module
        module.__dict__.update(runpy.run_path(str(source),run_name=module.__name__))
        result=Result();unittest.defaultTestLoader.loadTestsFromModule(module).run(result)
        receipt['complete']=True;save()
        return 0 if result.wasSuccessful() else 1
    except BaseException as error:
        receipt['error']=type(error).__name__+':'+str(error)[:2000];save();return 2


if __name__=='__main__':
    raise SystemExit(run(Path(sys.argv[1]),Path(sys.argv[2])))
