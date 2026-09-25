#!/usr/bin/env python3
"""Offline fixture: exercise installed-format dispatch into persistent ticket reports."""
import json, os, pathlib, subprocess, tempfile, shutil
ROOT=pathlib.Path(__file__).resolve().parents[1]

with tempfile.TemporaryDirectory(prefix='nightshift-35-boundary-') as tmp:
    base=pathlib.Path(tmp); project=base/'project'; project.mkdir(); binary=base/'bin';binary.mkdir()
    def run(argv, env=None):
        result=subprocess.run(argv,cwd=project,env=env,capture_output=True,text=True)
        if result.returncode: raise AssertionError((argv[:3],result.returncode,result.stderr[-1000:]))
        return result.stdout
    run(['git','init','-q']);run(['git','config','user.name','fixture']);run(['git','config','user.email','fixture@local'])
    run(['git','remote','add','origin','https://github.com/doctor-ew/nightshift-community.git'])
    (project/'README.md').write_text('fixture');run(['git','add','.']);run(['git','commit','-qm','fixture'])
    ticket=project/'docs'/'35';ticket.mkdir(parents=True)
    (ticket/'ticket.json').write_text(json.dumps({'source':'gh','repository':'doctor-ew/nightshift-community','source_id':'35','url':'https://github.com/doctor-ew/nightshift-community/issues/35'}))
    (project/'input.md').write_text('Offline fixture; return empty verified claim list.')
    contract={'status':'SUCCESS','reason':'offline fixture','attempts':1,'artifacts':{'branch':'','diff':'','provider':'codex','model':'fixture'},'rules_fired':[],'results':{'claims':[]}}
    mock = "#!/usr/bin/env python3\nimport json,pathlib,sys\nargs=sys.argv[1:]\n"
    codex=mock+"if args[:2]==['login','status']: print('Logged in using ChatGPT');sys.exit(0)\n"+"out=args[args.index('--output-last-message')+1]\n"+"pathlib.Path(out).write_text("+repr(json.dumps(contract))+")\n"+"print(json.dumps({'type':'turn.completed','usage':{'input_tokens':100,'cached_input_tokens':40,'cache_write_input_tokens':60,'output_tokens':10,'reasoning_output_tokens':5}}))\n"
    claude=mock+"if args[:1]==['auth']: print(json.dumps({'loggedIn':True,'authMethod':'claude.ai','apiProvider':'firstParty'}));sys.exit(0)\n"+"print(json.dumps({'type':'result','subtype':'success','usage':{'input_tokens':20,'cache_read_input_tokens':4,'cache_creation_input_tokens':2,'output_tokens':3},'modelUsage':{'claude-fixture':{'inputTokens':20,'cacheReadInputTokens':4,'cacheCreationInputTokens':2,'outputTokens':3,'costUSD':0.02}},'total_cost_usd':0.02,'structured_output':"+repr(contract)+"}))\n"
    for name,content in [('codex',codex),('claude',claude)]:
        f=binary/name;f.write_text(content);f.chmod(0o755)
    ROUTING=str(base/'routing.json')
    env=dict(os.environ,PATH=str(binary)+os.pathsep+os.environ['PATH'],NIGHTSHIFT_ROUTING_FILE=ROUTING,NIGHTSHIFT_PROJECT_DIR=str(project),PYTHONDONTWRITEBYTECODE='1')
    (base/'home').mkdir();env['HOME']=str(base/'home')
    for key in ['NIGHTSHIFT_RUN_ID','NIGHTSHIFT_RUN_DIR','NIGHTSHIFT_TICKET_JSON','NIGHTSHIFT_ROLE_CHILD']:
        env.pop(key,None)
    metrics=ROOT/'scripts/nightshift-run-metrics.py'
    for provider in ['codex','claude']:
        routing=json.loads((ROOT/'routing.json').read_text())
        routing['roles']['nightshift-code-fact-extractor']['gears']['1']={'provider':provider,'model':'fixture'}
        pathlib.Path(ROUTING).write_text(json.dumps(routing))
        context=json.loads(run(['python3',str(metrics),'init','--project',str(project),'--branch','none'],env))
        callenv=dict(env,NIGHTSHIFT_RUN_ID=context['run_id'],NIGHTSHIFT_RUN_DIR=context['run_dir'])
        args=['bash',str(ROOT/'scripts/nightshift-agent.sh'),'nightshift-code-fact-extractor','--task','35','--gear','1','--auth','subscription','--in',str(project/'input.md'),'--out',str(project/(provider+'.json'))]
        # Exercise inherited ticket attribution without an explicit --task.
        if provider=='claude':
            args.remove('--task');args.remove('35')
            callenv['NIGHTSHIFT_TICKET_JSON']=json.dumps({'source':'gh','repository':'doctor-ew/nightshift-community','source_id':'35'})
        run(args,callenv)
    report=json.loads(run(['python3',str(metrics),'ticket-report','--project',str(project),'--source','gh','--repository','doctor-ew/nightshift-community','--source-id','35'],env))
    assert report['run_count']==2,report
    assert report['usage']['known_subtotal']['total']==139,report
    assert report['cost']['provider_reported_estimate_usd']==0.02,report
    assert report['cost']['pricing_sources'],report
    assert report['completeness']['unmeasured_orchestrator_count']==2,report
    print(json.dumps({'status':'PASS','providers':['codex','claude'],'runs':2,'total':139,'provider_estimate_usd':0.02,'billed_usd':report['cost']['actual_billed_usd'],'pricing_provenance_preserved':True}))

    shutil.copy(ROOT/'nightshift.toml',project/'.nightshift.toml')
    shutil.copy(ROOT/'routing.json',project/'routing.json')
    # A single stage transport supplies usage; a process exit is not factory approval.
    handoff=base/'handoff.json';handoff.write_text('{}')
    factory_env=dict(env,NIGHTSHIFT_UPDATE_GUARD='1',NIGHTSHIFT_DASHBOARD='off',NIGHTSHIFT_HOME=str(base/'home'),NIGHTSHIFT_OUTPUT_CHILD='1',NIGHTSHIFT_OUTPUT_MODE='verbose',NIGHTSHIFT_PIPELINE_STAGE='product',NIGHTSHIFT_PIPELINE_TASK='35',NIGHTSHIFT_STAGE_HANDOFF=str(handoff),NIGHTSHIFT_STAGE_RECEIPT=str(base/'receipt.json'))
    run(['bash',str(ROOT/'scripts/nightshift-factory.sh'),'gh:35','--project',str(project),'--provider','claude','--branch','none'],factory_env)
    report=json.loads(run(['python3',str(metrics),'ticket-report','--project',str(project),'--source','gh','--repository','doctor-ew/nightshift-community','--source-id','35'],env))
    assert report['run_count']==3,report
    assert report['usage']['known_subtotal']['total']==168,report
    assert report['cost']['provider_reported_estimate_usd']==0.04,report
    snapshot=json.loads(run(['bash',str(ROOT/'scripts/nightshift-dashboard.sh'),'--project',str(project),'--json'],env))
    assert snapshot['ticket_usage'][0]['cost']['provider_reported_estimate_usd']==0.04,snapshot
    roles=[json.loads(p.read_text()) for p in (project/'.nightshift/agents').glob('dispatch-*.json')]
    assert any(r.get('usage_observations') for r in roles),roles
    print('PASS: factory + roles -> persistent ticket totals -> dashboard, including inherited attribution')
