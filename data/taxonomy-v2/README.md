# Propunere de taxonomie v2

Pachetul curent este `2.0.0-draft.2`. Are patru etape de maturitate, cel mult o etapă pe intrare,
și liste de coduri, roluri și gazde de linkuri în fișiere CSV. [versiuni.json](versiuni.json) descrie schimbările față de draft.1.
Promptul pentru experimentul automat este în [docs/prompts/taxonomy-v2-classifier.md](../../docs/prompts/taxonomy-v2-classifier.md).
Experimentul și evaluarea sunt în [runs/2026-10-19-reasoned-evidence/](runs/2026-10-19-reasoned-evidence/README.md). Rularea rămâne neschimbată.
Copia de integrare [integrare/](integrare/) preia clasificarea acelei rulări, cu cele trei corecții din evaluare.
Toate clasificările rămân propuneri. Site-ul public folosește în continuare datele din `data/`.

Aceasta este o copie separată pentru revizuire. Site-ul public nu o citește. Scripturile o citesc numai când primesc
`--data-dir` (vezi [Previzualizare](#previzualizare)).
Datele originale din `data/` rămân neschimbate. Specificația pentru integrare este în
[docs/specs/taxonomy-v2.md](../../docs/specs/taxonomy-v2.md).
Consultați [diagramele complete ale vocabularului](../../docs/specs/taxonomy-v2-vocabulary.md)
și [diagrama modelului și implicațiile pentru interfață](../../docs/specs/taxonomy-v2.md#model-diagram).
Regenerați diagramele după modificarea conceptelor cu `python3 data/taxonomy-v2/export_mermaid.py`.

Copie inițială (draft.1): **122 de intrări**, **125 de concepte**, **13 subiecte generale**,
**86 de atribuiri originale** și **66 de puncte de revizuit**.
Cele **22 de corespondențe EuroVoc** folosesc identificatori și etichete verificate la sursa oficială.
Echivalența semantică rămâne o propunere. Nicio intrare nu este acceptată automat.
Draft.2 are **128 de concepte**: s-au adăugat `maturitate:experiment`, `maturitate:pilot` și `maturitate:operational`.

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
| `valori.csv` | Listele de coduri: o valoare pe rând, cu etichete, definiție, statut și ordine | Da |
| `roluri-linkuri.csv` | Rolurile linkurilor (`github`, `donatii` …), cu etichete și ordine | Da |
| `gazde-linkuri.csv` | Gazda unui link și rolul ei, o gazdă pe rând | Da |
| `setari.json` | Adresele de raportare a unei probleme | Da |
| `catalogue.json` | Export al tabelelor pentru consum programatic | Nu; rulați `validate.py --export` |
| `schema.json` | Contractul structurii: coloane, chei, regulile câmpurilor și lista de coduri a fiecărui câmp | Numai când schimbați modelul |
| `versiuni.json` | Istoricul versiunilor pachetului | Numai la o versiune nouă |
| `integrare/` | Copia de integrare a rulării înghețate (vezi mai jos) | Numai `modificari.csv` și `reconciliere.csv`; restul se regenerează |
| `corespondente-v1.csv` | Trecerea de la categorii și etichete vechi la concepte candidate | Istoric de migrare |
| `atribuiri-initiale.csv` | Dovada locală și raționamentul pentru clasificarea inițială | Istoric de migrare |
| `observatii/` | Copii de lucru ale profilurilor și mențiunilor; același format ca înainte | Numai prin viitoarele scripturi adaptate |
| `source/` | Copii exacte ale tuturor fișierelor CSV/JSON de la primul nivel din `data/` | Nu |
| `reference/` | Interogarea și răspunsul oficial EuroVoc, plus sursele metodologice | Nu modificați răspunsul sau interogarea |
| `manifest.json` | Numerele inițiale draft.1 și hashurile copiilor originale | Nu |

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
| `maturitate` | În ce etapă este, după dovezi? Cel mult o valoare. | `maturitate:operational` |
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

## Liste de coduri

`valori.csv` are coloanele `lista,cod,eticheta_ro,eticheta_en,definitie_ro,statut,ordine`.
Perechea `(lista,cod)` este unică. `ordine` este un număr întreg, unic în listă.
`schema.json` leagă fiecare coloană de lista ei, de exemplu `stare` → `stare_manual`.
Un câmp opțional rămâne gol. Nu adăugați un rând cu cod gol.
Un cod cu `statut=retras` nu mai poate fi folosit.
Lista `revizuire_stare` are și codul `tehnic` (Închis tehnic): punctul nu cere decizie editorială.
Regula lui este în [Reconcilierea cozii de revizuire](#reconcilierea-cozii-de-revizuire).
Un rol nou din `roluri-linkuri.csv` are nevoie și de suport în cod pentru a apărea corect pe site.
`setari.json` nu mai conține secțiuni sau roluri. Validatorul respinge o a doua sursă pentru aceste liste.

## Copia de integrare

`integrare/` este o copie suprapusă peste acest pachet. `pachet.json` numește fișierele proprii.
Vocabularul, listele, ariile, relațiile, observațiile și copiile sursă vin din pachet.

| Fișier | Conținut |
| --- | --- |
| `intrari.csv` | Clasificarea rulării; textele, linkurile, contactele, `stare` și `nota` din `source/`, după `sursa_fisier` și `sursa_rand` |
| `modificari.csv` | Jurnalul corecțiilor făcute de om. Se adaugă rânduri; nu se rescriu cele existente |
| `rezultate.csv` | Rezultatul fiecărui răspuns (`classified`, `partial`, `insufficient_evidence`) și hashul lui |
| `revizuire.csv` | R001–R066 din pachet, reconciliate cu această copie; C pentru incertitudinile rulării, S pentru cele trei probleme semantice, V pentru propuneri |
| `reconciliere.csv` | Un rând pentru fiecare punct R, plus recomandarea pentru punctele C, S și V. Se editează; `integrare.py` îl aplică la `revizuire.csv` |
| `propuneri-vocabular.csv` | Concepte și arii propuse. Nu sunt în `concepte.csv` și nu sunt atribuite |

Intrarea `incentru` nu are subiect: rularea s-a abținut. Are `clasificare_stare=de-revizuit`.
Celelalte 121 de intrări au `propus`. Cele 16 rezultate parțiale rămân marcate în `rezultate.csv` și în `revizuire.csv`.

```sh
python3 data/taxonomy-v2/integrare.py           # verifică dacă integrare/ corespunde rulării și jurnalului
python3 data/taxonomy-v2/integrare.py --write   # regenerează integrare/ după o modificare în modificari.csv sau reconciliere.csv
python3 data/taxonomy-v2/validate.py --root data/taxonomy-v2/integrare --baseline --export
```

### Reconcilierea cozii de revizuire

Punctele R001–R066 din `revizuire.csv` de bază au fost scrise pentru propunerea manuală draft.1.
Valorile lor originale și propunerile lor pot să nu existe în această copie. Coada de bază rămâne neschimbată.
`integrare/reconciliere.csv` compară fiecare punct R cu `integrare/intrari.csv`.
`integrare.py` aplică fișierul când asamblează `integrare/revizuire.csv`. Nicio clasificare nu se schimbă prin reconciliere.

| Coloană | Sens |
| --- | --- |
| `id` | Punctul: R001, C001, S001 sau V001. Fiecare punct R are un rând |
| `rezultat` | `pastrat` (textul rămâne), `rescris` (câmpul, valoarea curentă, recomandarea și motivul se scriu din nou) sau `tehnic` (punctul se închide) |
| `camp` | Câmpul întrebării: o coloană din `intrari.csv`, `clasificare` sau `vocabular` |
| `valoare_originala` | Valoarea curentă din `integrare/intrari.csv` |
| `propunere` | Recomandarea pentru editor. Un punct deschis începe cu «Recomandare:» și numește o valoare sau o acțiune |
| `motiv` | De ce. `integrare.py` adaugă dovezile la sfârșitul lui, după «Dovadă:» |
| `dovada` | Dovezi separate prin `|`. Fiecare numește un fișier și un câmp care există |

Starea `tehnic` înseamnă că punctul nu cere decizie editorială. Se folosește numai în trei cazuri:

1. Premisa nu se aplică valorii curente din `integrare/intrari.csv`.
2. Punctul dublează exact un punct C sau S: aceeași intrare, același câmp, aceeași întrebare.
3. O corecție de cod sau de date a rezolvat punctul.

Un punct `tehnic` cere un `motiv` și nu are `decizie_editor`. Poarta de publicare numără numai punctele `deschis`.
Editorul decide în continuare fiecare punct deschis. O recomandare nu este o decizie.
Dacă nu există certitudine, punctul rămâne deschis.

O dovadă are una dintre formele:

- `fisier.csv:cheie:coloana`. Cheia este valoarea din prima coloană a fișierului.
  Exemple: `clasificare-input.csv:efor:oras_original`, `integrare/intrari.csv:crpe:arii_acoperite`, `concepte.csv:tehnologie:ai:definitie_ro`, `observatii/profil.csv:jailando:last_capture`.
  O celulă goală este dovada unei lipse, de exemplu a unei descrieri.
- `runs/<rulare>/responses/<slug>.json:cheie` sau `cheie[câmp=valoare]`. Cheia este una din cheile răspunsului sigilat, de exemplu
  `justifications`, `uncertainties`, `conflicts` sau `excluded_legacy_tags`.

`integrare.py` refuză o dovadă care nu există și un punct R fără rând. Fișierele din `runs/`, `source/` și `reference/` nu se modifică.

### Detașarea copiei

Înainte de revizuirea editorială, proprietarul rulează o singură dată:

```sh
python3 data/taxonomy-v2/integrare.py --detach   # apoi commit
```

Comanda scrie în `pachet.json` commitul și data detașării. După detașare, fișierele din `integrare/` se editează direct,
de mână sau prin fila `v2-intrari` a tabelului. `integrare.py` nu le mai regenerează. Verificarea dovedește doar că
`integrare/` de la commitul detașării corespunde rulării sigilate. Detașați înainte de orice modificare a vocabularului:
o modificare a vocabularului face rularea să nu mai corespundă, iar `--detach` refuză.

## Site-uri care interzic accesul automat

Dacă un site respinge cererile automate (de exemplu răspunde cu HTTP 429 sau cu o pagină de verificare) sau își interzice extragerea automată în termeni sau în `llms.txt`,
adăugați un rând în `data/taxonomy-v2/colectare-interzisa.csv`: `gazda` (numele gazdei, fără `https://` și fără `www.`; include și subdomeniile), `motiv` (o propoziție),
`dovada` (o adresă sau un citat scurt) și `data` (AAAA-LL-ZZ). După aceea niciun script nu mai cere gazda: nici `profile.py`, `review.py`, `collect_docs.py`, `inventory.py`, nici redirecționările către ea.
Intrarea își păstrează rândul din `profil.csv`; nu devine `offline`. Proprietarul salvează apoi paginile de mână, din browserul propriu,
și le importă cu `--import-saved` (`collect_docs.py` sau `inventory.py`). `validate.py` verifică fișierul și avertizează când nicio intrare nu mai folosește gazda. Coloanele: `docs/DATA-SCHEMA.md`.

## Previzualizare

```sh
python3 scripts/validate.py --data-dir data/taxonomy-v2/integrare
python3 scripts/build.py --data-dir data/taxonomy-v2/integrare --site-dir /tmp/civtech-v2 --allow-draft
python3 -m http.server -d /tmp/civtech-v2 8765
python3 scripts/test_taxonomy_v2.py
```

Construirea fără `--allow-draft` refuză clasificările neacceptate. `--site-dir` trebuie să fie în afara depozitului.
Previzualizarea nu modifică `site/`. Pagina afișează că clasificările sunt propuneri.

## Revizuirea în interfață

Pentru furnizorii de date (punctele D132 și următoarele din `integrare/revizuire.csv`) și pentru grupurile de variabile
(`inventar-concepte.json`) există o interfață locală. Ea scrie fișierele din depozit. Nu face commit și nu trimite nimic în rețea.

```sh
python3 scripts/review_ui.py          # apoi deschideți http://127.0.0.1:8790/
```

1. Antetul arată progresul (`Furnizori: 12 / 31 decise`, `Grupuri: 4 / 30 revizuite`) și starea validării. Filtrul implicit este `Deschise`.
2. Alegeți un element din listă. Selecția rămâne în adresă. Tastele `j` și `k` trec la elementul următor și la cel precedent.
3. Pentru un furnizor, citiți propunerea, dovada și elementele înrudite. Alegeți acțiunea (`Accept`, `Resping`, `Amân`, `Duplicat…`, `Resetează`) și citiți consecința.
   Scrieți nota (obligatorie) și salvați. `Accept` cere numele canonic al furnizorului și adresa dovezii; ambele sunt completate din propunere.
4. Starea dovezii: `verificat` înseamnă că amprenta textului păstrat și fragmentul se potrivesc. `schimbat` înseamnă că textul s-a schimbat de la fixarea dovezii.
   `indisponibil local` înseamnă că nu există o copie locală. `fără amprentă` înseamnă că elementul nu a înregistrat o amprentă; textul se citește, dar nu se poate verifica.
5. Pentru un grup, confirmați sau excludeți fiecare membru (excluderea cere notă). `Revizuit` rămâne dezactivat cât timp un membru este `propus`
   sau o deducție din dovezi nu este bifată. Pagina spune de ce. `Resping` și `Amân` cer o notă.
6. Fila `Verificări` rulează `validate.py --publication`, `inventory.py --check` și `inventory_report.py --check`.
   Ea arată furnizorii acceptați față de `HEAD`, fișierele modificate și comenzile următoare: `python3 scripts/inventory_report.py`, apoi `git add` și `git commit`.

O modificare a fișierelor pe disc după încărcarea paginii (editor, `sheets.py pull`, `git checkout`) oprește scrierea. Reîncărcați datele și repetați decizia.
Decizia rămâne în `git diff` până la commit. `Resetează` readuce elementul la valorile din `HEAD`.
