"""Export publication figures from measured benchmark evidence only."""
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def main():
    source=ROOT/'outputs/benchmarks/validation-2026-10-07.json'
    report=json.loads(source.read_text(encoding='utf-8'))
    output=ROOT/'outputs/figures'
    output.mkdir(parents=True,exist_ok=True)
    records=[]
    summaries=report['summary']
    budgets=sorted({row['training_timesteps'] for row in report['rows'] if row.get('training_timesteps')})
    for metric,filename,title in [
        ('mean_compatibility','01-validation-compatibility','Validation compatibility'),
        ('load_variance','02-validation-load-variance','Load variance (experimental capacities)'),
        ('invalid_proposals','03-validation-invalid-proposals','Invalid proposals before repair')]:
        fig,ax=plt.subplots(figsize=(8,4))
        names=[row['algorithm'] + (' + repair' if row['metrics']['fallback_count']['mean'] > 0 else '') for row in summaries]
        means=[row['metrics'][metric]['mean'] for row in summaries]
        std=[row['metrics'][metric]['std'] for row in summaries]
        ax.bar(names,means,yerr=std,color=['#2459C4' if n=='Hungarian' else '#137D78' for n in names],capsize=4)
        ax.set_title(title)
        ax.set_ylabel(metric.replace('_',' '))
        ax.tick_params(axis='x',labelrotation=25)
        ax.text(0,-.35,f"Split={report['split']}; N={report['students']}; M={report['advisors']}; seeds={report['seeds']}",transform=ax.transAxes,fontsize=8)
        ax.text(0,-.44,f'RL budgets: {budgets} steps/seed; experimental quotas; mean +/- population SD',transform=ax.transAxes,fontsize=8)
        fig.tight_layout()
        path=output/(filename+'.png')
        fig.savefig(path,dpi=300,bbox_inches='tight')
        plt.close(fig)
        records.append({'file':path.name,'kind':'measured-benchmark','metric':metric})
    fig=plt.figure(figsize=(8,4))
    ax=fig.add_subplot(111,projection='3d')
    students=np.array([[0,0,0],[0,2,0],[0,4,0]])
    advisors=np.array([[4,1,0],[4,3,0]])
    ax.scatter(*students.T,c='#2459C4',s=100,label='Students')
    ax.scatter(*advisors.T,c='#137D78',s=150,marker='s',label='Advisors')
    for i,j in enumerate([0,1,0]):
        points=np.stack((students[i],advisors[j]))
        ax.plot(*points.T,c='#137D78')
    ax.set_title('Illustrative matching sample (not an RL result)')
    ax.legend()
    path=output/'04-sample-3d.png'
    fig.savefig(path,dpi=300,bbox_inches='tight');plt.close(fig)
    records.append({'file':path.name,'kind':'synthetic-educational-sample'})
    fig,ax=plt.subplots(figsize=(10,3))
    ax.axis('off')
    labels=['Curated data\n+ temporal split','Features\nTRAIN fit only','Training\n+ validation gates','FastAPI\n+ session auth','Dashboard\n+ 3D event replay']
    for i,label in enumerate(labels):
        x=.02+i*.2
        ax.text(x,.55,label,transform=ax.transAxes,bbox={'boxstyle':'round,pad=.6','facecolor':'#F3F6FA','edgecolor':'#2459C4'},fontsize=9,ha='left')
        if i<4: ax.annotate('',xy=(x+.19,.57),xytext=(x+.145,.57),xycoords='axes fraction',arrowprops={'arrowstyle':'->'})
    path=output/'05-system-architecture.png'
    fig.savefig(path,dpi=300,bbox_inches='tight');plt.close(fig)
    records.append({'file':path.name,'kind':'architecture-not-measured-performance'})
    for record in records:
        record['sha256']=hashlib.sha256((output/record['file']).read_bytes()).hexdigest()
    manifest={'source':str(source.relative_to(ROOT)).replace('\\','/'),
              'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
              'figures':records,'absent':['convergence curve: no full-budget per-step reward log']}
    (output/'figure-provenance.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'figures':len(records),'source':manifest['source']}))


if __name__=='__main__':main()
