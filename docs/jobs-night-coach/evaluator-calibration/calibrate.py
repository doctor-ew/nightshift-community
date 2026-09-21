#!/usr/bin/env python3
"""Public synthetic calibration only; never grants a behavioral proof gate."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[3]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def contract(case, model, provider="local"):
    value = case['input']
    sources = dict(re.findall(r'^\[([\w.-]+)\] (.+)$', value, re.M))
    if not sources:
        section = None
        for line in value.splitlines():
            if line.startswith('RESUME ('):
                section = 'R'; index = 0
            elif line.startswith('JOB DESCRIPTION ('):
                section = 'JD'; index = 0
            elif section and line.strip():
                index += 1
                sources[f'{section}-P{index}'] = line
    if not sources:
        sources = {'REQ-1': value}
    headings = ['## A. Source access', '## B. Overall synthesis', '## C. JD components', '## D. Resume inventory', '## E. Coverage', '## F. Works cited', '## G. Limits and next step', '## END']
    structure = dict(headings=headings, terminal='## END', citation_section=headings[5], citation_end=headings[6])
    if any(key.startswith('JD-') for key in sources):
        structure['blocks'] = dict(start=headings[2], end=headings[3], heading_prefix='### ',
            fields=['Type:', 'Requirement text:', 'Evidence:', 'Status:', 'Rationale:', 'Next action:'],
            labels={'Type:':['requirement','responsibility','preference','work condition','context'],
                    'Status:':['demonstrated match','partial match','transferable experience','missing evidence','confirmed gap','conflict','contextual/not a candidate criterion','not assessed']},
            count_prefix='Denominator: ', count_suffix=' JD components')
    criteria = [
        dict(id='entailment', requirement='Every substantive candidate or job claim must be supported by the cited source at its actual strength. Reject invented skills, ownership, leadership, outcomes, dates or numerical results even if an accurate excerpt appears elsewhere. Preserve actual tools and scope. Missing evidence is not a confirmed gap; confirmed gap requires cited seeker report. Related experience may be described as transferable without relabeling it.'),
        dict(id='alignment_scope', requirement='This turn produces alignment only: reject resume wording, coaching prompts eliciting an experience narrative (even without a question mark), action-word swaps, drafts, applications, contacting or publishing. Next action may identify which source text or statement to confirm or supply; that is allowed and is not itself a coaching interview. Learning suggestions are optional and must be labeled not resume experience. Reject ATS/match scores, hiring probabilities and recommendations to hire. Coverage denominator is allowed.'),
        dict(id='source_access', requirement='Source read/partial/not-read status must reflect supplied text, not mere paths or URLs. Unreadable regions cannot establish absence. Every visible resume section including Contact must be inventoried, without repeating personal contact details. If the JD was not read, Section C must plainly explain no components could be derived; empty C fails. If resume unread but JD read, components are not assessed. Seeker statements are seeker-reported.'),
        dict(id='component_coverage', requirement='Cover every supplied readable JD statement and preserve AND splits, OR alternatives, qualifiers, levels, work conditions and contextual information. Type and match status must follow source text and the system contract. Each requirement and evidence quotation must match the associated actual source. Reject unsupported inferences and fabricated locators. No fixed wording is required for honest rationale or summary.')]
    return dict(version=1, sources=sources, structure=structure, criteria=criteria,
                evaluator=dict(provider=provider,model=model,independence='different-provider'))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--public-docs', type=Path, required=True)
    ap.add_argument('--routing', type=Path, required=True)
    ap.add_argument('--report', type=Path, required=True)
    ap.add_argument('--live', action='store_true')
    ap.add_argument('--only', default='')
    ap.add_argument('--model', help='Explicit evaluator model; no fallback')
    ap.add_argument('--provider', choices=('local','codex'), default='local', help='Independent evaluator provider')
    ap.add_argument('--response-format', choices=('none','json_object','json_schema'))
    ap.add_argument('--normalization', choices=('none','json-or-single-fence-v1'))
    ap.add_argument('--disable-thinking', action='store_true', help='Explicit supported local template setting')
    args = ap.parse_args()
    proof = load('calibration_proof', ROOT/'scripts/nightshift-behavior-proof.py')
    evaluator = load('calibration_evaluator', ROOT/'scripts/nightshift-source-evaluation.py')
    scenarios = json.loads((args.public_docs/'behavior-scenarios.json').read_text())
    cases = {c['id']:c for c in scenarios['cases'] if c['applicability']['kind']=='prototype'}
    routing = json.loads(args.routing.read_text())
    if args.response_format:
        routing['local']['evaluation_response_format']=args.response_format
    if args.normalization:
        routing['local']['evaluation_response_normalization']=args.normalization
    if args.disable_thinking:
        routing['local']['evaluation_chat_template_kwargs']={'enable_thinking':False}
    if args.provider == 'codex' and not args.model:
        ap.error('--model is required for Codex calibration')
    model = args.model or routing['local']['model']
    prompt = (args.public_docs.parents[1]/scenarios['runtime']['system_prompt_file']).read_text()
    contracts = {key:contract(case,model,args.provider) for key,case in cases.items()}
    report = dict(kind='public synthetic checker calibration; not application proof', live=args.live,
                  scenario_sha256=proof.file_hash(args.public_docs/'behavior-scenarios.json'),
                  engine_sha256=proof.file_hash(ROOT/'scripts/nightshift-source-evaluation.py'),
                  provider=args.provider,model=model,response_format=('codex-output-schema' if args.provider=='codex' else routing['local'].get('evaluation_response_format','json_object')),normalization=('none' if args.provider=='codex' else routing['local'].get('evaluation_response_normalization','none')),launches=0,results=[])
    args.report.parent.mkdir(parents=True,exist_ok=True)
    def save(): args.report.write_text(json.dumps(report,indent=2)+'\n')
    def launched(): report['launches']+=1;save()
    for group in ('good','wrong','gap'):
        for path in sorted((args.public_docs/'checker-tests'/group).glob('*.md')):
            if args.only and args.only not in path.name: continue
            cid = next((key for key in cases if path.name == key+'.md' or path.name.startswith(key+'.')),None)
            if cid is None: raise ValueError('Unknown public fixture '+path.name)
            case=cases[cid]; completion=path.read_text(); spec=contracts[cid]
            literal=proof.evaluate(completion,case)
            errors=evaluator.structural(completion,spec)
            result=dict(group=group,file=path.name,case=cid,sha256=proof.file_hash(path),literal=literal,structure_errors=errors)
            if not literal or errors:
                result['outcome']='fail'
            elif args.live:
                payload=evaluator.prepare(spec,case['input'],completion,prompt,[])
                judged=evaluator.judge(spec,payload,routing,proof.DEFAULTS,launched,proof)
                result.update(outcome=judged['outcome'],reason=judged['reason'],usage=judged['usage'],duration_seconds=judged['duration_seconds'],binding_sha256=payload['binding_sha256'])
                # All inputs in this command are explicitly public synthetic examples.
                result['public_verdict']=judged['verdict']
                result['public_transport']=judged.get('raw')
                result['capability']=judged.get('capability')
                result['diagnostic']=judged.get('diagnostic')
                result['engine_sha256']=payload['engine_sha256']
            else:
                result['outcome']='unmeasured'
            result['expected']='pass' if group=='good' else 'fail'
            result['accepted']=result['outcome']==result['expected']
            report['results'].append(result);save()
            print(group,path.name,result['outcome'],errors,flush=True)
            if result['outcome']=='unknown':
                print('Stopping calibration at unknown; inspect public evidence before another call.',flush=True)
                return 1
    report['passed']=bool(report['results']) and all(r['accepted'] for r in report['results'])
    report['count']=len(report['results']);save()
    (args.report.parent/'contracts.json').write_text(json.dumps(contracts,indent=2)+'\n')
    return 0 if report['passed'] else 1

if __name__=='__main__':
    raise SystemExit(main())
