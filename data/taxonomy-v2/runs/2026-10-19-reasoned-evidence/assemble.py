"""Serialize this session's explicit per-entry decisions. Not an inference runner."""
import csv,json,re,hashlib
from pathlib import Path
from datetime import datetime,timezone
RUN=Path(__file__).parent
F=RUN/'frozen'
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
vocab=json.load(open(F/'vocabulary.json'));schema=json.load(open(F/'output.schema.json'))
rows=list(csv.DictReader(open(F/'clasificare-input.csv')));concepts={x['id']:x for x in vocab['concepts']}
roots={k for k,v in concepts.items() if v['schema']=='subiect' and not v['mai_larg']}
public={};retrieval=[]
for p in sorted((RUN/'evidence').glob('web-*.json')):
 raw=json.load(open(p))
 for block in raw.split('--------------------------------------------------------------------------------'):
  m=re.search(r'cite([^]+)',block)
  if not m:continue
  ref=m[1]; url=re.search(r'"ref_id":"(https?[^"\s]+)"',block)
  if not url:url=re.search(r'\((https?[^\s)]+)\)',block)
  if not url:continue
  url=url[1];failed='Internal Error ()' in block;empty='Total lines: 0' in block
  retrieval.append(dict(source_id=ref,url=url,status='failed' if failed else 'empty' if empty else 'text',raw_file=str(p.relative_to(RUN)),retrieved_at=datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat()))
  if failed or empty:continue
  lines=re.findall(r'(?:^|\n)L(\d+): ([^\n]*)',block)
  text='\n'.join('L'+n+': '+t for n,t in lines) if lines else block.strip()
  public[ref]=dict(id=ref,kind='public_page' if lines else 'search_excerpt',url=url,retrieved_at=retrieval[-1]['retrieved_at'],locator=url+'#'+ref,text=text,source_identity=block.strip().split('\n')[0],raw_file=str(p.relative_to(RUN)),identity_checked='Selected by explicit entry URL, project name, or publisher statement; not by name similarity alone.')
dump(RUN/'evidence/retrieval-ledger.json',retrieval)
# Explicit evidence selection, made before evaluation. Never reuse another candidate as evidence.
refs={1:['turn4search0','turn4search2'],10:['turn3view7'],18:['turn0view2'],19:['turn7search12','turn7search1'],20:['turn0view4'],22:['turn0view5'],23:['turn0view6'],25:['turn2view2'],31:['turn2view1'],34:['turn6view2'],44:['turn3view7'],54:['turn7search0'],57:['turn6search2'],61:['turn4search5'],62:['turn5search3'],64:['turn3view2'],67:['turn1view2'],68:['turn3view7'],71:['turn3view7'],77:['turn3view4'],78:['turn2view6'],85:['turn1view6'],89:['turn3view7'],92:['turn1view5'],95:['turn6view1'],96:['turn6view0'],98:['turn1view7'],105:['turn3view8']}
# Restrict each public citation to an entry-specific passage. Raw captures remain separately auditable.
needles={1:'un instrument util pentru educația alegătorilor',10:'banipierduti.ro',18:'Centrul pentru Cariere oferă informații accesibile',19:'explică legislația în termeni simpli',20:'Un mediu inovator de învățare',22:'O societate sau regie autonomă',23:'Secțiunea cu baze de date conține',25:'Poți începe o petiție',34:'identifică un loc sigur',44:'hartapoliticii.ro',54:'Ne ocupăm doar cu cei condamnați definitiv',57:'O imagine în timp real a sistemului',61:'Multumesc.org este un proiect non-profit',62:'Muzeul Corupţiei găzduieşte Galeria Şpăgilor',64:'Manualul observatorului',67:'Topul instanțelor din România',68:'openbudget.ro',71:'raportează anonim',77:'Ești salariat în România?',78:'Alegeri parlamentare',85:'În paginile acestui site vei găsi',89:'am descoperit o listă bogată',92:'Platformă independentă (neoficială)',95:'Vot Corect oferă informații',96:'cea mai apropiată secție de votare',98:'Demontăm afirmațiile politice false',105:'urmărim două direcții complementare'}
# Status reflects material evidence gaps, not editorial acceptance.
partial={14,19,24,26,31,44,45,51,53,55,61,64,70,87,90,103,108}
# Strong editorial geographic statements are preserved as source claims, not independently verified coverage.
geo={3:('local',['localitate:bucuresti','judet:ilfov']),35:('international',['regiune:UE']),61:('national',['tara:RO']),63:('local',['localitate:bucuresti']),96:('international',[]),106:('international',[]),107:('international',[]),112:('international',['tara:RO'])}
extra_roots={8:['guvernare-democratie','media-informare'],9:['finante-publice'],23:['guvernare-democratie','sanatate','media-informare'],93:['sanatate'],109:['finante-publice','drept-justitie','sanatate'],110:['drept-justitie']}
entity_overrides={89:'publicatie',106:'publicatie'}
# Optional stages apply only to functional services with concrete descriptions of ordinary use.
# Explicit prototype and unresolved contradictory source claims are handled separately.
def local(r,key):return dict(id=r['slug']+':'+key,kind='curated_csv',url=None,retrieved_at=None,locator='clasificare-input.csv:'+r['slug']+':'+key,text=r[key])
def cite(s,excerpt=None):return dict(source_id=s['id'],locator=s['locator'],excerpt=excerpt or s['text'])
def paragraph(s,needle):
 lines=s['text'].splitlines()
 found=next((x for x in lines if needle in x),None)
 if not found:found=next((x for x in lines if len(x)>60 and not x.startswith(('cite','Source:'))),s['text'][:300])
 return found
field_schemes={'subiect_principal':'subiect','subiecte':'subiect','teme':'subiect','scopuri':'scop','functionalitati':'functie','formate':'format','tehnologii':'tehnologie','institutii_vizate':'institutie','tip_organizatie':'organizatie','maturitate':'maturitate'}
def ids(s,scheme):return [scheme+':'+x.strip() for x in s.split(',') if x.strip()]
def ancestors(cid):
 ps=[x for x in concepts[cid]['mai_larg'].split('|') if x]
 return {cid} if cid in roots else set().union(*(ancestors(p) for p in ps))
def uncertainty(field,reason,needed):return dict(field=field,reason_ro=reason,needed_evidence_ro=needed)
results=[];decisions=[]
for line in (RUN/'decisions.tsv').read_text().splitlines():
 if not line or line.startswith('#'):continue
 a=[x.strip() for x in line.split('|')]
 assert len(a)==11,(a[0],len(a))
 i=int(a[0]);r=rows[i];slug=r['slug'];decisions.append(i)
 c=dict(tip_entitate=entity_overrides.get(i,r['tip_entitate_original']),subiect_principal='subiect:'+a[1] if a[1] else None,subiecte=[],teme=ids(a[2],'subiect'),scopuri=ids(a[3],'scop'),functionalitati=ids(a[4],'functie'),formate=ids(a[5],'format'),tehnologii=ids(a[6],'tehnologie'),institutii_vizate=ids(a[7],'institutie'),tip_organizatie=ids(a[8],'organizatie'),maturitate=('maturitate:'+a[9]) if a[9] else None,nivel_acoperire=r['acoperire_original'] or 'necunoscut',arii_acoperite=[])
 if c['subiect_principal']:
  c['subiecte']=[c['subiect_principal']]
  for t in c['teme']:
   for root in sorted(ancestors(t)):
    if root not in c['subiecte']:c['subiecte'].append(root)
  for root in extra_roots.get(i,[]):
   if 'subiect:'+root not in c['subiecte']:c['subiecte'].append('subiect:'+root)
 sources=[local(r,k) for k in r if r[k]]
 ps=[public[x] for x in refs.get(i,[]) if x in public];sources+=ps
 if i in geo:c['nivel_acoperire'],c['arii_acoperite']=geo[i]
 elif c['nivel_acoperire']=='national':c['arii_acoperite']=['tara:RO']
 elif c['nivel_acoperire']=='local':
  c['arii_acoperite']=[x['id'] for x in vocab['areas'] if x['eticheta_ro']==r['oras_original']]
 if i==51:c['nivel_acoperire']='necunoscut';c['arii_acoperite']=[]
 # The request preserves the full original record; no unrelated local observations or withheld fields are read.
 attr=[]
 if r['autor_original']:
  for literal in re.split(r' / | & ',r['autor_original']):
   exact=next((e['slug'] for e in vocab['known_entities'] if literal in (e['slug'],e['name'])),None)
   attr.append(dict(source_id=slug+':autor_original',locator='clasificare-input.csv:'+slug+':autor_original',literal=literal,resolved_slug=exact))
 request=dict(schema_version='taxonomy-v2-classification/1',source_mode='retrieved_evidence',target_schema_version='2.0.0-draft.2',entry=dict(r,original_entity_type=r['tip_entitate_original'],original_url_section=r['sectiune_url_original'],original_attributions=attr),vocabulary=vocab,sources=sources,output_schema=schema)
 dump(RUN/'requests'/f'{slug}.json',request)
 base=[local(r,k) for k in ['descriere_scurta','descriere'] if r[k]]
 if not base and not ps:base=[local(r,k) for k in ['nume','domeniu_original','tip_original','cuvinte_original'] if r[k]]
 evidence=[cite(s) for s in base]
 # Do not cite an unrelated redirect as positive evidence about the original resource.
 if i!=31:
  evidence += [cite(s,paragraph(s,needles.get(i,''))) for s in ps[:1]]
 just=[]
 for field,value in c.items():
  values=value if isinstance(value,list) else [value]
  for val in values:
   if val is None or (field=='nivel_acoperire' and val=='necunoscut'):continue
   ev=evidence;basis='inference';conf='medie';why=a[10]
   if field=='tip_entitate':
    if i in entity_overrides:basis='inference';why='Intrarea este un material editorial individual, conform descrierii și paginii selectate.'
    else:ev=[cite(local(r,'tip_entitate_original'))];basis='identity_preservation';conf='mare';why='Păstrez tipul entității din înregistrarea originală; acesta nu dovedește funcționalități.'
   elif field in ['subiect_principal','subiecte']:
    selected=next((t for t in c['teme'] if val in ancestors(t)),None)
    if selected and selected!=val:basis='hierarchy';why=a[10]+' Conceptul '+selected+' are acest strămoș în vocabularul înghețat.'
   elif field in ['nivel_acoperire','arii_acoperite']:
    if i in geo:
     ev=evidence;why='Aplicabilitatea rezultă din descrierea specifică intrării, nu din adresa editorului. '+a[10]
    else:
     ev=[cite(local(r,'acoperire_original'))]
     if field=='arii_acoperite' and r['oras_original']:ev.append(cite(local(r,'oras_original')))
     why='Păstrez declarația geografică originală; nu confirm existența datelor pentru fiecare localitate.'
   elif field=='maturitate':
    basis='explicit' if val=='maturitate:prototip' else 'inference'
    why='Descrierea declară un prototip demonstrativ.' if val.endswith('prototip') else 'Descrierea oferă un flux concret pentru utilizare obișnuită de către publicul țintă. '+a[10]
   elif field=='tehnologii':basis='explicit';conf='mare';why=a[10]
   if i in {14,24,44,45,53,70,87} and field not in {'tip_entitate','nivel_acoperire','arii_acoperite'}:conf='mica'
   if field in field_schemes and field not in ['subiect_principal','subiecte']:
    why+=' Încadrare: '+concepts[val]['eticheta_ro']+'.'
   just.append(dict(field=field,value=val,basis=basis,confidence=conf,evidence=ev,rationale_ro=why))
 uncertainties=[]
 if c['maturitate'] is None and c['tip_entitate']=='proiect':uncertainties.append(uncertainty('maturitate','Dovezile nu stabilesc fără ambiguitate o etapă de utilizare actuală.','Declarație explicită sau documentare a utilizării în condiții reale.'))
 if not r['descriere'] and not ps:uncertainties.append(uncertainty('classification','Lipsește descrierea detaliată; titlul, textul scurt și etichetele au precizie limitată.','Documentație publică specifică intrării.'))
 if i in partial:uncertainties.append(uncertainty('classification',a[10],'Documentație primară care rezolvă ambiguitatea indicată.'))
 ats=[]
 for at in attr:
  ats.append(dict(predicate='atribuit_in_sursa',object_slug=at['resolved_slug'],object_literal=None if at['resolved_slug'] else at['literal'],basis='identity_preservation',confidence='mare',evidence=[cite(local(r,'autor_original'))],rationale_ro='Păstrez atribuirea originală; câmpul autor nu stabilește separat creatorul, editorul sau administratorul.'))
 if ats:uncertainties.append(uncertainty('attributions','Rolurile rămân nespecificate în câmpul original autor.','Declarație explicită despre rolul fiecărei persoane sau organizații.'))
 excluded=[]
 # Account for every legacy type/tag without treating them as authoritative assignments.
 for field,key in [('tip','tip_original'),('cuvinte','cuvinte_original')]:
  for token in [t.strip() for t in r[key].split(',') if t.strip()]:
   allids=[v for values in c.values() for v in (values if isinstance(values,list) else [values]) if isinstance(v,str)]
   matching=any(token.casefold() in [concepts[x]['eticheta_ro'].casefold(),x.split(':')[-1],*concepts[x]['alternative_ro'].casefold().split('|')] for x in allids if x in concepts)
   if not matching:excluded.append(dict(original_field=field,original_value=token,reason_ro=('Eticheta nu dovedește tehnologia folosită sau oferită.' if token in ['ai','mcp','aplicație-mobilă'] else 'Etichetă istorică mixtă sau nesusținută suficient; folosesc sensul concret al descrierii și fațetele independente.')))
 conflicts=[]
 if i==31:
  conflicts.append(dict(field='tip_entitate',source_ids=[slug+':descriere_scurta','turn2view1'],reason_ro='Sursa editorială descrie un ghid; URL-ul redirecționează către pagina generală APADOR-CH.',resolution_ro='Păstrez identitatea ghidului și nu îi atribui toate activitățile organizației.'))
 if i==26:
  conflicts.append(dict(field='maturitate',source_ids=[slug+':cuvinte_original',slug+':descriere'],reason_ro='Eticheta originală spune prototip; descrierea oferă utilizare gratuită fără cont, fără etapă explicită.',resolution_ro='Las maturitatea necunoscută până la clarificarea documentară.'))
 if i in [35,63,96,106,107,112]:
  geosource=next((s['id'] for s in base),ps[0]['id'] if ps else slug+':nume')
  conflicts.append(dict(field='nivel_acoperire',source_ids=[slug+':acoperire_original',geosource],reason_ro='Eticheta geografică originală nu descrie precis aplicabilitatea documentată.',resolution_ro='Propun nivelul și ariile susținute de descriere; nu modific sursa originală.'))
 result=dict(schema_version='taxonomy-v2-classification/1',slug=slug,result_status='insufficient_evidence' if not c['subiect_principal'] else 'partial' if i in partial else 'classified',classification=c,justifications=just,attributions=ats,uncertainties=uncertainties,conflicts=conflicts,excluded_legacy_tags=excluded,new_concept_proposals=[],new_area_proposals=[])
 results.append(result)
assert sorted(decisions)==list(range(122))
# Proposals are separate from the frozen IDs and never enter classification fields.
gaps={
 3:('tehnologie','Rețea de senzori','Sensor network','Folosește senzori fizici pentru colectarea sistematică de măsurători.',[], 'Vocabularul nu exprimă măsurarea fizică prin senzori.'),
 14:('format','Calendar','Calendar','Prezintă evenimente sau operațiuni în funcție de data programată.',[], 'Programul de ridicare a deșeurilor nu este descris precis de formatele existente.'),
 33:('functie','Semnarea documentelor','Document signing','Permite aplicarea unei semnături pe un document.',[], 'Generarea documentelor nu exprimă separat etapa de semnare.'),
 47:('functie','Indexarea documentelor','Document indexing','Indexează colecții de documente pentru recuperarea informației.',[], 'Căutarea nu descrie pregătirea și indexarea colecțiilor.'),
 56:('institutie','Autoritate pentru cetățenie','Citizenship authority','Instituție care gestionează cererile și procedurile privind cetățenia.',[], 'Nu există o categorie pentru instituția vizată de statisticile de cetățenie.'),
 86:('functie','Simularea scenariilor','Scenario simulation','Calculează rezultatele unor ipoteze sau combinații introduse de utilizator.',[], 'Simulatorul de coaliții depășește compararea sau analiza descriptivă.'),
 108:('subiect','Informații geografice','Geographic information','Colectarea, prelucrarea și utilizarea informațiilor cu referință geografică.',['subiect:tehnologia-informatiei'], 'GIS este mai precis decât categoria tehnologiei informației.'),
 112:('subiect','Agricultură și dezvoltare rurală','Agriculture and rural development','Activități agricole și politici de dezvoltare a comunităților rurale.',[], 'Cercetarea CRPE include agricultura; vocabularul nu are un concept suficient de precis.')}
for i,args in gaps.items():
 result=results[i];request=json.load(open(RUN/'requests'/f"{result['slug']}.json"));r=rows[i]
 src=next(s for s in request['sources'] if s['id']==r['slug']+':'+('descriere' if r['descriere'] else 'nume'))
 scheme,ro,en,definition,broader,reason=args
 # Hoover's short description supports searching, not an undocumented indexing capability.
 if i==47:continue
 result['new_concept_proposals'].append(dict(scheme=scheme,label_ro=ro,label_en=en,definition_ro=definition,broader_existing_ids=broader,reason_ro=reason,evidence=[cite(src)]))
for i,label,typ,parent in [(96,'Țările cu secții de votare pentru diaspora','regiune',[]),(106,'Europa de Est','regiune',['regiune:Europa']),(112,'Republica Moldova','tara',[])]:
 if i==96:
  results[i]['uncertainties'].append(uncertainty('arii_acoperite','Lista țărilor cu secții de votare nu este furnizată în dovezile extrase.','Lista explicită a secțiilor și a țărilor pentru scrutinul relevant.'));continue
 request=json.load(open(RUN/'requests'/f"{results[i]['slug']}.json"));src=next(s for s in request['sources'] if s['id']==rows[i]['slug']+':descriere')
 results[i]['new_area_proposals'].append(dict(label_ro=label,area_type=typ,parent_existing_ids=parent,reason_ro='Aria este menționată explicit, dar nu are un identificator în lista înghețată.',evidence=[cite(src)]))
for x in results:dump(RUN/'responses'/f"{x['slug']}.json",x)
(RUN/'results.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in results))
(RUN/'errors.jsonl').write_text('')
# Candidate rows retain every consolidated source field verbatim; no import into production is attempted.
headers=list(rows[0])+list(results[0]['classification'])+['clasificare_stare','result_status','response_file']
with open(RUN/'candidate/intrari-candidate.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=headers);w.writeheader()
 for r,x in zip(rows,results):w.writerow(dict(r,**{k:'|'.join(v) if isinstance(v,list) else v for k,v in x['classification'].items()},clasificare_stare='propus',result_status=x['result_status'],response_file='responses/'+r['slug']+'.json'))
dump(RUN/'candidate/catalogue-candidate.json',dict(schema_version='taxonomy-v2-classification/1',editorial_state='propus',entries=[dict(original=r,result=x) for r,x in zip(rows,results)]))
queue=[dict(slug=x['slug'],result_status=x['result_status'],uncertainties=x['uncertainties'],conflicts=x['conflicts']) for x in results if x['result_status']!='classified' or x['conflicts']]
dump(RUN/'candidate/review-queue.json',queue)
dump(RUN/'candidate/vocabulary-gaps.json',[dict(slug=x['slug'],concepts=x['new_concept_proposals'],areas=x['new_area_proposals']) for x in results if x['new_concept_proposals'] or x['new_area_proposals']])
print('Serialized',len(results),'responses;',len(queue),'review records;',len(public),'retrieved text sources;',len(retrieval),'retrieval records')
