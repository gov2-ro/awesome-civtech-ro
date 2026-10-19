# Sources for the taxonomy proposal

Checked on 2026-10-19. These sources informed the model; they do not validate the individual catalogue entries.

- [EuroVoc, Publications Office](https://op.europa.eu/en/web/eu-vocabularies/dataset/-/resource?uri=http%3A%2F%2Fpublications.europa.eu%2Fresource%2Fdataset%2Feurovoc): multilingual subject thesaurus, including Romanian.
- [Official SPARQL endpoint](https://publications.europa.eu/webapi/rdf/sparql): source of `eurovoc-response.json`.
  `eurovoc-query.rq` contains the exact query. The response includes 22 concept URIs with English and Romanian preferred labels.
  The query requested 30 English labels; only the returned 22 are proposed mappings. Missing results were not guessed.
- [W3C SKOS Primer](https://www.w3.org/TR/skos-primer/): concepts, preferred and alternative labels, concept schemes, and hierarchical relations.
- [W3C SKOS Reference](https://www.w3.org/TR/skos-reference/): semantic and mapping properties, including `closeMatch` and `exactMatch`.
- [ISO 25964 overview, NISO](https://www.niso.org/standards-committees/iso-25964): thesaurus construction and interoperability guidance.
  The full standard was not used to conduct a conformity assessment.
- [EU controlled vocabularies](https://op.europa.eu/fi/web/eu-vocabularies/controlled-vocabularies): Data Theme is intended for dataset classification.
  No Data Theme mappings are asserted in this proposal.
- [OECD COFOG data](https://data-explorer.oecd.org/vis?df%5Bag%5D=OECD.SDD.NAD&df%5Bds%5D=DisseminateFinalDMZ&df%5Bid%5D=DSD_NASEC10%40DF_TABLE11): government expenditure by function.
  No COFOG mappings are asserted in this proposal.

The thirteen top-level browsing subjects are local editorial groupings. They are not the official EuroVoc top-level hierarchy.
Target identifiers and labels were verified through the official endpoint. The meanings of the local-to-external mappings remain editorial proposals.
The proposal does not claim that a project complies with any EU or W3C specification.
