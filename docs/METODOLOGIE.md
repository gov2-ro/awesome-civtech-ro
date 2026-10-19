# Metodologie: starea, datele și scorul

Această pagină explică cum calculează site-ul starea, datele și scorul unei intrări.
Textul descrie codul din `scripts/profile.py`, `scripts/search.py`, `scripts/review.py` și `scripts/build.py`
la 2026-10-19. Dacă se schimbă codul, se schimbă și acest text.

Aproape toate valorile sunt **semnale automate**. Ele nu sunt verdicte. Un semnal poate fi greșit, vechi sau incomplet.
Dacă vezi o valoare greșită, folosește „Semnalează o problemă” din fișa intrării.

## De unde vin datele

| Pas | Script | Ce face | Cum rulează |
| --- | --- | --- | --- |
| Verificarea site-urilor | `profile.py` | Cere adresa fiecărei intrări și citește pagina principală. Apoi adaugă semnalele de vârstă și activitate: arhiva web, depozitul de cod, feed-ul, sitemap-ul, certificatul. `--extra` reia doar acești pași. | La cererea unui editor, nu continuu. |
| Căutarea mențiunilor | `search.py` | Caută numele și adresa intrării cu Serper (Google) și Brave. | La cererea unui editor. |
| Etichetarea mențiunilor | `review.py` | Un model de limbaj etichetează rezultatele păstrate, cel mult 40 pe intrare. | La cererea unui editor. |
| Construirea site-ului | `build.py` | Combină tabelele editate de om cu rezultatele de mai sus. Calculează starea, datele și scorul. | La fiecare publicare. |

Fără `--force`, `profile.py` nu verifică din nou o intrare deja verificată, dacă adresa ei nu s-a schimbat.
Data ultimei verificări apare în fișa intrării (rândul „Stare”). Starea poate fi deci mai veche decât starea reală a site-ului.

## 1. Starea

Site-ul arată una dintre cinci stări.

| Stare | Ce a văzut verificarea | Ce nu înseamnă |
| --- | --- | --- |
| **Activ** | Adresa a răspuns cu un cod HTTP sub 400. Pagina nu are text de domeniu parcat. Dacă adresa duce pe alt domeniu, intrarea rămâne Activ, cu noua adresă. | Nu înseamnă că serviciul funcționează, că datele sunt la zi sau că proiectul are echipă. |
| **Neconfirmat** | Site-ul a blocat verificarea (HTTP 401, 403, 429 sau 503) sau n-a răspuns la timp. O a doua verificare, cu un browser, n-a lămurit situația sau n-a rulat. | Nu înseamnă că site-ul e căzut. |
| **Offline** | Adresa a dat o eroare (HTTP 400 sau mai mare, fără cele de mai sus) sau n-a putut fi deschisă. Sau pagina arată text de domeniu parcat. Sau o subpagină trimite acum la prima pagină a gazdei. | Nu înseamnă că proiectul s-a încheiat. Poate fi o defecțiune trecătoare. |
| **Arhivat** | Un editor a scris `arhivat` în coloana `stare`. Sau verificarea a găsit „offline”, iar arhiva web n-a mai captat adresa de peste un an. | `build.py` tratează proiectul ca încheiat. Semnalul vine din absența capturilor, nu dintr-o dovadă. |
| **Neverificat** | Intrarea n-are rând de profil: nu a fost verificată sau nu are adresă. | Nu spune nimic despre site. |

### Ce înseamnă „Activ”

`classify()` din `profile.py` decide starea. Ea folosește doar codul HTTP, tipul erorii de rețea, o listă scurtă de fraze
de domeniu parcat și adresa finală după redirecționări. Ea nu citește conținutul paginii dincolo de aceste fraze.

Un site poate răspunde „200” și totuși să fie gol, abandonat sau să arate o altă pagină.
Un site care se mută pe alt domeniu apare tot „Activ”. Fișa arată atunci „mutat de pe” și noua adresă.

### Reguli de decizie

1. Dacă coloana `stare` are o valoare (`arhivat` sau `offline`), `build.py` o folosește fără alte verificări.
   Pentru o astfel de intrare, `build.py` ignoră ce găsește profilerul la adresa veche.
2. Altfel, `build.py` folosește starea profilerului: `activ` → Activ, `mutat` → Activ, `blocat` → Neconfirmat,
   `parcat` → Offline, `offline` → Offline.
3. Dacă starea profilerului e `offline` și ultima captură din arhiva web e mai veche de un an, rezultatul este Arhivat.
   Fără data ultimei capturi, acest pas nu are efect.
4. Fără rând de profil, starea este Neverificat.

Un site blocat (`blocat`) trece printr-o verificare cu browser, dacă aceasta rulează. Dacă browserul primește un cod sub 400, starea devine `activ`.
Dacă primește alt cod de eroare decât 401, 403, 429 sau 503, sau nu poate deschide pagina, starea devine `offline`. Un timp depășit lasă starea „Neconfirmat”.

### Ce schimbă starea în listă

- Intrările Offline și Arhivat sunt ascunse implicit („Ascunde proiecte inactive”). Contoarele filelor nu le numără.
- Intrările Activ și Neconfirmat pot primi eticheta „neactualizat din AAAA” (vezi secțiunea 4).
- Scorul se înmulțește cu 0,4 pentru orice stare în afară de Activ și Neconfirmat (secțiunea 6).

## 2. Cod public și licență

- Insigna „cod public” și filtrul „Doar cu cod sursă public” înseamnă că intrarea are un link către cod.
  Linkul vine din coloana `linkuri` (rolurile `github`, `gitlab`, `cod`) sau din linkurile către GitHub, GitLab sau Codeberg
  găsite pe pagina principală.
- Un link către cod **nu este o licență open source**. `build.py` nu verifică licența, conținutul sau completitudinea depozitului.
- Un link găsit pe pagina principală poate duce la contul autorului sau la un alt proiect, nu la depozitul intrării.
- Dacă intrarea nu are link către cod, `profile.py` caută pe GitHub un depozit cu pagina principală egală cu domeniul
  și cu un nume asemănător domeniului. Căutarea rulează doar pentru un site care răspunde și are adresa la rădăcina domeniului.
  Rezultatul e o presupunere automată.
- Statisticile depozitului (licență, stele, commit-uri, contribuitori) există doar pentru depozite GitHub.
- Rândul „Licență” apare doar când GitHub raportează un identificator SPDX pentru primul depozit GitHub al intrării.
  Valoarea `NOASSERTION` se ignoră. Lipsa rândului nu înseamnă că depozitul n-are licență.
  Licența unui depozit nu spune nimic despre datele sau serviciul proiectului.
- Un depozit arhivat pe GitHub apare cu eticheta „arhivat” și poate face intrarea „neactualizată” (secțiunea 4).

## 3. Prima urmă observată

Câmpul `since` este **prima urmă pe care a observat-o verificarea automată**. Nu este data lansării.

`since` este data cea mai veche dintre:

1. prima captură reușită (HTTP 200) a adresei exacte a intrării în Wayback Machine (se ignoră `https://` și `www.`);
2. crearea depozitului de cod pe GitHub.

Dacă niciuna nu există, `since` este data primului certificat TLS al domeniului, din crt.sh.
Certificatul se citește doar pentru intrările al căror URL este rădăcina unui domeniu.
Un domeniu poate fi mai vechi decât proiectul care îl folosește acum.

Cum se vede în site (cod `site-v2/app.js`; interfața veche, `site/app.js`, numește aceeași dată „Vechime”
și aceeași insignă „nou” sau „lansat recent”):

- „Prima urmă observată” în fișă, cu data și sursa.
- Insigna „apărut recent” pentru o primă urmă mai nouă de 183 de zile. Insigna plină înseamnă mai puțin de 60 de zile.
- Ordonarea „Apărute recent (prima urmă)” și filtrul „Doar proiecte apărute recent”.
- Coloana „Prima urmă” din listă (secțiunea 5).
- Feed-ul RSS listează cele mai noi 40 de proiecte după această dată. El omite proiectele Offline și Arhivat.

O urmă recentă poate însemna un proiect nou. Poate însemna și un site vechi pe care arhiva web sau GitHub l-au văzut târziu.
Un proiect fără nicio urmă n-are insignă și apare ultimul la ordonarea după această dată.

## 4. Ultima actualizare și „neactualizat”

`updated` este cea mai nouă dată dintre aceste surse:

| Sursă | Ce măsoară |
| --- | --- |
| `cod` | Ultimul push în depozitul de cod. |
| `feed` | Data celui mai nou articol dintr-un feed RSS sau Atom. |
| `wordpress` | Ultima modificare a unui articol sau a unei pagini, din API-ul WordPress. |
| `sitemap` | Cel mai nou `lastmod` din sitemap. |
| `server` | Antetul `Last-Modified` al paginii. |

Sursa `cod` se citește pentru orice intrare cu depozit GitHub. Celelalte patru se citesc doar pentru un site care răspunde.
Pentru un site care nu răspunde, profilerul folosește în plus data ultimei capturi din arhiva web (`arhiva`).
Profilerul ignoră datele de ieri și de azi: paginile dinamice raportează de obicei data curentă.
Pentru un proiect aflat pe o subpagină a unui site mai mare, profilerul nu citește feed-ul, sitemap-ul și WordPress,
fiindcă nu aparțin proiectului.

Aceste date arată ce a observat verificarea. Ele nu dovedesc că datele sau serviciul proiectului sunt la zi.
Un depozit poate primi push-uri fără ca site-ul să se schimbe. Un sitemap poate fi regenerat automat.

`last_activity` (în `build.py`) este `updated`, dacă acesta există. Numai fără `updated`, `build.py` folosește anul din notița
de drepturi de autor a paginii principale (cel mai mare an găsit după © sau „copyright”), ca 1 ianuarie al acelui an.
O dată din viitor se ignoră. Multe pagini scriu anul curent automat, deci anul din notiță este un semnal slab.
`build.py` folosește `last_activity` în două locuri:

- eticheta „neactualizat din AAAA”: pentru o intrare Activ sau Neconfirmat cu o dată de activitate, când aceasta e mai veche
  de 3 ani sau depozitul de cod este arhivat;
- termenul „activitate” al scorului (secțiunea 6).

## 5. Coloanele „Prima urmă” și „Actualizat”

Lista arată pentru fiecare intrare un interval scurt, cu o literă:

| Literă | Înseamnă | Exemplu |
| --- | --- | --- |
| `Z` | zile | `9Z` = 9 zile |
| `L` | luni | `2L` = 2 luni |
| `A` | ani | `13A` = 13 ani |

Intervalul se numără de la data din coloană până azi. Sub o zi, lista scrie „azi”. Trecând cu mouse-ul peste celulă
se vede data exactă și sursa ei. Pe ecrane înguste, fiecare intrare arată aceleași date în cuvinte.

## 6. Scorul de relevanță

`score` este un număr de la 0 la 100, calculat în `build.py` (funcția `score`). Ordonarea „Relevanță” folosește doar acest număr.
Scorul este o euristică de ordonare. Ponderile pot fi ajustate.

Scorul are cinci termeni. Fiecare termen dă un factor între 0 și 1. Punctele sunt factorul înmulțit cu maximul termenului.

| Termen | Puncte maxime | Cum se calculează factorul |
| --- | --- | --- |
| Activitate | 30 | Din `last_activity`: sub 3 luni = 1; sub 1 an = 0,75; sub 2 ani = 0,45; sub 4 ani = 0,2; mai vechi = 0. Fără nicio dată = 0,3. |
| Vizibilitate | 25 | Media ponderată a șapte semnale (tabelul de mai jos). |
| Volum | 15 | Numărul de adrese din sitemap, cu scară logaritmică; maximul la 5000 de adrese. |
| Vechime | 15 | Anii de la `since`, împărțiți la 8; maximul la 8 ani. |
| Documentare | 15 | Media a patru răspunsuri da/nu: descriere scurtă, descriere (din catalog sau preluată de pe site), subiect principal (în datele v1: cuvinte cheie), imagine. |

Rezultatul se înmulțește cu 1 pentru Activ și Neconfirmat și cu 0,4 pentru Offline, Arhivat și Neverificat. Apoi se rotunjește.

### Vizibilitate

| Semnal | Pondere | Maximul la | Sursă |
| --- | --- | --- | --- |
| Luni cu capturi în arhiva web | 0,30 | 120 de luni | Wayback Machine, o lună = cel puțin o captură reușită |
| Gazde independente care menționează intrarea | 0,20 | 15 gazde | `mentiuni.csv` și etichetele din `review.py` |
| Gazde de știri | 0,10 | 10 gazde | etichete din `review.py` |
| Gazde de cercetare sau guvern | 0,05 | 5 gazde | etichete din `review.py` |
| Open PageRank | 0,15 | valoarea 6 | `profile.py --opr` (fără rulare: 0) |
| Articole Wikipedia (ro și en) care trimit la domeniu | 0,10 | 20 de articole | API-ul Wikipedia |
| Stele pe GitHub | 0,10 | 200 de stele | primul depozit al intrării |

Fiecare semnal, în afară de Open PageRank, folosește o scară logaritmică: `ln(1 + valoare) / ln(1 + maxim)`, cu plafon 1.
Jumătate din puncte se obțin deja la `√(1 + maxim) − 1`: circa 10 luni de arhivă, 3 gazde independente,
70 de adrese în sitemap sau 13 stele.

**Mențiunile.** `search.py` memorează toate rezultatele și marchează pe cele care cad sub o regulă de excludere:
magazine, rețele sociale, găzduiri de cod, registre de firme, site-uri generate pentru orice domeniu, site-uri care răspund
la orice nume (dicționare, joburi, muzică, film) și site-urile proprii ale intrării. Un editor poate păstra (`1`) sau elimina (`0`)
un rezultat. `build.py` folosește rezultatele păstrate.
O etichetă contează numai pentru un rezultat păstrat cu aceeași adresă. O etichetă rămasă de la un rezultat eliminat nu contează.
Dacă toate rezultatele păstrate au etichete, `build.py` numără gazdele paginilor etichetate „despre proiect” și „independente”.
Dacă numai o parte au etichete, `build.py` adaugă gazdele rezultatelor fără etichetă și marchează numărul ca provizoriu.
Fără etichete, `build.py` numără gazdele distincte ale rezultatelor păstrate. `build.py` afișează acoperirea etichetelor la fiecare rulare.
Modelul de limbaj scrie etichetele, iar `build.py` le folosește direct.

### Ce favorizează scorul

- **Vechimea.** Arhiva web și `since` aduc împreună până la 22,5 puncte din 100. Un proiect nou nu poate câștiga aceste puncte.
- **Numărul de pagini.** Un site mare, cu sitemap, primește mai multe puncte decât un instrument mic și bine făcut.
- **Vizibilitatea.** Un proiect despre care scrie multă lume, cu stele și link-uri din Wikipedia, primește mai multe puncte.
- **Completarea catalogului.** Documentarea cere descriere scurtă, descriere, subiect și imagine.

Scorul nu măsoară calitatea, impactul civic, corectitudinea datelor sau utilitatea. Un proiect fără sitemap,
fără depozit public sau fără capturi în arhiva web pierde puncte fără să fie mai slab.

### Ordonarea „Active și relevante”

Această ordonare (în `site-v2/app.js`) pornește de la scor. Ea înmulțește scorul cu `0,5 + 0,5 × proaspăt`
și adaugă 8 puncte pentru o primă urmă mai nouă de 60 de zile.
`proaspăt` este `e^(−zile / 365)`, unde `zile` este vârsta ultimului semn de viață: ultima actualizare
sau, dacă e mai nouă, prima urmă recentă. Fără nicio dată, `proaspăt` este 0,25.

## Limite

- Starea arată ce s-a văzut la data verificării. Verificarea nu rulează continuu.
- „Activ” înseamnă că adresa răspunde. Nu înseamnă că proiectul funcționează.
- Un link către cod nu este o licență. Licența apare doar când GitHub o raportează.
- „Prima urmă observată” nu este data lansării.
- Datele de actualizare vin din semnale tehnice (depozit, feed, sitemap, antet). Ele pot fi regenerate automat.
- Scorul favorizează vechimea, numărul de pagini și vizibilitatea. El nu măsoară calitatea.
- Pentru proiectele de pe o subpagină a unui site mai mare, profilerul nu citește sitemap-ul, feed-ul și certificatul gazdei.

## Unde în cod

| Ce | Unde |
| --- | --- |
| Starea profilerului | `classify()` în `scripts/profile.py` |
| Starea afișată | `status_of()` în `scripts/build.py` |
| „Neactualizat” | `observed()` în `scripts/build.py` |
| Prima urmă | `since()` în `scripts/build.py`; surse în `extras_one()` din `scripts/profile.py` |
| Ultima activitate | `last_activity()` în `scripts/build.py`; surse în `extras_one()` din `scripts/profile.py` |
| Scorul | `score()` și `reach_features()` în `scripts/build.py` |
| Insigne, coloane, ordonări | `site-v2/app.js` |
