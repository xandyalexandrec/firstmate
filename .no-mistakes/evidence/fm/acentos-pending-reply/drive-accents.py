import os, pathlib, subprocess, json, shutil
root=pathlib.Path.cwd()
evidence=pathlib.Path('/Users/alex/.no-mistakes/evidence/01M5G38E8XTPHS7HRXVRZSZGPY')
lab=root/'.accent-lab'
sock=root/'.accent-sock'
baseline=root/'bin/.accent-baseline.sh'
env={k:v for k,v in os.environ.items() if not k.startswith('FM_') and k not in ('TMUX','TMUX_PANE','TASKS_AXI_FILE','TASKS_AXI_BACKEND')}
env.update(FM_HOME=str(lab), TMUX=f'{sock},0,0', LC_ALL='en_US.UTF-8')
rows=[]
def run(args, **kw):
    p=subprocess.run(args,env=env,capture_output=True,timeout=45,**kw)
    if p.returncode: raise RuntimeError(f'{args[0:2]} exit {p.returncode}: {p.stderr.decode(errors="replace")}')
    return p.stdout
try:
    run(['bash','bin/fm-lab-home.sh','create',str(lab)])
    baseline.write_bytes(run(['git','show','83b70ef49e33eff529f574618415997c8ef67518:bin/fm-pending-reply-lib.sh']))
    before=run(['bash','-c','. "$1"; fm_pending_reply_summarize "$2"','_',str(baseline),'não faça a correção']).decode()
    assert before=='no faa a correo',before
    rows.append(dict(kind='baseline',input='não faça a correção',output=before))
    run(['tmux','-S',str(sock),'-f','/dev/null','new-session','-d','-s','fm-lab-accents','-n','fm-accent','-x','100','-y','30','cat'])
    (lab/'state/accent.meta').write_text(f'window=fm-lab-accents:fm-accent\nendpoint_task_id=accent\nworktree={lab}\nproject={lab}\nharness=echo\nkind=secondmate\nmode=secondmate\nyolo=off\nhome={lab}\nprojects=accent\n')
    cases=[
      ('portuguese','não faça a correção','não faça a correção'),
      ('controls',' \x01não\tfaça\r\na\x1b correção\x7f ','não faça  a correção'),
      ('exact-limit','ç'*120,'ç'*120),
      ('over-limit','ç'*121,'ç'*117+'...'),
      ('mixed-multibyte','a'*115+'ç界😀'+'não faça a correção','a'*115+'ç界...'),
      ('ascii','x'*121,'x'*117+'...'),
      ('prefix','FM_FROMFIRST_MARK corr=0123456789abcdef não faça a correção','não faça a correção'),
    ]
    # Obtain the real carrier from its product owner, without inventing marker bytes.
    marker=run(['bash','-c','. bin/fm-marker-lib.sh; printf %s "$FM_FROMFIRST_MARK"']).decode()
    cases[-1]=('prefix',marker+'corr=0123456789abcdef não faça a correção','não faça a correção')
    for loc in ['C','en_US.UTF-8','pt_BR.UTF-8']:
      env['LC_ALL']=loc
      for name,text,expected in cases:
        previous=set((lab/'state/pending-replies').glob('*')) if (lab/'state/pending-replies').exists() else set()
        p=subprocess.run(['bash','bin/fm-send.sh','accent',text],env=env,capture_output=True,timeout=45)
        if p.returncode: raise RuntimeError(f'{name}/{loc}: {p.returncode} {p.stderr.decode(errors="replace")}')
        new=set((lab/'state/pending-replies').glob('*'))-previous
        assert len(new)==1,(name,new)
        rec=new.pop()
        data=dict(line.split('=',1) for line in rec.read_text().splitlines() if '=' in line)
        actual=data['request_summary']
        assert actual==expected,(name,loc,actual,expected)
        assert data['delivered_epoch'] and data['phase']=='awaiting_report',data
        inbox=sorted((lab/'state/accent.inbox').glob('*.msg'))[-1]
        body=run(['bash','-c','. bin/fm-task-inbox-lib.sh; fm_task_inbox_body "$1"','_',str(inbox)]).decode()
        assert (expected if name=='prefix' else text) in body,(name,body)
        recovery=run(['bash','-c','. bin/fm-pending-reply-lib.sh; fm_pending_reply_recovery_message "$1"','_',str(rec)]).decode()
        assert 'Original request: '+expected in recovery,(name,recovery)
        rows.append(dict(scenario=name,locale=loc,input=text,request_summary=actual,characters=len(actual),phase=data['phase'],delivered_epoch=data['delivered_epoch'],inbox_body=body,recovery_message=recovery,stderr=p.stderr.decode()))
        (evidence/f'{name}-{loc}-record.txt').write_text(rec.read_text())
    (evidence/'terminal.txt').write_bytes(run(['tmux','-S',str(sock),'capture-pane','-p','-t','fm-lab-accents:fm-accent']))
finally:
    subprocess.run(['tmux','-S',str(sock),'kill-server'],capture_output=True)
    shutil.rmtree(lab,ignore_errors=True)
    baseline.unlink(missing_ok=True)
    sock.unlink(missing_ok=True)
    (evidence/'live-results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'cases':len(rows)-1,'baseline':before,'result':'pass'},ensure_ascii=False))
