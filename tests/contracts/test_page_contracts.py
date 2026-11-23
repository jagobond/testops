"""
TESTOPS-7 page-contract suite.

Independent, black-box suite written from brief/page-contracts.md only. It drives
the running server over HTTP with urllib (requests is not installed in the target
venv) and never imports the application.

Every test names the promise (P1..P24) it verifies. Presentation details the
brief puts out of scope (colour, spacing, fonts, exact wording) are not pinned;
where a promise is about *looking* different, the assertion is on structural
distinguishability (e.g. whether two verdicts share a styling marker), not on a
particular colour.

Run:
    C:/Users/Chester/Projects/testops/.venv/Scripts/python.exe -m pytest tests -v

The suite starts and owns the server it talks to (TESTOPS-53): ``conftest.py`` launches the product
in a child process on a port the kernel chooses, over a disposable store built under a temp
directory discovered from the OS (not from ``TMPDIR``; TESTOPS-58 skips when that variable points
into the repository, the home directory or a checkout's ``data/``). There is no base URL to
configure and no environment variable that can point it at another deployment; a run that cannot
start its own server skips and says why.
"""

import re
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request

import pytest

import harness


def base_url() -> str:
    """The address of the server this session started. There is no default: no server, no URL."""
    server = getattr(harness, "SERVER", None)
    assert server is not None, (
        "the contract server was not started, so there is no address to talk to. The suite does "
        "not fall back to a configured or live URL."
    )
    return server.base_url


# --------------------------------------------------------------------------
# Small HTTP + HTML helpers (stdlib only)
# --------------------------------------------------------------------------

def _request(path, data=None):
    """GET (data None) or form-encoded POST. Returns (status, body) for HTTP
    errors too, so a refusal page can be inspected instead of raised."""
    url = base_url() + path if path.startswith("/") else path
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        raise AssertionError(
            "Application under test is not reachable at %s (%r). "
            "The suite does not work around a down server." % (url, e.reason)
        )


def get(path):
    status, body = _request(path)
    assert status == 200, "GET %s returned HTTP %s" % (path, status)
    return body


def post(path, data):
    return _request(path, data)


def text(html):
    """Visible text: styles/scripts stripped, tags removed, whitespace collapsed."""
    h = re.sub(r"(?is)<style.*?</style>", " ", html)
    h = re.sub(r"(?is)<script.*?</script>", " ", h)
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    import html as _html
    h = _html.unescape(h)
    return re.sub(r"\s+", " ", h).strip()


def hrefs(html):
    return [m for m in re.findall(r'href="([^"]+)"', html)]


def run_links(runs_html):
    return [h for h in hrefs(runs_html) if re.match(r"^/run/[^/]+$", h)]


def _entries(html, kind):
    """(url, visible_text) for <li><a href="/kind/...">..</a></li> entries."""
    out = []
    for m in re.finditer(
        r'<li>\s*<a href="(/%s/[^"]+)"[^>]*>(.*?)</a>\s*</li>' % kind,
        html,
        re.S | re.I,
    ):
        out.append((m.group(1), text(m.group(2))))
    return out


def case_links(run_html):
    return [h for h in hrefs(run_html) if re.match(r"^/case/[^/]+$", h)]


def verdict_class(case_html):
    m = re.search(r'<strong class="(verdict[^"]*)">', case_html)
    return m.group(1) if m else None


def verdict_text(case_html):
    m = re.search(r'<strong class="verdict[^"]*">(.*?)</strong>', case_html)
    return text(m.group(1)) if m else None


# --------------------------------------------------------------------------
# Discovery fixtures (follow links, do not construct IDs)
# --------------------------------------------------------------------------

@pytest.fixture(scope="session")
def front(contract_server):
    return get("/")


@pytest.fixture(scope="session")
def runs(contract_server):
    return get("/runs")


@pytest.fixture(scope="session")
def run_urls(runs):
    urls = run_links(runs)
    assert urls, "The runs index linked to no run pages; P5 cannot be followed."
    return urls


@pytest.fixture(scope="session")
def first_run_html(run_urls):
    return get(run_urls[0])


@pytest.fixture(scope="session")
def first_case_url(first_run_html):
    cs = case_links(first_run_html)
    assert cs, "The run page linked to no case pages; P5 cannot be followed."
    return cs[0]


@pytest.fixture(scope="session")
def case_urls(run_urls):
    """Case links discovered by walking a handful of run pages."""
    out = []
    for u in run_urls[:12]:
        for c in case_links(get(u)):
            if c not in out:
                out.append(c)
    assert out, "No case pages were reachable from any run page."
    return out


# A disposable project for the config promises. Creating a project is the
# reader-level action P22 describes; there is no project-delete endpoint, so the
# slug is timestamped and a fresh one is made each run.
@pytest.fixture(scope="session")
def audit_project():
    slug = "contract-audit-" + time.strftime("%Y%m%d%H%M%S")
    status, body = post("/config/projects", {"slug": slug, "name": "Contract audit"})
    assert status == 200, "Adding a project returned HTTP %s, not a normal page" % status
    assert slug in get("/config"), "A project added through the config page did not appear on it"
    return slug


@pytest.fixture
def audit_service(audit_project):
    marker = "svc-" + uuid.uuid4().hex[:8]
    status, _ = post(
        "/config/services",
        {
            "project": audit_project,
            "type": "git_repo",
            "role": "test",
            "name": marker,
            "repo": "owner/keep",
            "board": "", "host": "", "org": "", "ado_project": "", "pipeline_id": "",
        },
    )
    assert status == 200, "Adding a service returned HTTP %s" % status
    cfg = get("/config")
    sid = None
    for m in re.finditer(r'<form method="post" action="/config/service/(\d+)">(.*?)</form>', cfg, re.S):
        if marker in m.group(2):
            sid = m.group(1)
            break
    assert sid, "A service added through the config page did not appear with an editable form"
    yield {"id": sid, "marker": marker, "project": audit_project}
    post("/config/service/%s/delete" % sid, {})  # best-effort cleanup


# --------------------------------------------------------------------------
# P1 — nothing is silent
# --------------------------------------------------------------------------

def test_P01_a_run_that_found_nothing_says_so(front, runs, run_urls):
    """P1: a page with nothing to show explains why; it is not blank or a bare 0."""
    # Find a no-findings run from the runs index (its entry says so in words).
    empty = [u for u, t in _entries(runs, "run") if re.search(r"\bno findings?\b", t, re.I)]
    assert empty, "No no-findings run in the store to check P1 against"
    page = text(get(empty[0]))
    assert len(page) > 200, "The no-findings run page is nearly blank"
    assert re.search(r"no findings?", page, re.I), "The run page does not say it found nothing"
    # It must give the reader a reason / next fact, not a lone zero.
    assert re.search(r"(run (itself )?is the record|so |because |created no case)", page, re.I), (
        "The page says 'no findings' but does not explain what that means for the reader"
    )


def test_P01_no_page_is_blank(front, runs, first_run_html, first_case_url):
    """P1: every reachable page carries content or an explicit explanation."""
    for name, page in [
        ("front", front),
        ("runs", runs),
        ("run", first_run_html),
        ("case", get(first_case_url)),
    ]:
        assert len(text(page)) > 80, "%s page is effectively blank" % name


# --------------------------------------------------------------------------
# P2 — a number says what it counts
# --------------------------------------------------------------------------

def test_P02_counts_carry_their_unit(front, runs, first_run_html):
    """P2: no bare numbers; every count names what it counts."""
    numeric_badges = []
    for page in (front, runs):
        for m in re.finditer(r'<span class="badge[^>]*>([^<]+)</span>', page):
            b = text(m.group(1))
            if re.match(r"^\d", b):
                numeric_badges.append(b)
    assert numeric_badges, "No numeric badges found to check"
    for b in numeric_badges:
        assert re.match(r"^\d+\s+[A-Za-z]", b), (
            "A count is shown without a unit noun: %r" % b
        )
    page = text(first_run_html)
    assert re.search(r"\d+\s+findings?\b", page, re.I), "Run header count does not say 'findings'"
    assert re.search(r"\d+\s+claims?\b", page, re.I), "Run count does not say 'claims'"


# --------------------------------------------------------------------------
# P3 — unread is never dressed as read
# --------------------------------------------------------------------------

def test_P03_unread_files_are_counted_and_named_on_the_page(first_run_html):
    """P3: files the tool could not open are stated on the page with a count and kind."""
    page = text(first_run_html)
    assert re.search(r"could not read|not read|could not be read", page, re.I), (
        "The run page never mentions files it could not read"
    )
    assert re.search(r"\d+\s+\.\w+\b", page), (
        "Unread files are not given by count and file kind (e.g. '142 .java')"
    )


# --------------------------------------------------------------------------
# P4 — certainty and uncertainty look different
# --------------------------------------------------------------------------

def test_P04_uncertain_verdict_is_not_styled_as_settled(case_urls):
    """P4: a conclusion the tool could not reach must not share the styling of a settled one."""
    uncertain = None
    settled = None
    for u in case_urls:
        h = get(u)
        vt = verdict_text(h)
        vc = verdict_class(h)
        if not vt or not vc:
            continue
        if re.search(r"cannot (assess|tell)|could not|unknown|unplaced", vt, re.I):
            uncertain = (u, vt, vc)
        elif re.search(r"checked|placed|settled|already asserted", vt, re.I):
            settled = (u, vt, vc)
        if uncertain and settled:
            break
    assert uncertain, "No case presenting an uncertain/undecided verdict was reachable"
    assert settled, "No case presenting a settled verdict was reachable"
    assert uncertain[2] != settled[2], (
        "An uncertain verdict (%r, class %r) is styled identically to a settled one "
        "(%r, class %r): 'Cannot tell' is dressed as settled (P4)."
        % (uncertain[1], uncertain[2], settled[1], settled[2])
    )


# --------------------------------------------------------------------------
# P5 — reachability, no dead ends
# --------------------------------------------------------------------------

def test_P05_front_reaches_run_and_run_reaches_case(front, runs, first_case_url):
    """P5: front page -> a run -> a case, all by following links."""
    assert any(re.match(r"^/run/", h) for h in hrefs(runs)), "Runs index links to no run"
    assert re.match(r"^/case/", first_case_url), "Run page does not link to its cases"


def test_P05_case_links_back_to_its_run(run_urls, case_urls):
    """P5: from a case a reader can get back to its run."""
    # Take a run page, take one of its cases, and require the case to link that run.
    run_html = get(run_urls[0])
    cs = case_links(run_html)
    assert cs, "No case links on the selected run page"
    case_html = get(cs[0])
    assert run_urls[0] in hrefs(case_html), (
        "The case page %s has no link back to its run %s; the only navigation is "
        "to / and /runs. A reader cannot return to the run they came from (P5)."
        % (cs[0], run_urls[0])
    )


def test_P05_config_page_is_reachable_from_the_front_page(front):
    """P5: no page that only exists if you already know its URL. The brief's
    config promises (P21..P24) imply a config page, so it must be linked."""
    seen, frontier = {"/"}, ["/"]
    found = set()
    for _depth in range(3):
        nxt = []
        for path in list(frontier)[:120]:
            try:
                h = get(path)
            except AssertionError:
                continue
            for link in hrefs(h):
                if not link.startswith("/"):
                    continue
                link = link.split("#")[0]
                found.add(link)
                if link not in seen:
                    seen.add(link)
                    nxt.append(link)
        frontier = nxt
    assert "/config" in found, (
        "No reachable page links to the configuration page (/config): it can only be "
        "reached by guessing the URL (P5). Reachable from the front page: %s"
        % sorted(found)
    )


# --------------------------------------------------------------------------
# P6 — a URL is stable enough to cite
# --------------------------------------------------------------------------

def test_P06_a_case_url_shows_the_same_thing_twice(first_case_url):
    """P6: pasting a case URL twice shows the same claim, verdict and evidence."""
    a = get(first_case_url)
    b = get(first_case_url)
    assert verdict_text(a) == verdict_text(b), "Verdict changed between two reads of the same URL"
    claim_re = r'<p class="wrong">(.*?)</p>'
    ca = re.search(claim_re, a, re.S)
    cb = re.search(claim_re, b, re.S)
    assert ca and cb and text(ca.group(1)) == text(cb.group(1)), (
        "The stated claim changed between two reads of the same case URL"
    )
    ev = r"blob/[0-9a-f]{7,40}/[^\"#]+#L\d+"
    assert re.findall(ev, a) == re.findall(ev, b), "Evidence links changed between two reads"


# --------------------------------------------------------------------------
# P7 — the front page says what the tool analyses and what exists
# --------------------------------------------------------------------------

def test_P07_front_page_states_what_analyses_and_how_much_exists(front):
    """P7: a newcomer sees what is analysed and how many projects, runs, cases exist."""
    page = text(front)
    assert re.search(r"\bprojects?\b", page, re.I), "Front page never says 'projects'"
    missing = [kind for kind in ("projects", "runs", "cases")
               if not re.search(r"\b\d+\s+%s?\b" % kind, page, re.I)]
    assert not missing, (
        "The front page does not state a count of %s. A newcomer is told what exists "
        "only by counting sections; P7 promises 'how many projects, runs, cases'." % missing
    )


# --------------------------------------------------------------------------
# P8 — runs are distinguishable at a glance
# --------------------------------------------------------------------------

def test_P08_two_runs_of_one_project_at_different_commits_are_tellable_apart(runs):
    """P8: project, repositories+commits, when, and how much found, per run."""
    entries = _entries(runs, "run")
    rb = [(u, t) for u, t in entries if "restfulbooker" in t.lower()]
    assert len(rb) >= 2, "Not enough restfulbooker runs to compare"
    commits = []
    for u, t in rb:
        for repo, sha in re.findall(r"([A-Za-z0-9_.-]+)@([0-9a-f]{7,40})", t):
            commits.append((repo, sha))
    distinct = sorted(set(commits))
    assert len({sha for _, sha in distinct}) >= 2, (
        "No two runs of one project at different commits are present to distinguish"
    )
    # Every restfulbooker entry must show a repository@commit, a time, and a finding count.
    for u, t in rb:
        assert re.search(r"@[0-9a-f]{7,40}", t), "Run entry %s shows no commit" % u
        assert re.search(r"\d+\s+findings?\b|\bno findings?\b", t, re.I), (
            "Run entry %s does not say how much it found" % u
        )


# --------------------------------------------------------------------------
# P9 — empty and failed runs are different things
# --------------------------------------------------------------------------

@pytest.mark.skip(reason="P9: the store contains no failed run (the runs index has "
                         "No findings / All decided / N findings, never a failure), so the "
                         "required contrast between a found-nothing run and a failed run "
                         "cannot be observed over HTTP. See factory-report.md (d).")
def test_P09_failed_and_empty_runs_are_distinguishable(runs):
    """P9: an empty run and a failed run must not look the same."""
    entries = _entries(runs, "run")
    failed = [t for _, t in entries if re.search(r"\bfailed?\b|\berror\b", t, re.I)]
    empty = [t for _, t in entries if re.search(r"\bno findings?\b", t, re.I)]
    assert failed and empty, "Need both a failed run and an empty run in the store"
    assert not set(failed) & set(empty), "A run is described as both empty and failed identically"


# --------------------------------------------------------------------------
# P10 — what was read, per repository, per kind, with explicit zeroes
# --------------------------------------------------------------------------

def test_P10_run_states_files_read_per_kind_including_explicit_zeroes(first_run_html):
    """P10: per repository, how many files of each kind were read, including zeroes."""
    page = text(first_run_html)
    assert re.search(r"\d+\s+files?\s+(?:were\s+)?read", page, re.I), (
        "The run page gives no 'N files read' statement per repository"
    )
    # The distinctive promise is the explicit zero: "0 product files".
    assert re.search(r"\b0\s+(?:product|test|[.\w-]+)\s+files?\b", page, re.I), (
        "The run page gives no explicit zero read-count per file kind (e.g. "
        "'0 product files'), so a reader cannot tell a kind that was read-and-empty "
        "from one that was never mentioned (P10)."
    )


# --------------------------------------------------------------------------
# P11 — what each repository was read as
# --------------------------------------------------------------------------

def test_P11_each_repository_says_what_it_was_read_as(first_run_html):
    """P11: name the recognised language/framework family, and say plainly when none."""
    page = text(first_run_html)
    assert len(re.findall(r"\bread as\b", page, re.I)) >= 2, (
        "The run page does not state, per repository, what it was read as"
    )
    assert re.search(r"no ecosystem|recognised none|none of the \d+ ecosystems", page, re.I), (
        "A repository the tool could not recognise is not said plainly to be unrecognised"
    )


# --------------------------------------------------------------------------
# P12 — what was skipped, by kind and count
# --------------------------------------------------------------------------

def test_P12_skipped_files_are_stated_by_kind_and_count(first_run_html):
    """P12: files not read, by kind and count, whenever they were skipped."""
    page = text(first_run_html)
    assert re.search(r"could not read|did not fetch|skipped", page, re.I), (
        "The page never says files were skipped"
    )
    assert re.search(r"\d+\s+\.\w+", page), "Skipped files are not counted by kind (e.g. '142 .java')"


# --------------------------------------------------------------------------
# P13 — what it placed and what it could not, with a reason
# --------------------------------------------------------------------------

def test_P13_placed_and_unplaced_are_stated_with_a_reason(first_run_html):
    """P13: what was placed, what could not be, and an actionable reason."""
    page = text(first_run_html)
    assert re.search(r"\bplaced\b", page, re.I), "The page never says what was placed"
    assert re.search(r"matched no|could not place|unplaced|not placed", page, re.I), (
        "The page never says what could not be placed"
    )
    assert re.search(r"\bbecause\b|so that|no binding matches", page, re.I), (
        "The page gives no reason a reader can act on for the unplaced items"
    )


# --------------------------------------------------------------------------
# P14 — no credit for analysis not performed
# --------------------------------------------------------------------------

@pytest.mark.skip(reason="P14: 'credit for analysis it did not perform' is an attribution "
                         "the page does not expose as a testable claim over HTTP; deciding "
                         "whether a finding was 'awarded credit' to an unread repository needs "
                         "the analysis model, not the rendered page. See factory-report.md (d).")
def test_P14_unanalysed_repository_gets_no_credit(first_run_html):
    """P14: never award a repository credit for analysis it did not perform."""
    ...


# --------------------------------------------------------------------------
# P15 — the claim, in the developer's words
# --------------------------------------------------------------------------

def test_P15_case_states_an_actionable_claim_naming_the_step(first_case_url):
    """P15: one sentence a developer can act on, naming the asserted step."""
    h = get(first_case_url)
    m = re.search(r'<p class="wrong">(.*?)</p>', h, re.S)
    assert m, "The case page has no claim statement"
    claim = text(m.group(1))
    assert re.search(r"assert|step", claim, re.I), (
        "The claim is not about an asserted step a developer would recognise: %r" % claim[:200]
    )
    act = re.search(r'<p class="action">(.*?)</p>', h, re.S)
    assert act and text(act.group(1)), "The case gives the developer no action to take"


# --------------------------------------------------------------------------
# P16 — verdict: word + context + what would change its mind
# --------------------------------------------------------------------------

def test_P16_verdict_has_context_and_states_what_settles_it(first_case_url):
    """P16: one-word-ish verdict plus context, including what evidence changes it."""
    h = get(first_case_url)
    assert verdict_text(h), "The case page shows no verdict"
    page = text(h)
    assert re.search(r"settle|would change|evidence", page, re.I), (
        "The verdict is not accompanied by what evidence would settle/change it"
    )


# --------------------------------------------------------------------------
# P17 — evidence is traceable
# --------------------------------------------------------------------------

def test_P17_evidence_names_repo_commit_file_and_line(first_case_url):
    """P17: repository, commit, file and line the reader would open."""
    h = get(first_case_url)
    m = re.search(r"https://[^\"]+/blob/[0-9a-f]{7,40}/[^\"#]+#L(\d+)", h)
    assert m, (
        "The case page links to no repository file at a specific commit and line"
    )
    page = text(h)
    assert re.search(r"\bcommit\b", page, re.I), "The page does not name the commit in words"
    assert re.search(r"[\w./-]+:\d+", page), "The page does not show a file:line for the evidence"


# --------------------------------------------------------------------------
# P18 — whether everything needed was readable
# --------------------------------------------------------------------------

def test_P18_partial_read_is_stated_on_the_case_page(case_urls):
    """P18: a conclusion drawn from a partial read says so on that page."""
    found = False
    for u in case_urls:
        page = text(get(u))
        if re.search(r"cannot assess|could not be read|could not read|not read", page, re.I):
            found = True
            assert re.search(r"\d+\s+\.\w+|code was not read|requirements", page, re.I), (
                "A case says it could not read something but gives no kind/detail"
            )
            break
    assert found, "No case page stated a partial read, though the corpus has unreadable repos"


# --------------------------------------------------------------------------
# P19 — record a decision, and what it covers
# --------------------------------------------------------------------------

def test_P19_decision_form_and_its_coverage_are_present(first_case_url):
    """P19: a way to record a decision, and a statement of what it covers later."""
    h = get(first_case_url)
    forms = re.findall(r'(?is)<form[^>]+action="([^"]*)"[^>]*>(.*?)</form>', h)
    decision = [(a, b) for a, b in forms if a.endswith("/state")]
    assert decision, "No decision form (an action ending /state) on the case page"
    action, body = decision[0]
    assert re.search(r'name="state"', body) and re.search(r'value="[a-z_]+"', body), (
        "The decision form offers no way to choose a state"
    )
    page = text(h)
    assert re.search(r"this case only|future runs|suppress", page, re.I), (
        "The page does not state what a decision will and will not cover on later runs"
    )


# --------------------------------------------------------------------------
# P20 — unplaced claim looks less settled
# --------------------------------------------------------------------------

def test_P20_unplaced_claims_are_rendered_with_the_soft_tone(first_run_html):
    """P20: a claim that could not be placed must look less settled, without a legend.

    P20 was skipped while unplaced claims were only a count. TESTOPS-57 gives them a section of
    their own on the run page, so the soft badge is now rendered on a served page. This asserts
    the section exists, that its count and its entries agree, and that every entry carries the
    soft badge - not the alarm red a placed finding wears.
    """
    page = first_run_html
    marker = "What this run could not place"
    assert marker in page, "the run page does not give unplaced claims a section of their own"
    section = page.split(marker, 1)[1].split("<h2", 1)[0]
    entries = re.findall(r'<li id="unplaced-\d+">', section)
    assert entries, "the unplaced section lists no entries"
    count = re.search(r"(\d+) steps? in this run (?:was|were) not assessed", text(section))
    assert count, "the unplaced section does not say how many claims it lists"
    assert int(count.group(1)) == len(entries), (
        f"the section says {count.group(1)} but lists {len(entries)} entries")
    assert "not assessed" in text(section).lower()
    assert "badge verdict soft" in section, "an unplaced entry does not wear the soft tone"
    assert "badge verdict hot" not in section, "an unplaced entry wears the alarm tone"
    assert "unsupported ecosystem" not in section.lower()
    assert "could not be tied to a layer" not in section.lower()
    assert "nearest declared patterns" in section.lower()


# --------------------------------------------------------------------------
# P21..P24 — the config page
# --------------------------------------------------------------------------

def test_P21_config_lists_projects_and_their_resources():
    """P21: which projects exist and which resources belong to each."""
    page = get("/config")
    body = text(page)
    assert "Projects and services" in body, "The config page has no projects/services listing"
    serviced = re.findall(r'<form method="post" action="/config/service/\d+">(.*?)</form>', page, re.S)
    assert serviced, "No project has any listed resource/service"
    # Each service form carries its project; every such project must be a known heading.
    projects = set(re.findall(r'name="project" value="([^"]+)"', page))
    assert projects, "Services are not grouped under projects"


def test_P22_project_and_service_can_be_added(audit_project, audit_service):
    """P22: adding a project and a resource needs no code change or restart."""
    page = get("/config")
    body = text(page)
    assert audit_project in page, "The added project is not listed after being added"
    assert audit_service["marker"] in page, "The added service is not listed after being added"
    assert re.search(r"Slug", body) and re.search(r"Name", body), (
        "The page does not say what adding a project needs (slug, name)"
    )
    assert re.search(r"Repository|Board key|Pipeline id", body), (
        "The page does not say what a service needs"
    )


def test_P23_credential_token_is_refused_with_a_reason(audit_service):
    """P23: a token-looking value is refused, and the reason does not blame the reader."""
    status, body = post(
        "/config/service/%s" % audit_service["id"],
        {
            "project": audit_service["project"],
            "type": "git_repo", "role": "test",
            "name": audit_service["marker"],
            "repo": "ghp_1234567890abcdefghijklmnopqrstuvwx",  # a GitHub token prefix
            "board": "", "host": "", "org": "", "ado_project": "", "pipeline_id": "",
        },
    )
    assert status == 400, (
        "A GitHub-token-looking value in a settings field was accepted (HTTP %s)" % status
    )
    refusal = text(body)
    assert re.search(r"credential|token|password|key", refusal, re.I), (
        "The refusal does not say why the value was refused"
    )
    # The refused value must not have been stored.
    assert "ghp_1234567890abcdefghijklmnopqrstuvwx" not in get("/config"), (
        "The refused credential appears in the stored configuration"
    )


def test_P23_password_looking_value_is_refused(audit_service):
    """P23: a value that looks like a password is refused ('a token, a key, a password')."""
    status, body = post(
        "/config/service/%s" % audit_service["id"],
        {
            "project": audit_service["project"],
            "type": "git_repo", "role": "test",
            "name": audit_service["marker"],
            "repo": "password=hunter2",
            "board": "", "host": "", "org": "", "ado_project": "", "pipeline_id": "",
        },
    )
    assert status == 400, (
        "A password-looking value (repo='password=hunter2') was accepted and stored "
        "(HTTP %s). P23 promises refusal of 'a token, a key, a password'." % status
    )


def test_P23_password_in_free_text_field_is_refused(audit_service):
    """P23: a password-looking value must be refused wherever it is entered, not only
    in a field with its own format validation (the repo field rejects 'password'
    partly as a coordinate check; the free-text Name field is stored verbatim)."""
    status, body = post(
        "/config/service/%s" % audit_service["id"],
        {
            "project": audit_service["project"],
            "type": "git_repo", "role": "test",
            "name": "password=hunter2",  # free-text display name, no format of its own
            "repo": "owner/keep",
            "board": "", "host": "", "org": "", "ado_project": "", "pipeline_id": "",
        },
    )
    if status == 200:
        stored = get("/config")
        assert "password=hunter2" not in stored, (
            "A password-looking value ('password=hunter2') was accepted and stored "
            "verbatim in the free-text Name field (HTTP 200). P23 promises to refuse "
            "anything that looks like a password."
        )
    assert status == 400, (
        "A password-looking value ('password=hunter2') entered in the free-text Name "
        "field was accepted and shown as stored configuration (HTTP %s). P23 promises "
        "to refuse anything that looks like a password." % status
    )
    refusal = text(body)
    assert re.search(r"credential|token|password|key", refusal, re.I), (
        "The refusal does not say why the value was refused"
    )


def test_P24_editing_one_field_does_not_blank_another(audit_service):
    """P24: changing one thing does not silently blank another."""
    sid = audit_service["id"]
    # Establish two known values through the form a reader uses.
    base = {
        "project": audit_service["project"], "type": "git_repo", "role": "test",
        "name": audit_service["marker"], "repo": "owner/keep",
        "board": "", "host": "", "org": "", "ado_project": "", "pipeline_id": "",
    }
    status, _ = post("/config/service/%s" % sid, base)
    assert status == 200, "Setting the service's baseline values failed (HTTP %s)" % status
    # Change only the name, resending the rest as the rendered form does.
    edited = dict(base)
    edited["name"] = audit_service["marker"] + "-renamed"
    status, _ = post("/config/service/%s" % sid, edited)
    assert status == 200, "Editing the service name failed (HTTP %s)" % status
    cfg = get("/config")
    block = None
    for m in re.finditer(r'<form method="post" action="/config/service/%s">(.*?)</form>' % sid, cfg, re.S):
        block = m.group(1)
    assert block, "The edited service is no longer shown"
    repo = re.search(r'name="repo"[^>]*value="([^"]*)"', block)
    name = re.search(r'name="name"[^>]*value="([^"]*)"', block)
    assert name and name.group(1) == edited["name"], "The name change was not stored"
    assert repo and repo.group(1) == "owner/keep", (
        "Editing the name silently blanked the repository (%r)" % (repo.group(1) if repo else None)
    )
