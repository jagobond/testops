# The product-line golden pages

Each page is the whole `/case/case-product-line` page rendered by `app.case_page` from the fixture
in `tests/test_case_product_line.py` with `app.age` frozen to "a fixed time ago". They are pinned
byte for byte (`test_the_*_is_pinned_*`), so a change to a sentence fails a test before it can ship
silently.

| page | the declaration's state |
|---|---|
| `case-product-line-complete.html` | complete and small: the annotation and signature are the whole declaration. No ellipsis, no count. |
| `case-product-line-trimmed.html` | delimited but trimmed: a 64-line body, of which two signature lines are shown. A count and an ellipsis. |
| `case-product-line-undelimitable.html` | undelimitable: the stored file ends inside the method body, so the `{` is found and never closed. "The rest of this declaration could not be delimited", an ellipsis, and no count. |
| `case-product-line-missing.html` | the store holds no declaration for the matched surface (TESTOPS-83): no code block at all, a sentence naming the absence. |

Regenerating is a deliberate act: render the fixture with `app.age` frozen and write the returned
bytes to the file. `git` stores LF; a `core.autocrlf` checkout presents CRLF and the tests compare
on normalised newlines, because a line-ending translation is not a changed page.
