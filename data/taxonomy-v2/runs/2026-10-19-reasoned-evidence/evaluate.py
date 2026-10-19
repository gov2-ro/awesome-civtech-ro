"""Evaluate the sealed candidate; never rewrite classification output."""
import json,csv,hashlib
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter,defaultdict
RUN=Path(__file__).parent;BASE=RUN.parent.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def csvout(p,rows,headers=None):
 with open(p,'w') as f:
  w=csv.DictWriter(f,fieldnames=headers or list(rows[0]));w.writeheader();w.writerows(rows)
seal=json.load(open(RUN/'classification-seal.json'))
assert all(sha(RUN/p)==h for p,h in seal['files'].items()),'Classification changed after seal'
evaluation_started_at=datetime.now(timezone.utc).isoformat()
# First semantic reads of withheld files occur only after the classification seal.
manual=list(csv.DictReader(open(BASE/'intrari.csv')))
review=list(csv.DictReader(open(BASE/'revizuire.csv')))
initial=list(csv.DictReader(open(BASE/'atribuiri-initiale.csv')))
results=[json.loads(l) for l in (RUN/'results.jsonl').read_text().splitlines()]
by_slug={x['slug']:x for x in results};baseline={r['slug']:r for r in manual}
assert set(by_slug)==set(baseline)
listfields={'subiecte','teme','scopuri','functionalitati','formate','tehnologii','institutii_vizate','tip_organizatie','arii_acoperite'}
fields=list(results[0]['classification'])
comparisons=[];metrics=[]
for field in fields:
 agree=0;jaccards=[];ca_total=ba_total=intersection_total=0
 for x in results:
  c=x['classification'][field];b=baseline[x['slug']][field]
  if field in listfields:
   cset=set(c);bset=set(filter(None,b.split('|')));same=cset==bset
   relation='equal' if same else 'candidate_adds' if bset<cset else 'candidate_omits' if cset<bset else 'mixed_membership'
   inter=len(cset&bset);union=len(cset|bset);jaccards.append(inter/union if union else 1)
   ca_total+=len(cset);ba_total+=len(bset);intersection_total+=inter
   ctext='|'.join(sorted(cset));btext='|'.join(sorted(bset))
  else:
   cv=c or '';same=cv==b;relation='equal' if same else 'candidate_abstains' if not cv else 'different_scalar';ctext=cv;btext=b
  agree+=same
  if not same:comparisons.append(dict(slug=x['slug'],field=field,baseline=btext,candidate=ctext,comparison=relation,result_status=x['result_status']))
 metric=dict(field=field,entries=122,exact_agreement=agree,disagreements=122-agree,exact_agreement_rate=round(agree/122,4))
 if field in listfields:metric.update(mean_jaccard=round(sum(jaccards)/122,4),candidate_assignments=ca_total,baseline_assignments=ba_total,shared_assignments=intersection_total)
 metrics.append(metric)
csvout(RUN/'evaluation/field-disagreements.csv',comparisons)
dump(RUN/'evaluation/field-metrics.json',metrics)
primary=[]
for x in results:
 b=baseline[x['slug']]['subiect_principal'];c=x['classification'];cp=c['subiect_principal']
 if b==cp:continue
 category='abstention' if cp is None else 'primary_emphasis_existing_baseline_root_retained' if b in c['subiecte'] else 'different_root_requires_semantic_review'
 primary.append(dict(slug=x['slug'],baseline=b,candidate=cp or '',category=category,rationale=x['justifications'][1]['rationale_ro'] if len(x['justifications'])>1 else 'Abținere documentată.'))
csvout(RUN/'evaluation/primary-subject-disagreements.csv',primary)
# Relate existing review requests to frozen evidence and outcomes, without claiming editorial resolution.
review_out=[]
for r in review:
 x=by_slug[r['slug']];q=json.load(open(RUN/'requests'/f"{r['slug']}.json"));pub=[s for s in q['sources'] if s['kind'] in ['public_page','search_excerpt']]
 review_out.append(dict(review_id=r['id'],slug=r['slug'],field=r['camp'],baseline_reason=r['motiv'],candidate_status=x['result_status'],public_sources=len(pub),disposition='Evidence added; evaluate the affected claim' if pub else 'Conservative reassignment or uncertainty; no new public evidence',editorial_acceptance='none'))
csvout(RUN/'evaluation/withheld-review-comparison.csv',review_out)
ledger=[]
for r in initial:
 x=by_slug[r['slug']];v=x['classification'].get(r['camp']);vs=v if isinstance(v,list) else [v] if v else []
 ledger.append(dict(slug=r['slug'],field=r['camp'],baseline_concept=r['concept'],baseline_basis=r['baza'],retained=r['concept'] in vs))
csvout(RUN/'evaluation/initial-assignment-comparison.csv',ledger)
# Manual semantic inspection by this assistant, after sealing. This is not an independent human audit.
sample=[
('465','supported','Contactele parlamentarilor susțin registrul și reprezentarea; maturitatea rămâne necunoscută.'),
('7-ani-de-acasa','supported_with_historical_limit','EFOR confirmă educația electorală și procedurile de vot. Sursa este istorică; nu demonstrează operarea actuală.'),
('accesinfo','supported','Descrierea susține cereri și documente conform Legii 544. Nu confirmă aplicație mobilă sau achiziții publice.'),
('antibunk','supported','Descrierea privește dezinformarea. Eticheta mediu nu a devenit subiect; discuția despre AI nu a devenit tehnologie.'),
('centrul-pentru-cariere','supported','Pagina primară oferă fișe de job și planificarea carierei. Domeniul economie-muncă este justificat.'),
('ce-zice-legea','partial_supported','Sursele publice descriu explicarea legislației. Repozitoriul istoric propune urmărirea schimbărilor. Rezultatul rămâne parțial.'),
('data-expertforum','citation_and_scope_concern','Sursa completă include media și date despre Republica Moldova. Citatul ales nu probează separat rădăcina media. Acoperirea națională moștenită este incompletă.'),
('demoanaf','supported_uncertainty','Eticheta prototip și descrierea unui serviciu accesibil nu stabilesc etapa. Valoarea null evită o certitudine falsă.'),
('de-obste','supported','Descrierea declară explicit un prototip demonstrativ. Nu rezultă un pilot sau o utilizare obișnuită.'),
('drepturi-civile','supported_identity_preservation','Pagina actuală redirecționează la organizație. Ghidul își păstrează identitatea; conflictul este înregistrat.'),
('dupa-cutremur','supported','Descrierea leagă harta Bucureștiului de pregătirea seismică. Mediul nu este subiectul principal.'),
('europescope','supported','Instituțiile și voturile UE justifică aria UE. Exemplul nu stabilește aria întregii Europe.'),
('harta-firmelor','supported','Relațiile dintre companii justifică economia și achizițiile secundare. Grafurile nu sunt presupuse hărți geografice.'),
('jailando','weak_format_support','Descrierea susține condamnări, fără a restrânge infracțiunile la corupție. Formatul registru se bazează mai ales pe tipul istoric.'),
('incentru','supported_abstention','Numele și categoria civic nu stabilesc un subiect. Rezultatele despre blog nu au fost tratate drept aceeași identitate.'),
('monarh-ai','supported_abstention_on_technology','Monitorizarea automată este explicită. Descrierea nu precizează utilizarea AI în operare; tehnologia rămâne goală.'),
('monitorul-ai','supported','Arhiva și căutarea parlamentară sunt explicite. Numele .ai nu probează inteligență artificială.'),
('muzeul-coruptiei','supported_with_historical_limit','Relatarea lansării confirmă galeria și testul. Include exemple fictive; rezultatul nu le tratează ca dosare reale.'),
('observatori-votcorect','partial_supported','Manualul și formarea sunt vizibile. Panoul cu text implicit nu dovedește un serviciu operațional.'),
('ro-api-hub','supported','Catalogul documentează API-uri externe. Nu sunt atribuite API propriu, MCP sau AI pe baza indexului pentru agenți.'),
('aiparte-research','supported','Colecția oferă rapoarte despre educație și administrație. Legăturile către proiecte MCP nu schimbă tehnologia colecției.'),
('votdiaspora','supported_with_area_gap','Descrierea identifică harta secțiilor pentru românii aflați în străinătate. Țările exacte rămân necunoscute.'),
('piratii-digitali-ai-kremlinului','supported','Unitatea este o investigație individuală. Articolul privește date personale și dezinformare în Europa de Est.'),
('crpe','supported_with_area_gap','Descrierea confirmă activitate în Moldova și agricultură. Lipsesc conceptul agricol și identificatorul Moldovei.'),
('code4ro','conservative_organisation_type','Descrierea susține dezvoltarea societății civile. Tipul ONG nu este preluat automat din eticheta originală.'),
('presspay','purpose_boundary_concern','Finanțarea presei independente este explicită. Scopul sprijin-organizatii poate fi prea îngust: definiția numește organizații civice.'),
('proiecte-geo-spatial','supported_with_topic_gap','GIS susține tehnologia informației în sens larg. Colecția nu oferă automat hartă, API sau licență de date deschise.')]
csvout(RUN/'evaluation/semantic-sample.csv',[dict(slug=s,outcome=o,finding_ro=t) for s,o,t in sample])
validation=json.load(open(RUN/'validation.json'));retrieval=json.load(open(RUN/'evidence/retrieval-ledger.json'))
requests=[json.load(open(RUN/'requests'/f"{x['slug']}.json")) for x in results]
entry_pub=sum(any(s['kind'] in ['public_page','search_excerpt'] for s in q['sources']) for q in requests)
source_usage=Counter(s['id'] for q in requests for s in q['sources'] if s['kind'] in ['public_page','search_excerpt'])
existing=json.load(open(RUN/'existing-files.sha256.json'));changed=[p for p,h in existing.items() if not Path(p).exists() or sha(Path(p))!=h]
assert not changed,changed
assert all(sha(RUN/p)==h for p,h in seal['files'].items())
summary=dict(evaluation_started_at=evaluation_started_at,classification_sealed_at=seal['sealed_at'],candidate_seal_valid=True,withheld_files={n:dict(sha256=sha(BASE/n),rows=len(rs)) for n,rs in [('intrari.csv',manual),('revizuire.csv',review),('atribuiri-initiale.csv',initial)]},entry_coverage=122,validation=validation,field_metrics=metrics,primary_subject_disagreements=len(primary),primary_difference_categories=dict(Counter(r['category'] for r in primary)),field_disagreements=len(comparisons),retrieval=dict(records=len(retrieval),statuses=dict(Counter(r['status'] for r in retrieval)),entries_with_public_evidence=entry_pub,unique_public_sources_supplied=len(source_usage),used_sources=dict(source_usage)),initial_assignment_rows=len(initial),initial_assignments_retained=sum(x['retained'] for x in ledger),existing_review_items=len(review),semantic_sample=dict(entries=len(sample),outcomes=dict(Counter(o for _,o,_ in sample)),independent_human_review=False),existing_file_hashes_checked=len(existing),existing_files_changed=changed,limitations=['Exact backend model ID, per-entry token usage and sampling settings unavailable in this session.','Direct assistant classification with batch serialization; not an isolated API response per entry or an implemented inference runner.','No local_only control arm; retrieval benefit is not a causal measurement.','Mechanical citation validity does not prove semantic entailment.','Candidate is frozen before evaluation; identified semantic issues remain documented, not silently corrected.','Candidate preserves all consolidated input fields. It does not contain excluded contact, notes or availability overrides; later implementation must preserve those by source identity.'])
dump(RUN/'evaluation/summary.json',summary)
print(json.dumps({k:summary[k] for k in ['primary_subject_disagreements','primary_difference_categories','field_disagreements','retrieval','initial_assignment_rows','initial_assignments_retained','existing_file_hashes_checked','existing_files_changed']},ensure_ascii=False,indent=2))
print('FIELD METRICS')
for m in metrics:print(m['field'],m['exact_agreement'],m['disagreements'])
print('PRIMARY DIFFERENCES')
for r in primary:print(r['slug'],r['baseline'],'->',r['candidate'],r['category'])
