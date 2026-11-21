"""Deterministic duplication analysis.

The question: does more than one test assert the same claim, and if so, is the copy at the expensive level
adding anything? A copy that reaches the UI to assert what the API already asserts adds a mechanism, not a
claim — and it costs maintenance forever.

No model is involved. This runs in CI and can fail a build.
"""
from __future__ import annotations

from collections import defaultdict

from ..extract import gherkin, stepbindings
from .base import Claim, Evidence

name = "duplication"
version = "1.0.0"
uses_model = False


def _scenario_ref(feature_path: str, scenario: gherkin.Scenario) -> str:
    return f"scenario:{feature_path}#{scenario.name}"


def _suite(path: str) -> str:
    """Top-level project segment of a spec path, e.g. 'ReqOverflow.Specs.API'."""
    head = path.split("/", 1)[0]
    return head


def analyse(features: list[gherkin.Feature], bindings: list[stepbindings.Binding],
            uri_for_path) -> list[Claim]:
    """Group scenarios by normalised step signature and judge the surplus copies."""
    groups: dict[str, list[tuple[gherkin.Feature, gherkin.Scenario, str]]] = defaultdict(list)

    # Each suite defines its own step bindings for the same step text. Matching globally meant every step
    # resolved to whichever suite happened to be parsed first, which collapsed the layering entirely.
    by_suite: dict[str, list[stepbindings.Binding]] = defaultdict(list)
    for b in bindings:
        by_suite[_suite(b.path)].append(b)

    for feat in features:
        suite_bindings = by_suite.get(_suite(feat.path)) or bindings
        for sc in feat.scenarios:
            if not sc.steps:
                continue
            layers = []
            for step in sc.steps:
                b = stepbindings.match_step(suite_bindings, step.text)
                if b:
                    layers.append(b.layer)
            layer = stepbindings.highest(layers) if layers else "unknown"
            groups[sc.signature].append((feat, sc, layer))

    claims: list[Claim] = []
    for signature, members in groups.items():
        if len(members) < 2:
            continue
        layers = {m[2] for m in members}
        known = {l for l in layers if l != "unknown"}

        if len(known) > 1:
            cheapest = min(known, key=stepbindings.LAYER_ORDER.index)
            seen_at_cheapest = 0
            for feat, sc, layer in members:
                if layer != cheapest:
                    others = [m for m in members if m[2] == cheapest]
                    claims.append(Claim(
                        subject_ref=_scenario_ref(feat.path, sc),
                        statement=(f"asserts the same claim as {len(others)} cheaper copy(ies) at "
                                   f"{cheapest}; this copy drives {layer}"),
                        verdict="duplicate",
                        confidence=0.9,
                        evidence=[Evidence(uri=uri_for_path(feat.path), line=sc.line,
                                           note=f"{sc.name} ({layer})")]
                                 + [Evidence(uri=uri_for_path(o[0].path), line=o[1].line,
                                             note=f"{o[1].name} ({cheapest})") for o in others],
                        detail={"signature": signature, "layer": layer, "cheapest": cheapest,
                                "group_size": len(members)},
                    ))
                else:
                    # A repeat *at* the cheapest layer is waste too, and the earlier code dropped it
                    # entirely because it looked like "the copy that earns its place".
                    seen_at_cheapest += 1
                    if seen_at_cheapest > 1:
                        first = next(m for m in members if m[2] == cheapest)
                        claims.append(Claim(
                            subject_ref=_scenario_ref(feat.path, sc),
                            statement=f"repeats {first[1].name!r} at the same level ({cheapest})",
                            verdict="duplicate",
                            confidence=0.85,
                            evidence=[Evidence(uri=uri_for_path(feat.path), line=sc.line, note=sc.name),
                                      Evidence(uri=uri_for_path(first[0].path), line=first[1].line,
                                               note=first[1].name)],
                            detail={"signature": signature, "layer": layer, "intra_level": True},
                        ))
        elif len(members) > 1:
            # Same level, same steps: duplication inside one layer. Still waste, different fix.
            for feat, sc, layer in members[1:]:
                first = members[0]
                claims.append(Claim(
                    subject_ref=_scenario_ref(feat.path, sc),
                    statement=f"duplicates {first[1].name!r} at the same level ({layer})",
                    verdict="duplicate",
                    confidence=0.85,
                    evidence=[Evidence(uri=uri_for_path(feat.path), line=sc.line, note=sc.name),
                              Evidence(uri=uri_for_path(first[0].path), line=first[1].line,
                                       note=first[1].name)],
                    detail={"signature": signature, "layer": layer, "intra_level": True},
                ))
    return claims
