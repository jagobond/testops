# Third-party notices

This repository redistributes third-party code. This file is the index; the full notice travels with
the copy.

## reqnroll/Sample-ReqOverflow

- What: `tests/fixtures/demo-service/` - 108 `.cs` and `.feature` files copied from the three test
  projects of the sample (`ReqOverflow.Specs.API`, `ReqOverflow.Specs.Controller`,
  `ReqOverflow.Specs.WebUI`). They are test data for the duplication analyser, not a build target.
  Since TESTOPS-103 the copy's own names are neutral (`DemoService.Specs.API`, and so on) and the
  text was renamed with them; the upstream names are here because this is where the attribution is
  made, and `PROVENANCE.md` records exactly what was changed.
- Upstream: https://github.com/reqnroll/Sample-ReqOverflow at commit
  `78153818b81d7c9a324af81b4e95f65aead705b4`
- Licence: MIT
- Copyright: Copyright (c) 2013-2024 Reqnroll and Gaspar Nagy, https://www.specsolutions.eu
- Full licence text: `tests/fixtures/demo-service/LICENSE`
- Provenance, the exact file set copied, what was left out, and the two mechanical differences (a
  stripped UTF-8 byte-order mark, and the TESTOPS-103 rename): `tests/fixtures/demo-service/PROVENANCE.md`

The MIT licence requires the copyright notice and permission notice to accompany copies of the
software. Both are in `tests/fixtures/demo-service/LICENSE`; do not remove that file or this one when
tidying the fixture. `tests/test_third_party_attribution.py` fails if either goes missing.
