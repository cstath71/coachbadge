import sys, os; sys.path.insert(0,'scripts'); from fetch import fetch, to_text
os.makedirs('raw/text',exist_ok=True)
pre=sys.argv[2]
for i,u in enumerate(open(sys.argv[1]).read().split()):
    m=fetch(u); t=to_text(m) if m.get('body') else ''
    open(f'raw/text/{pre}{i:02d}.txt','w').write(u+'\n'+t)
    print(i, m['status'], m['error'], len(t), u[:90], flush=True)
