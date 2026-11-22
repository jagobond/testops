# Third-party notices

This repository redistributes third-party code. This file is the index; the full notice travels with
the copy.

## reqnroll/Sample-ReqOverflow

- What: `tests/fixtures/reqoverflow/` - 108 `.cs` and `.feature` files copied verbatim from the three
  test projects of the sample (`ReqOverflow.Specs.API`, `ReqOverflow.Specs.Controller`,
  `ReqOverflow.Specs.WebUI`). They are test data for the duplication analyser, not a build target.
- Upstream: https://github.com/reqnroll/Sample-ReqOverflow at commit
  `78153818b81d7c9a324af81b4e95f65aead705b4`
- Licence: MIT
- Copyright: Copyright (c) 2013-2024 Reqnroll and Gaspar Nagy, https://www.specsolutions.eu
- Full licence text: `tests/fixtures/reqoverflow/LICENSE`
- Provenance, the exact file set copied, what was left out, and the one mechanical difference (a
  stripped UTF-8 byte-order mark): `tests/fixtures/reqoverflow/PROVENANCE.md`

The MIT licence requires the copyright notice and permission notice to accompany copies of the
software. Both are in `tests/fixtures/reqoverflow/LICENSE`; do not remove that file or this one when
tidying the fixture. `tests/test_third_party_attribution.py` fails if either goes missing.
