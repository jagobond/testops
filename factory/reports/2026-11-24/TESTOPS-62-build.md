# TESTOPS-62 build - a word in the name is not a clause

Ticket: `factory/tickets/TESTOPS-62.md`. Branch: `factory/testops-62-predication`.
Store copy used for all runs: `data/` in this worktree. The live store and port 8791 were never
contacted.

## The rule, in the rule's own terms

`_names_a_credential` (testops/services.py) no longer exempts a name because it contains a finite verb
or a negator **anywhere**. The exemption now holds only when the parts are a **predication about the
credential word**:

- a **subject** - at least one part before the predicate head that is not itself a verb or negator;
- a **predicate head** - a finite verb from the closed auxiliary/copula class, or a true negator
  (`not`, `never`) read as an elided copula ("xox [is] not a Slack token");
- the **credential word as the complement after the head**, and the last part of the name.

Implemented as `_is_predication(lowered, credential_index)`, called only after the determiner test.
A verb or negator anywhere triggers the predication test; failing it makes the determiner decisive
and the name is refused. Plain determiner-bearing compounds whose credential word is not the final
part (`password-manager`, `token-bucket-limiter`, `the-token-service`) still fall through as compound
nouns, and names with no determiner (`session-token`, `vault-token`, `prod-db-password`) still pass
as kind names.

**Precedence (AC3), stated once in code and pinned in the test:** `no` is in both `_DETERMINERS` and
`_NEGATORS`; it is read **only as a determiner**, so it takes a name into the instance test and is
excluded from `_PREDICATE_HEADS`. It can never be the predicate that excuses the instance it marked.

## AC1 - the credential word must be the complement

- `this-is-not-a-password` accepted: subject `this`, head `is`, complement `a-password`.
- `my-password-is-here`, `the-token-is-abcd1234`, `this-token-was-leaked`, `my-secret-has-value`
  refused: the credential word is the verb's **subject**, so the name labels an instance.

## AC2 - fragments are not clauses (all refused)

`has-my-token` and `is-my-password` (nothing before the head), `never-the-api-token` (nothing before
the negator), `no-password-yet` (`no` is a determiner and no predicate is made),
`x-not-a-token-but-abcdef` (the credential word is not the final complement).
`not-a-password` and `not-my-password` fall to the same rule: a denial with no subject is a fragment.
`xox-not-a-slack-token` is the other direction - a subject before `not` and the credential word as
its complement - and stays accepted (one of the TESTOPS-59 twenty ordinary values).

## AC3 - a negator alone never excuses

`acme-no-password` and `acme-their-no-password` refused; `no-password-yet` refused. Precedence is
commented above `_NEGATORS`/`_PREDICATE_HEADS` and asserted in
`test_a_word_in_two_classes_cannot_satisfy_both_tests`, including `"no" not in _PREDICATE_HEADS`.
`acme-not-password` (true negator, subject, final complement) is accepted; `never-the-api-token`
remains refused.

## AC4 - the boundary table argues the boundary

`tests/test_config_credential_screen.py::BOUNDARY` now carries, each with a one-line grammatical
reason: the ten TESTOPS-61 review probes (`my-password-is-here`, `the-token-is-abcd1234`,
`not-my-password`, `never-the-api-token`, `my-secret-has-value`, `is-my-password`, `has-my-token`,
`no-password-yet`, `this-token-was-leaked`, `x-not-a-token-but-abcdef`), the follow-up
`acme-no-password`, `acme-their-no-password`, and both named AC1 cases plus `this-is-not-a-password`.
The `not-a-password` row moved from accepted to refused with its reason (denial fragment, no
subject); `xox-not-a-slack-token` keeps its accepted row with the reason restated as a denial with a
subject and complement.

## AC5 - no weakening, no regression

- The T59 leak probes are unchanged and green (tokens/JWT/PEM/name=value inside sentences).
- All twenty ordinary T59 values still accept, including `xox-not-a-slack-token`,
  `password-list`, `passwords-list`, `the-token-service`, `my-secret-store`,
  `my-password-manager`, `session-token`, `vault-token`.
- `token-bucket-limiter`, `session-token`, `vault-token`, `password-manager/tool` accepted;
  `acme-their-prod-db-password` refused. All pinned in the boundary table.

## AC6 - verification

Interpreter:

    env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 \
      C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe -m pytest -q

- Contract suite: `pytest tests/contracts -q` -> **37 passed, 2 skipped**.
- Full suite: `pytest -q` -> **866 passed, 2 skipped**.
- Case-page goldens untouched: `git status --short` shows only `testops/services.py` and
  `tests/test_config_credential_screen.py`.

## Residual, stated rather than hidden

The exemption is now a claim about the *syntax of the name*, not the presence of a word: a subject
must precede a finite verb or true negator, and the credential word must be that predicate's final
complement. Consequences that remain:

- a name with no determiner is still accepted as a kind name even if it contains a verb
  (`prod-db-password`, `has-token` as a compound-looking label) - the determiner is the marker that
  a name claims to label a particular instance;
- a true-negator denial with a subject (`acme-not-password`) is accepted, because it is a
  predication about the credential word, not a label for one;
- `not-a-password` is now refused rather than accepted: with no subject it is a fragment, the same
  shape as `never-the-api-token`. This is a deliberate narrowing, not a detection change - no
  credential shape was weakened and no pasted secret becomes storable.
