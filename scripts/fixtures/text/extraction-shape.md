## Consolidated schema reference

Common envelope:

```json
{
  "schema_version": "1.5.0",
  "document_id": "mo://2026/PII/48",
  "content_sha": "a3f9c1d2e4b8",
  "document_type": "plenary_stenogram | plenary_joint_session | committee_synthesis | report_facsimile | question_register | other",
  "metadata": {
    "issue": "48",
    "year": 2026,
    "part": "II",
    "published": "2026-04-29",
    "chamber": "Camera Deputaților | Senatul | joint",
    "session": "SESIUNEA I ORDINARĂ – APRILIE 2026",
    "session_type": "ordinary | extraordinary | null",
    "session_date": "2026-04-14",
    "legislature": "X"
  },
  "raw_markdown_path": "pdfs/2026-04-29_MO-PII-48-2026.md",
  "raw_pdf_path": "pdfs/2026-04-29_MO-PII-48-2026.pdf",
  "extraction": {
    "extractor": "hybrid@1",
    "extracted_at": "2026-05-04T08:30:00Z",
    "extractor_versions": {                                         // 1.5.0: per-component dict, open-ended
      "boilerplate": "0.1.0",
      "coverage": "0.1.0",
      "references": "0.1.0",
      "speakers": "0.1.0",
      "question_register": "0.1.0",
      "topic_classifier": null
    },
    "confidence": 0.94
  },
  "coverage": {                                                     // 1.5.0: added
    "body_chars": 45230,
    "claimed_chars": 44890,
    "claimed_pct": 0.9925,
    "gaps": [
      { "chars": [12340, 12390], "lines": [421, 423], "preview": "..." }
    ],
    "claimed_by_policy": [
      { "chars": [0, 87], "lines": [1, 4], "reason": "shared_boilerplate.partea_header" }
    ]
  },
  "body": { "...one of the five shapes below..." }
}
```

### body for `committee_synthesis`

```json
{
  "period": { "start": "2013-04-08", "end": "2013-04-11" },
  "committees": [
    {
      "name": "Comisia pentru politică economică, reformă și privatizare",
      "kind": "permanent | special | inquiry | special_joint | inquiry_joint",  // 1.3.0: added
      "chair": Speaker,
      "meetings": [
        {
          "dates": ["2013-04-08"],                         // 1.1.0: was singular
          "joint_with": [                                  // 1.3.0: items: string → { name, chamber }
            { "name": "Comisia pentru buget, finanțe și bănci", "chamber": "camera" }
          ],
          "presider": Speaker,
          "format": "in_person | online | mixed",          // 1.1.0: added
          "purpose": "documentare_consultare | dezbatere_decizie | aprobare_raport | audiere_candidați | null",  // 1.4.0: audiere_candidați added
          "time_windows": [{ "start": "08:30", "end": "12:00" },
                           { "start": "13:00", "end": "18:00" }],  // 1.1.0: was started_at
          "roster": [                                      // 1.1.0: replaces attendees+absentees+substitutions
            { "speaker": Speaker,
              "mode": "physical | online | absent | substituted",
              "intra_committee_role": "președinte | vicepreședinte | secretar | membru",  // 1.2.0: added
              "substituted_by": Speaker }
          ],
          "guests": [{ "name": "Claudiu Doltu", "title": "secretar de stat",
                       "organization": "Ministerul Finanțelor Publice" }],
          "agenda": [
            {
              "ordinal": 1,
              "title": "Cererea de reexaminare a Legii pentru aprobarea OUG nr. 93/2012...",
              "primary_references": [Reference, "..."],    // 1.1.0: pluralized for consistency with plenary
              "co_committees": ["Comisia pentru industrii și servicii",
                                "Comisia juridică, de disciplină și imunități"],  // 1.1.0: pluralized
              "committee_role": "fond | aviz | fond_comun",   // 1.1.0: added
              "output_type": "raport | raport_preliminar | raport_suplimentar | raport_comun | raport_comun_suplimentar | aviz | studiu | proiect_de_opinie | amânare",  // 1.4.0: raport_comun, raport_comun_suplimentar added
              "for_committees": ["Comisia pentru muncă și protecție socială"],  // 1.4.0: pluralised — populated when output_type ∈ {raport_preliminar, aviz}
              "outcome_text": "...",
              "vote_summary": {
}
```
