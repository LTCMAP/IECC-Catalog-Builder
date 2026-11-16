"""Rebuild content/policies from the Board Policy Manual PDFs (iecc.edu/policymanual).

Usage:  python tools/import_policies.py <folder with POLICY_*.pdf> [content/policies]
Expects POLICY_CONTENTS.pdf and POLICY_<100..800>_<CODE>.pdf (e.g. POLICY_500_STUDENT.pdf).
Writes policy-register.csv plus one <number>.md per policy. Review the printed anomalies.
"""
import pdfplumber, re, csv, json, pathlib, datetime, sys
PDF=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else 'pdf')
OUT=pathlib.Path(sys.argv[2] if len(sys.argv)>2 else 'content/policies')
TODAY=datetime.date.today().isoformat()
SECTIONS={'100':('BOARD','Board of Trustees','POLICY_100_BOARD_10-20-2026_0.pdf'),'200':('ADMIN','Administration','POLICY_200_ADMIN_5-19-2026_0.pdf'),
 '300':('BUSINESS','Business','POLICY_300_BUSINESS_10-21-2025%20Rev%201.pdf'),'400':('HR','Human Resources','POLICY_400_HR_8-18-2026.pdf'),
 '500':('STUDENT','Students','POLICY_500_STUDENT_5-19-2026.pdf'),'600':('COMREL','Community Relations','POLICY_600%20COMREL_9-16-2025%20Rev%201.pdf'),
 '700':('AUXSERV','Auxiliary Services','POLICY_700%20AUXSERV%2010-17-2023_Rev1.pdf'),'800':('INSTRUCTION','Instruction','POLICY_800_INSTRUCTION_5-19-2026.pdf')}
BASE='https://iecc.edu/sites/default/files/inline-files/'
D=r'\d{1,2}/\d{1,2}/\d{4}'
def mdy(s):
    try: return datetime.datetime.strptime(s,'%m/%d/%Y').date().isoformat()
    except: return ''
def long(s):
    try: return datetime.datetime.strptime(s.strip().replace('  ',' '),'%B %d, %Y').date().isoformat()
    except: return ''

# ---- 1. register from contents
reg={}
with pdfplumber.open(PDF/'POLICY_CONTENTS.pdf') as pdf:
    lines=[l for p in pdf.pages for l in (p.extract_text() or '').splitlines()]
pending=None
for l in lines:
    l=l.strip()
    m=re.match(rf'^(\d{{3}}\.\d+)\s+(.*?)\s+({D})(?:\s+({D}|N/A))?\s*$',l)
    if m:
        num,title,a,r=m.groups(); reg[num]=dict(number=num,title=title,adopted=mdy(a),last_revised=mdy(r) if r and r!='N/A' else '')
        continue
    # wrapped row: title+dates on one line, number alone next line (e.g. 200.5)
    m=re.match(rf'^(.*?)\s+({D})\s+({D})\s*$',l)
    if m: pending=m.groups(); continue
    m=re.match(r'^(\d{3}\.\d+)\s*$',l)
    if m and pending:
        reg[m.group(1)]=dict(number=m.group(1),title=pending[0],adopted=mdy(pending[1]),last_revised=mdy(pending[2])); pending=None
for r in reg.values():
    r['status']='deleted' if re.search(r'DELETED',r['title'],re.I) else 'active'
    r['title']=re.sub(r'\s*[–-]?\s*DELETED.*$','',r['title'],flags=re.I).strip() if r['status']=='deleted' else r['title']
    sec=r['number'].split('.')[0]; r['section']=SECTIONS.get(sec,('','?',''))[1]

# ---- 2. full text from section PDFs
HEAD=re.compile(r'^(?P<title>[A-Z].{2,150}?)\s*\((?P<num>\d{3}\.\d+)\)\s*$')
NUMONLY=re.compile(r'^\((?P<num>\d{3}\.\d+)\)\s*$')
STARTKEY=re.compile(r'(Date\s+)?Adopted|Effective date|Removed|Per Board action|Deleted|Revised',re.I)
texts={}; text_dates={}
for sec,(code,name,fn) in SECTIONS.items():
    path=PDF/f'POLICY_{sec}_{code}.pdf'
    with pdfplumber.open(path) as pdf:
        lines=[]
        for p in pdf.pages:
            for l in (p.extract_text() or '').splitlines():
                s=l.strip()
                if re.match(rf'^{re.escape(name.upper().split()[0])}\b.*[-–]\s*{sec}\s*$',s,re.I) or re.match(rf'^[A-Z ]+[-–]\s*{sec}\s*$',s): continue
                if re.match(r'^(Page \d+( of \d+)?|\d+)$',s): continue
                lines.append(s)
    cur=None
    for i,s in enumerate(lines):
        m=HEAD.match(s); title=None
        if m: title=m.group('title').strip(); num=m.group('num')
        else:
            m2=NUMONLY.match(s)
            if m2 and i>0: title=lines[i-1].strip(); num=m2.group('num')
        if title and any(STARTKEY.match(x) for x in lines[i+1:i+3]) and not title.lower().startswith(('student military policy (','related')):
            if cur and texts[cur]['lines'] and texts[cur]['lines'][-1]==title: texts[cur]['lines'].pop()
            cur=num
            if cur not in texts: texts[cur]={'title':title,'lines':[],'section_pdf':BASE+fn}
            continue
        if cur: texts[cur]['lines'].append(s)

def to_md(lines):
    meta={'adopted':'','revised':[]}; body=[]
    MON=r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}'
    header=True
    for s in lines:
        if header and re.match(r'^((Date\s+)?Adopted|Effective date|Revised|Reinstated|Removed|Deleted|Per Board action)',s,re.I):
            m=re.search(r'(?:Adopted|Effective date):\s*'+MON,s,re.I)
            if m: meta['adopted']=long(re.search(MON,m.group(0)).group(0))
            for m in re.finditer(r'(?:Revised|Reinstated)[^:]*:\s*('+MON+')',s,re.I):
                meta['revised'].append(long(m.group(1)))
            continue
        header=False
        body.append(s)
    paras=[]; buf=''
    for s in body:
        if not s: continue
        new=re.match(r'^([A-Z]\.|\d+\.|[a-z]\.|[ivx]+\.|•|\([a-z0-9]+\))\s',s) or (buf and buf.rstrip().endswith(('.',':',';')) and s[:1].isupper() and len(buf)<95)
        if new and buf: paras.append(buf); buf=s
        else: buf=(buf+' '+s).strip() if buf else s
    if buf: paras.append(buf)
    out=[]
    for p in paras:
        p=re.sub(r'^•\s*','- ',p)
        out.append(p)
    return meta,'\n\n'.join(out)

outdir=OUT; outdir.mkdir(parents=True,exist_ok=True)
rows=[]
for num in sorted(set(reg)|set(texts), key=lambda n:(int(n.split('.')[0]),int(n.split('.')[1]))):
    r=reg.get(num,{'number':num,'title':texts.get(num,{}).get('title',''),'adopted':'','last_revised':'','status':'active','section':SECTIONS.get(num.split('.')[0],('','?',''))[1]})
    t=texts.get(num)
    if t and (not r['title'] or re.match(r'^\d',r['title'])): r['title']=t['title']
    if re.search(r'Renumbered|Relocated|Moved to',r['title'],re.I): r['status']='moved'
    r['title']=re.sub(r'\s*\($','',r['title']).strip()
    r['in_contents']='yes' if num in reg else 'NO'
    r['in_section_pdf']='yes' if t else 'no'
    r['source_pdf']=t['section_pdf'] if t else BASE+SECTIONS.get(num.split('.')[0],('','',''))[2]
    r['text_revised']=''
    r['file']=''
    if t:
        meta,md=to_md(t['lines'])
        revs=[x for x in meta['revised'] if re.match(r'\d{4}-',x)]
        r['text_revised']=max(revs) if revs else ''
        fn=f"{num}.md"; r['file']=f'policies/{fn}'
        fm={'number':num,'title':t['title'],'section':r['section'],'adopted':meta['adopted'] or r.get('adopted',''),'revised':revs,'source':r['source_pdf'],'retrieved':TODAY}
        (outdir/fn).write_text('---\n'+'\n'.join(f'{k}: {json.dumps(v,ensure_ascii=False)}' for k,v in fm.items())+'\n---\n\n# '+t['title']+f' ({num})\n\n'+md+'\n',encoding='utf-8')
    rows.append(r)
cols=['number','title','section','status','adopted','last_revised','text_revised','in_contents','in_section_pdf','file','source_pdf']
with open(OUT/'policy-register.csv','w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore'); w.writeheader(); w.writerows(rows)
import collections
print(len(rows),'policies;',collections.Counter(r['status'] for r in rows), 'with text:',sum(1 for r in rows if r['file']))
print('not in contents:',[r['number'] for r in rows if r['in_contents']=='NO'])
print('active but no text:',[r['number'] for r in rows if r['status']=='active' and not r['file']][:40])
mism=[(r['number'],r['last_revised'],r['text_revised']) for r in rows if r['file'] and r['last_revised'] and r['text_revised'] and r['last_revised']!=r['text_revised']]
print('date mismatch contents vs text:',len(mism),mism[:20])
