# Cum propui un proiect

Două căi, același format:

1. **GitHub** — adaugă un rând în `data/proiecte.csv` (proiecte și resurse) sau `data/orgs.csv` (organizații) și deschide un pull request. Verificarea automată (`scripts/validate.py`) îți arată pe PR ce trebuie corectat.
2. **Formular / Google Sheets** — completezi formularul; rândul ajunge într-un tabel cu aceleași coloane și e adus în repo printr-un PR revizuit de echipă.

Fișierele se pot edita și ca tabel (LibreOffice, Excel, Google Sheets) — păstrează encodarea UTF-8 și separatorul virgulă.

## Coloane — `proiecte.csv`

| coloană | ce conține |
| --- | --- |
| `slug` | identificator unic: litere mici, cifre, cratime (`harta-firmelor`) |
| `fel` | `proiect` sau `resursa` (listă, ghid, colecție) |
| `nume` | numele proiectului, așa cum îl folosește el |
| `descriere_scurta` | o frază, sub ~90 de caractere |
| `descriere` | ce face, pentru cine, din ce date |
| `url` | adresa principală |
| `linkuri` | **toate celelalte linkuri, în aceeași celulă**, separate prin spațiu sau linie nouă (sau listă JSON). Tipul se deduce din domeniu (Facebook, GitHub…) sau îl scrii în față: `donatii:` `despre:` `contact:` `termeni:` `date:` `api:` `mcp:` `cod:`. Primul link GitHub/GitLab/`cod:` e codul sursă. |
| `domeniu` | una dintre cheile din `data/taxonomy.json` → `domenii` (`bani`, `politica`, `justitie`…) |
| `tip` | una sau mai multe chei din `tipuri`, separate prin virgulă, cea principală prima (`instrument`, `vizualizare`, `harta`, `baza-de-date`, `monitorizare`, `educativ`, `ghid`) |
| `cuvinte` | cuvinte cheie separate prin virgulă |
| `acoperire` | `national`, `local` sau `international` |
| `oras` | pentru proiectele locale |
| `autor` | oameni sau organizații, separați prin ` / ` |
| `contact` | opțional |
| `civictech` | `1` dacă e un proiect civic tech (făcut de societatea civilă / voluntari), `0` altfel |
| `stare` | gol (verificată automat), `arhivat` sau `offline` |
| `nota` | note interne, nu apar pe site |

`orgs.csv` are aceleași coloane, fără `fel`, `tip`, `autor`, `contact` și `civictech`.

Restul — starea site-ului, imaginea, iconița, linkurile sociale găsite pe pagină — se completează automat (`scripts/profile.py` → `data/profil.csv`).
