import csv, json, hashlib, shutil
from pathlib import Path
from datetime import datetime, timezone
RUN=Path(__file__).parent
ROOT=Path.cwd()
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
existing={str(p):sha(p) for base in ['data','docs','scripts','site'] for p in Path(base).rglob('*') if p.is_file() and RUN not in p.parents and '__pycache__' not in p.parts}
write(RUN/'existing-files.sha256.json',existing)
for src,name in [('data/taxonomy-v2/clasificare-input.csv','clasificare-input.csv'),('data/taxonomy-v2/arii.csv','arii.csv'),('docs/prompts/taxonomy-v2-classifier.md','prompt.md'),('docs/prompts/taxonomy-v2-classifier.schema.json','output.schema.json')]: shutil.copyfile(src,RUN/'frozen'/name)
cs=list(csv.DictReader(open('data/taxonomy-v2/concepte.csv')))
stages=[('experiment','Experiment','Experiment','Explorează o idee sau o abordare; utilizarea practică nu este stabilită.'),('prototip','Prototip','Prototype','Demonstrează funcționalitatea propusă.'),('pilot','Pilot','Pilot','Este utilizat într-o implementare limitată în condiții reale sau într-un test cu utilizatori reali.'),('operational','Operațional','Operational','Este oferit pentru utilizare obișnuită de către publicul său țintă.')]
cs=[r for r in cs if r['schema']!='maturitate']
for key,ro,en,definition in stages: cs.append(dict(zip(cs[0],['maturitate:'+key,'maturitate',ro,en,'',definition,'','','propus'])))
with open(RUN/'frozen/concepte.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=list(cs[0])); w.writeheader();w.writerows(cs)
schema=json.load(open(RUN/'frozen/output.schema.json'))
old=json.load(open('data/taxonomy-v2/schema.json'))
codes=dict(old['enums']); codes['predicat']=old['relation_predicates']
with open(RUN/'frozen/valori.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=['lista','cod','eticheta_ro','eticheta_en','definitie_ro','statut','ordine']);w.writeheader()
 for name,values in codes.items():
  for i,v in enumerate(values):
   if v: w.writerow(dict(lista=name,cod=v,eticheta_ro=v,eticheta_en=v,definitie_ro='Cod păstrat din contractul existent.',statut='propus',ordine=i))
rs=list(csv.DictReader(open(RUN/'frozen/clasificare-input.csv')))
known=[dict(slug=r['slug'],name=r['nume']) for r in rs]
vocab=dict(target_schema_version='2.0.0-draft.2',concepts=cs,areas=list(csv.DictReader(open(RUN/'frozen/arii.csv'))),code_lists=codes,known_entities=known,approved_identity_aliases=[])
write(RUN/'frozen/vocabulary.json',vocab)
manifest=dict(run_id=RUN.name,created_at=datetime.now(timezone.utc).isoformat(),source_mode='retrieved_evidence',target_schema_version='2.0.0-draft.2',entry_count=len(rs),classifier={'provider':'OpenAI','model':'GPT-6 (session identity; exact backend model ID unavailable)','execution':'Direct assistant reasoning; one persisted JSON response per entry. No external inference API or automated inference runner.','settings':'Session settings; temperature and seed unavailable','usage':'Per-entry token usage unavailable; no fabricated counts.'},withheld=['intrari.csv','revizuire.csv','atribuiri-initiale.csv'],frozen_files={str(p.relative_to(RUN)):sha(p) for p in (RUN/'frozen').iterdir()},preparation_notes=['Run-local vocabulary only. Replaced draft.1 prototype definition and added experiment, pilot, operational.','Code lists copied from existing structural contract. Labels are code mirrors, not reviewed translations.','No aliases approved; exact original names and slugs only.','Existing data hashed for final non-mutation audit; withheld contents not exposed.'])
write(RUN/'manifest.json',manifest)
print('Frozen:',len(cs),'concepts;',len(rs),'entries;',len(vocab['areas']),'areas')
