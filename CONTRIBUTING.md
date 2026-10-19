# Cum propui un proiect

Patru căi. Primele trei folosesc același format de date:

1. **GitHub** — adaugă un rând în `data/proiecte.csv` (proiecte și resurse) sau `data/orgs.csv` (organizații) și deschide un pull request. Verificarea automată (`scripts/validate.py`) îți arată pe PR ce trebuie corectat.
2. **Formular** — completezi [formularul public](https://forms.gle/wswqrm7P4QV25NZx7). Răspunsul ajunge într-un tab separat al tabelului Google Sheets (`propuneri`), cu alte coloane decât CSV-urile. Un editor îl verifică și îl copiază în tabul `proiecte` sau `orgs`, ori în CSV.
3. **Tabelul Google Sheets** — dacă ai drept de editare, corectezi rândul direct în tabul `proiecte` sau `orgs`. Tabul are aceleași coloane ca CSV-ul, în aceeași ordine. Nu schimba rândul 1 și nu scrie în dreapta ultimei coloane. Un workflow aduce modificările în repo printr-un pull request („Sheets: modificări din tabel”), la fiecare 6 ore sau la cerere. Echipa îl revizuiește. Dacă aceeași celulă s-a schimbat și în repo, sincronizarea se oprește până când un editor egalează valorile.
4. **Issue** — deschide un [issue pe GitHub](https://github.com/gov2-ro/awesome-civtech-ro/issues/new) cu adresa și o scurtă explicație.

Fișierele se pot edita și ca tabel (LibreOffice, Excel, Google Sheets) — păstrează encodarea UTF-8 și separatorul virgulă.

## Înainte de pull request

Rulează din rădăcina depozitului. Ai nevoie doar de Python 3, fără pachete.

```sh
python3 scripts/validate.py   # verifică data/proiecte.csv și data/orgs.csv
python3 scripts/build.py      # construiește site/data.json din ele
```

GitHub rulează aceleași comenzi pe fiecare pull request care schimbă `data/`, `scripts/`, `site/`, `site-v2/` sau workflow-urile, plus testele unitare și verificările previzualizării v2. Un rând nou apare pe site cu starea „Neverificat” și fără mențiuni, până când un editor rulează `scripts/profile.py` și `scripts/search.py` pe calculatorul lui. GitHub nu le rulează.

## Coloane — `proiecte.csv`

| coloană | ce conține |
| --- | --- |
| `slug` | identificator unic: litere mici, cifre, cratime (`harta-firmelor`) |
| `fel` | `proiect`, sau o resursă: `resursa` (listă, colecție), `articol`, `ghid`, `campanie`, `cercetare`. Resursele apar la „Resurse & liste” |
| `nume` | numele proiectului, așa cum îl folosește el |
| `descriere_scurta` | o frază, sub ~90 de caractere |
| `descriere` | ce face, pentru cine, din ce date |
| `url` | adresa principală |
| `linkuri` | **toate celelalte linkuri, în aceeași celulă**, separate prin spațiu, virgulă, `\|` sau linie nouă (sau listă JSON). Tipul se deduce din domeniu (Facebook, GitHub…) sau îl scrii în față: `donatii:` `despre:` `contact:` `termeni:` `date:` `api:` `mcp:` `cod:`. Primul link GitHub/GitLab/`cod:` e codul sursă. |
| `domeniu` | una dintre cheile din `data/taxonomy.json` → `domenii` (`bani`, `politica`, `justitie`…) |
| `tip` | una sau mai multe chei din `tipuri`, separate prin virgulă, cea principală prima (`instrument`, `vizualizare`, `harta`, `baza-de-date`, `monitorizare`, `educativ`, `ghid`) |
| `cuvinte` | cuvinte cheie separate prin virgulă |
| `acoperire` | `national`, `local` sau `international`. Goală înseamnă `national` |
| `oras` | pentru proiectele locale |
| `autor` | oameni sau organizații, separați prin ` / `. Dacă numele e `slug`-ul unui rând din `orgs.csv` (`funky-citizens`), proiectul apare legat de organizație, iar pagina organizației îi listează proiectele |
| `contact` | opțional |
| `civictech` | `1` dacă e un proiect civic tech (făcut de societatea civilă / voluntari), `0` altfel |
| `stare` | gol (verificată automat), `arhivat` sau `offline`. Un site offline pe care Wayback Machine nu l-a mai văzut de un an apare automat ca `arhivat`. |
| `nota` | note interne, nu apar pe site |

`orgs.csv` are aceleași coloane, fără `fel`, `tip`, `autor`, `contact` și `civictech`.

Restul — starea site-ului, imaginea, iconița, linkurile sociale găsite pe pagină — se completează automat (`scripts/profile.py` → `data/profil.csv`).

Toate fișierele de date, coloană cu coloană, sunt descrise (în engleză) în [docs/DATA-SCHEMA.md](docs/DATA-SCHEMA.md).

## Rezultatele căutării — `mentiuni.csv`

`scripts/search.py` salvează în `data/mentiuni.csv` paginile găsite pe web despre fiecare intrare (Google prin Serper, plus Brave). Fișierul e generat, cu o singură excepție: coloana `editor` o completezi tu.

| `editor` | ce înseamnă |
| --- | --- |
| `1` | păstrează rezultatul, chiar dacă o regulă automată îl respinge (coloana `regula` nu e goală) |
| `0` | elimină rezultatul, chiar dacă nicio regulă nu îl respinge |
| gol | decide regula: rezultatul se păstrează doar dacă `regula` e goală |

Coloana `regula` spune de ce a fost respins un rezultat: `propriu` (site-ul intrării, linkurile ei și site-urile autorilor), `social`, `cod`, `magazin`, `registru`, `ferma`, `zgomot`. Regulile marchează rândurile, nu le șterg. La următoarea rulare, `search.py` păstrează valorile din `editor`.

Rezultatele păstrate sunt etichetate de `scripts/review.py` în `data/mentiuni_etichete.csv` (generat, nu se editează) și intră apoi în scorul „Relevanță".

## Clasificarea v2 (previzualizare)

Echipa pregătește o clasificare nouă a intrărilor, numită „taxonomia v2”. În locul unui singur `domeniu`, fiecare intrare primește mai multe fațete: subiecte, scopuri, funcționalități, formate, tehnologii, instituții, maturitate și zone acoperite. Fiecare valoare este un identificator dintr-un vocabular controlat.

Clasificarea v2 există doar ca previzualizare. Propunerile ei sunt în `data/taxonomy-v2/`, iar echipa nu a acceptat încă nicio clasificare. Site-ul public folosește în continuare `domeniu`, `tip` și `cuvinte` din `proiecte.csv` și `orgs.csv`.

Ce înseamnă pentru tine:

- Propui un proiect ca mai sus, cu coloanele din `proiecte.csv` și `orgs.csv`. Nu alegi concepte v2.
- Nu editezi fișierele din `data/taxonomy-v2/`. Contribuitorii nu le pot edita încă: un editor revizuiește clasificările.
- Formularul public și tabul `proiecte` / `orgs` păstrează întrebările și coloanele de azi. Variantele pentru v2 (tab-urile `v2-intrari` și `v2-revizuire`, planul formularului v2) sunt previzualizări și nu sunt conectate la site-ul public.
- Dacă schimbi un rând din `proiecte.csv` sau `orgs.csv`, intrarea corespunzătoare din `data/taxonomy-v2/` nu se actualizează singură.

Detalii pentru editori: [data/taxonomy-v2/README.md](data/taxonomy-v2/README.md) (ghidul de editare, în română), [docs/specs/taxonomy-v2.md](docs/specs/taxonomy-v2.md) (specificația) și [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#taxonomy-v2-preview) (cum se leagă de restul).
