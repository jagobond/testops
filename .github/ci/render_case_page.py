"""TESTOPS-15 AC3 - import the app and serve one real case page, on the interpreter that runs it.

The compile guard in ``tests/test_python_floor.py`` protects the construct that broke the floor
(a backslash inside an f-string expression). It cannot protect the floor itself: ``from itertools
import batched`` compiles cleanly on 3.11 and dies at import, past both sides of the guard. The only
check that covers that class of failure is running the thing.

So this script does what a person would: it builds a store from the page-contract suite's own
fixture (``tests/test_case_page.py``), imports ``testops.web.app``, renders the case page straight
from the store, and then serves the same page over HTTP through ``app.Handler`` - the code path a
reader's browser actually takes. A page that raises, an import that needs a newer interpreter, or a
handler that returns anything but 200 fails the job.

The store lives under a temporary directory, never in the checkout: the suite's isolation guard and
the repository's own hygiene both depend on that.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _fail(message: str) -> int:
    print(f"FAIL: {message}")
    return 1


def main() -> int:
    print(f"interpreter: Python {sys.version.split()[0]} ({sys.platform})")

    with tempfile.TemporaryDirectory(prefix="testops-render-") as tmp:
        # Read before importing testops.config: DB_PATH and DATA are computed from it at import.
        os.environ["TESTOPS_HOME"] = tmp

        sys.path.insert(0, str(ROOT / "tests"))
        sys.path.insert(0, str(ROOT))

        import test_case_page as fixture          # the suite's own store fixture
        from testops import config
        from testops.store import db
        from testops.web import app

        built = Path(tmp) / "fixture"
        conn, claim_id = fixture._seed(built)
        conn.close()
        fixture_db = built / "case-page.db"
        if not fixture_db.is_file():
            return _fail(f"the store fixture wrote no database at {fixture_db}")

        # app.Handler opens the default store, so the fixture has to be where it looks. Both paths
        # are under $TESTOPS_HOME, which is the temporary directory above.
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fixture_db, config.DB_PATH)
        print(f"store fixture: one claim ({claim_id}), one case ({fixture.CASE}) -> {config.DB_PATH}")

        # 1. Render straight from the store: the import and the render are the check.
        store = db.connect()
        try:
            body = app.case_page(store, fixture.CASE)
        finally:
            store.close()
        if body is None:
            return _fail(f"app.case_page returned None for case {fixture.CASE!r}")
        html = body.decode("utf-8")
        missing = [heading for heading in fixture.SECTIONS if heading not in html]
        if missing:
            return _fail(f"the rendered page is missing {missing}")
        print(f"rendered {len(body)} bytes from the store; all six sections present")

        # 2. Serve it: the handler is the code a browser talks to, and a 500 here is what a
        #    compile-only guard would have let through.
        httpd = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{port}/case/{urllib.parse.quote(fixture.CASE)}"
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                status, served = response.status, response.read().decode("utf-8")
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=10)

        if status != 200:
            return _fail(f"GET {url} returned {status}")
        missing = [heading for heading in fixture.SECTIONS if heading not in served]
        if missing:
            return _fail(f"the served page is missing {missing}")
        if not served.startswith("<!doctype html>"):
            return _fail("the served page is not the app's HTML document")
        if "features/panel_api.feature" not in served:
            return _fail("the served page does not show the fixture's assertion coordinates")
        print(f"served {url} -> {status}, {len(served.encode('utf-8'))} bytes; "
              f"all six sections present")

    print("OK: app imported, case page rendered from the store fixture, and served over HTTP")
    return 0


if __name__ == "__main__":
    sys.exit(main())
