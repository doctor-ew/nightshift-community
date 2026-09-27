#!/usr/bin/env python3
"""Controller-owned unittest lifecycle receipts; derived from the #96 adapter."""
import json
import os
from pathlib import Path
import runpy
import sys
import unittest


def run(script,output,binding):
    path=Path(output)
    report=dict(version=1,adapter='python-unittest-v1',binding=binding,runtime=sys.version,complete=False,runs=[],error=None)
    def save():
        text=json.dumps(report)
        if len(text.encode())>1000000:raise ValueError('verification_events_too_large')
        temporary=path.with_suffix('.tmp')
        with temporary.open('w') as stream:stream.write(text);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    seen=set()
    original=unittest.TextTestRunner.run
    def observed(runner,test):
        row=dict(complete=False,counts={},tests=[]);report['runs'].append(row);save()
        skipped_parents=set();passed_subtests=set()
        class Result(unittest.TextTestResult):
            def startTest(self,test):
                super().startTest(test)
                if len(seen)>=10000 or test.id() in seen:raise ValueError('duplicate_or_excessive_test_identity')
                seen.add(test.id());row['tests'].append(dict(id=test.id(),status='running'));save()
            def outcome(self,test,status):
                item=next(item for item in row['tests'] if item['id']==test.id())
                if item['status'] not in ('running','failed','errors'):raise ValueError('duplicate_test_outcome')
                item['status']=status;save()
            def addSuccess(self,test):super().addSuccess(test);self.outcome(test,'passed')
            def addFailure(self,test,error):super().addFailure(test,error);self.outcome(test,'failed')
            def addError(self,test,error):super().addError(test,error);self.outcome(test,'errors')
            def addSkip(self,test,reason):
                super().addSkip(test,reason)
                if hasattr(test,'test_case'):skipped_parents.add(test.test_case.id());save()
                else:self.outcome(test,'skipped')
            def addExpectedFailure(self,test,error):super().addExpectedFailure(test,error);self.outcome(test,'expected_failures')
            def addUnexpectedSuccess(self,test):super().addUnexpectedSuccess(test);self.outcome(test,'unexpected_successes')
            def addSubTest(self,test,subtest,error):
                super().addSubTest(test,subtest,error)
                if error is not None:self.outcome(test,'failed')
                else:passed_subtests.add(test.id())
            def stopTest(self,test):
                super().stopTest(test)
                item=next(item for item in row['tests'] if item['id']==test.id())
                if test.id() in skipped_parents and item['status'] in ('running','passed'):item['status']='passed' if test.id() in passed_subtests else 'skipped'
                save()
        runner.resultclass=Result
        result=original(runner,test)
        counts={key:0 for key in ('total','passed','failed','errors','skipped','expected_failures','unexpected_successes')}
        for item in row['tests']:
            if item['status']=='running':raise ValueError('incomplete_test_lifecycle')
            counts[item['status']]+=1;counts['total']+=1
        row.update(complete=True,counts=counts);save();return result
    unittest.TextTestRunner.run=observed
    save();code=0
    sys.argv=[script];sys.path.insert(0,str(Path(script).resolve().parent));sys.path.insert(0,str(Path.cwd()))
    try:
        namespace=runpy.run_path(script,run_name='__main__')
        if not report['runs']:
            import types
            module=types.ModuleType('__nightshift_test__');module.__dict__.update(namespace)
            result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromModule(module))
            code=0 if result.wasSuccessful() else 1
    except SystemExit as error:code=error.code if type(error.code) is int else 0 if error.code is None else 1
    except BaseException as error:
        report['error']=type(error).__name__+':'+str(error)[:2000];save();raise
    report['complete']=True;save();return code


if __name__=='__main__':raise SystemExit(run(*sys.argv[1:]))
