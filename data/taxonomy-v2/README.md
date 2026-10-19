# Propunere de taxonomie v2

Pachetul curent este `2.0.0-draft.1`. Modelul aprobat pentru implementare este `2.0.0-draft.2`.
Actualizarea trebuie să adauge cele patru etape de maturitate, cardinalitatea și listele de coduri în CSV.
Începeți implementarea din [brief-ul de predare](../../docs/briefs/handoff-taxonomy-v2.md).
Promptul pentru experimentul automat este în [docs/prompts/taxonomy-v2-classifier.md](../../docs/prompts/taxonomy-v2-classifier.md).
Experimentul și evaluarea sunt în [runs/2026-10-19-reasoned-evidence/](runs/2026-10-19-reasoned-evidence/README.md).
Consultați raportul înainte de integrare. Păstrați rularea înghețată și aplicați corecțiile într-o copie separată.
Instrucțiunile de pregătire de mai jos descriu copia inițială draft.1; repetarea clasificării nu este o condiție pentru implementare.

Aceasta este o copie separată pentru revizuire. Site-ul și scripturile curente nu o citesc.
Datele originale din `data/` rămân neschimbate. Specificația pentru integrare este în
[docs/specs/taxonomy-v2.md](../../docs/specs/taxonomy-v2.md).
Consultați [diagramele complete ale vocabularului](../../docs/specs/taxonomy-v2-vocabulary.md)
și [diagrama modelului și implicațiile pentru interfață](../../docs/specs/taxonomy-v2.md#model-diagram).
Regenerați diagramele după modificarea conceptelor cu `python3 data/taxonomy-v2/export_mermaid.py`.

Copie inițială: **122 de intrări**, **125 de concepte**, **13 subiecte generale**,
**86 de atribuiri originale** și **66 de puncte de revizuit**.
Cele **22 de corespondențe EuroVoc** folosesc identificatori și etichete verificate la sursa oficială.
Echivalența semantică rămâne o propunere. Nicio intrare nu este acceptată automat.

## Începeți aici

Pentru experimentul automat, [clasificare-input.csv](clasificare-input.csv) reunește toate cele 122 de intrări originale.
Fișierul este derivat din `source/proiecte.csv` și `source/orgs.csv`, fără clasificările v2 propuse sau notele interne.
Etichetele originale rămân dovezi istorice slabe. Folosiți separat vocabularul și promptul pentru a defini clasificarea cerută.
Mai întâi actualizați modelul la draft.2, apoi înghețați vocabularul și rulați experimentul.
Evaluați datele rezultate înainte de integrarea în build și în interfață.

1. Deschideți `revizuire.csv`. Începeți cu prioritatea `mare`.
2. Modificați clasificarea în `intrari.csv`. Consultați etichetele și definițiile din `concepte.csv`.
3. Completați `decizie_editor` în `revizuire.csv`. Setați punctul la `acceptat`, `respins` sau `amanat`.
4. Setați `clasificare_stare=acceptat` în `intrari.csv` numai după verificarea întregii intrări.
5. Rulați verificarea de mai jos. Exportul actualizează numai `catalogue.json` din această copie.

```sh
python3 data/taxonomy-v2/validate.py --export
```

Comanda rulează din rădăcina proiectului. Nu accesează rețeaua și nu publică nimic.
Folosiți `--baseline` pentru a verifica păstrarea exactă a copiei inițiale:

```sh
python3 data/taxonomy-v2/validate.py --baseline --export
```

După modificări editoriale, verificarea normală este cea potrivită.
`--baseline` refuză modificările textelor originale, ale listei de intrări sau ale atribuirilor inițiale.
Un rezultat cu zero erori verifică structura. Nu confirmă corectitudinea clasificării.

## Ce fișier se editează

| Fișier | Rol | Se editează? |
| --- | --- | --- |
| `intrari.csv` | Toate proiectele, organizațiile și resursele, cu noile fațete | Da |
| `concepte.csv` | Identificatori, etichete române/engleze, definiții, ierarhie și termeni alternativi | Da |
| `relatii.csv` | Persoane și organizații atribuite în vechiul câmp `autor` | Da, cu dovada rolului |
| `arii.csv` | Zonele geografice folosite în clasificare | Da |
| `revizuire.csv` | Întrebări concrete și deciziile editorului | Da |
| `mapari-externe.csv` | Corespondențe propuse cu EuroVoc | Da, după verificarea sensului |
| `setari.json` | Secțiunile, rolurile linkurilor și adresele de raportare copiate | Da |
| `catalogue.json` | Export al tabelelor pentru consum programatic | Nu; rulați `validate.py --export` |
| `schema.json` | Contractul structurii: coloane, liste și valori admise | Numai când schimbați modelul |
| `corespondente-v1.csv` | Trecerea de la categorii și etichete vechi la concepte candidate | Istoric de migrare |
| `atribuiri-initiale.csv` | Dovada locală și raționamentul pentru clasificarea inițială | Istoric de migrare |
| `observatii/` | Copii de lucru ale profilurilor și mențiunilor; același format ca înainte | Numai prin viitoarele scripturi adaptate |
| `source/` | Copii exacte ale tuturor fișierelor CSV/JSON de la primul nivel din `data/` | Nu |
| `reference/` | Interogarea și răspunsul oficial EuroVoc, plus sursele metodologice | Nu modificați răspunsul sau interogarea |
| `manifest.json` | Numerele inițiale și hashurile copiilor originale | Nu |

`international.csv` este păstrat numai în `source/`. Nu a fost introdus în cele 122 de intrări.
Imaginile nu sunt duplicate. Căile din profiluri se referă la imaginile existente din `site/img/`.
Profilurile și mențiunile păstrează și înregistrările vechi fără o intrare activă în catalog.
Aceste înregistrări nu creează intrări noi.

## Convenții de editare

- Salvați CSV în UTF-8, cu virgulă drept separator de coloane. Păstrați antetul.
- Separați valorile multiple prin `|`, fără spații în jurul separatorului.
- Păstrați identificatorii fără diacritice. Etichetele afișate au diacritice.
- Folosiți identificatori, nu etichete, în coloanele de clasificare.
- O celulă goală înseamnă necunoscut sau neaplicabil. Nu scrieți `null` sau `n/a`.
- Nu modificați un identificator când corectați o etichetă. Actualizați toate referințele dacă retrageți un concept.
- Nu transformați automat fiecare etichetă veche într-o afirmație nouă.
- Nu transformați un termen mai îngust într-un sinonim al unuia mai larg.

Exemplu existent: `ce-cumpara-primaria` are `subiect:finante-publice` ca subiect principal,
`subiect:achizitii-publice` ca temă, `functie:cautare|functie:comparare` ca funcționalități,
`format:vizualizare` ca format și `institutie:primarie` ca instituție vizată.

## Sensul fațetelor

| Coloană | Întrebare | Exemplu |
| --- | --- | --- |
| `subiect_principal` | Unde apare prima dată în lista grupată? | `subiect:finante-publice` |
| `subiecte` | Ce domenii generale tratează? | `subiect:finante-publice|subiect:guvernare-democratie` |
| `teme` | Ce subiecte mai precise tratează? | `subiect:achizitii-publice` |
| `scopuri` | Ce scop civic sprijină? | `scop:transparenta` |
| `functionalitati` | Ce permite să faci? | `functie:comparare` |
| `formate` | În ce formă oferă conținutul sau instrumentul? | `format:harta` |
| `tehnologii` | Ce tehnologie folosește sau oferă explicit? | `tehnologie:ai` |
| `institutii_vizate` | Ce tip de instituție vizează? | `institutie:primarie` |
| `tip_organizatie` | Ce fel de organizație este? | `organizatie:think-tank` |
| `maturitate` | Este declarat un prototip? | `maturitate:prototip` |
| `nivel_acoperire` | Care este întinderea geografică? | `local` |
| `arii_acoperite` | Ce zone acoperă? | `localitate:bucuresti` |

Un proiect despre AI nu folosește obligatoriu AI. Un catalog de API-uri nu oferă obligatoriu un API propriu.
Un ghid despre corupție nu este o condamnare. Un oraș din adresa organizației nu limitează acoperirea sa.

`stare` păstrează intervenția manuală asupra stării site-ului. Nu descrie maturitatea sau verificarea clasificării.
`civictech_original` păstrează vechea valoare. Nu reprezintă o certificare nouă.
`sectiune_url` păstrează adresele actuale chiar dacă se schimbă `tip_entitate`.

## Limitele copiei

Clasificările folosesc textele și etichetele existente. Nu am reverificat site-urile individuale.
Încrederea este mică unde lipsesc descrierile și medie în celelalte cazuri.
Cele 66 de puncte sunt întrebări specifice, nu singurele intrări care necesită verificare.

`atribuiri-initiale.csv` păstrează clasificarea de la creare, nu starea curentă după editările dumneavoastră.
`corespondente-v1.csv` conține alternative și reguli de context. Nu este un tabel de înlocuiri automate.
Mapările EuroVoc au `stare_mapare=propus` și `relatie=closeMatch`.
Acceptați o mapare numai după compararea definițiilor. Folosiți `exactMatch` numai pentru sensuri echivalente.

Modelul este inspirat de SKOS. Fișierele CSV/JSON nu sunt un export RDF și nu declară conformitate ISO.
