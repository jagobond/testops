"""Read a Java source file: the HTTP routes it declares, and what each one claims.

TESTOPS-70. The surface reader parsed Python only, so a Java/Spring product was honest but useless:
the run said *not assessable* and could not compare a test against the thing it tests.

This is a reader, not a scraper. It lexes the file first - comments, string literals, character
literals and text blocks are consumed as such - and only then walks the token stream for type
declarations and their members. That distinction is load-bearing: ``@GetMapping("/fake")`` inside a
comment, or ``"/@GetMapping"`` inside a string, is not a route, and a regex over the raw text would
report it as one. The parser understands the two things Spring puts a route in:

  * a mapping annotation on a method - ``@GetMapping``, ``@PostMapping``, ``@PutMapping``,
    ``@PatchMapping``, ``@DeleteMapping``, and ``@RequestMapping`` with ``value``/``path`` and
    ``method``;
  * a class-level ``@RequestMapping("/booking")``, which prefixes every mapping below it.

It does not compile Java, and does not claim to: it reads the declarations this question depends on
and reports routes, never types, and never anything it could not lex.

TESTOPS-74. Two shapes this reader used to get silently wrong, both a wrong answer that looks like a
right one:

  * a class that extends a base controller, or implements an interface, carrying the
    ``@RequestMapping`` prefix (Spring honours both). Dropping the prefix turns
    ``GET /booking/{id}`` into ``GET /{id}`` - a route that does not exist, presented as one that
    does. The reader now records the types it saw (``Reading.superclass``, ``Reading.interfaces``)
    and leaves the prefix to its caller, which can read them in the same repository; when the caller
    cannot, the mapping is *unread* and says so, naming the type. This file never guesses a prefix.
  * a mapping path that is not a string literal, e.g. ``@GetMapping(Paths.BOOKING)``. The old reader
    found no string, fell back to ``/`` and invented a route at the root of the service. A path this
    reader cannot resolve is now *unread*, with a reason naming the expression, and produces no
    surface at all.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

TYPE_KEYWORDS = {"class", "interface", "enum", "record"}

# Annotation simple name -> the HTTP method it pins. @RequestMapping has no fixed method.
MAPPINGS = {"GetMapping": "GET", "PostMapping": "POST", "PutMapping": "PUT",
            "PatchMapping": "PATCH", "DeleteMapping": "DELETE", "RequestMapping": ""}

# What a @RequestMapping with no ``method`` attribute matches: Spring's default, not a guess.
ANY = "ANY"

_WORD = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "0": "\0",
            '"': '"', "'": "'", "\\": "\\"}


@dataclass(frozen=True)
class Route:
    """One HTTP route a method declares, and what that method says it does."""
    verb: str
    path: str
    claims: tuple[str, ...]
    method: str
    source: str


@dataclass(frozen=True)
class Unread:
    """One mapping declaration this reader could not turn into a route, and why.

    ``reason`` is the sentence the run page groups by (``path is a constant``); ``detail`` names the
    thing a reader needs to check the reason against - the expression, or the superclass.
    """
    source: str
    method: str
    reason: str
    detail: str = ""

    def record(self) -> dict:
        return {"source": self.source, "method": self.method,
                "reason": self.reason, "detail": self.detail}


@dataclass(frozen=True)
class Reading:
    """What one file declared: its routes, what could not be read, and what the caller must resolve.

    ``own_prefix`` is ``None`` when the type declares no class-level ``@RequestMapping``; a tuple when
    it does. ``superclass`` is the type it ``extends`` (as written), and ``interfaces`` the types a
    class ``implements``: Spring honours a class-level ``@RequestMapping`` on either, so the caller
    may read them in the same repository to recover an inherited prefix. ``class_problem`` is set
    when the type's own prefix could not be read as a literal, so no method under it can be placed.
    """
    type_name: str | None
    superclass: str | None
    own_prefix: tuple[str, ...] | None
    routes: tuple[Route, ...]
    unread: tuple[Unread, ...] = ()
    class_problem: tuple[str, str] | None = None
    interfaces: tuple[str, ...] = ()


# Why a mapping is unread. Fixed wording, grouped on the run page (TESTOPS-74 AC3).
REASON_PATH_CONSTANT = "path is a constant"
REASON_CLASS_PATH_CONSTANT = "class prefix is a constant"
REASON_PREFIX_NOT_READ = "class prefix is inherited and its superclass was not read"


@dataclass(frozen=True)
class _Token:
    kind: str       # word | string | symbol | doc
    value: str
    start: int


@dataclass(frozen=True)
class _Annotation:
    name: str                          # simple name, fully-qualified input stripped
    args: dict[str, tuple[_Token, ...]] = field(default_factory=dict)


# --------------------------------------------------------------------------- lexing

def _unquote(body: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(body):
        char = body[index]
        if char == "\\" and index + 1 < len(body):
            following = body[index + 1]
            if following == "u" and index + 5 < len(body) + 1:
                try:
                    out.append(chr(int(body[index + 2:index + 6], 16)))
                    index += 6
                    continue
                except ValueError:
                    pass
            out.append(_ESCAPES.get(following, following))
            index += 2
            continue
        out.append(char)
        index += 1
    return "".join(out)


def lex(text: str) -> list[_Token]:
    """Tokens with comments and literals consumed, so structure is read and only structure."""
    tokens: list[_Token] = []
    index, size = 0, len(text)
    while index < size:
        char = text[index]
        if char in " \t\r\n\f":
            index += 1
        elif text.startswith("//", index):
            newline = text.find("\n", index)
            index = size if newline < 0 else newline
        elif text.startswith("/*", index):
            close = text.find("*/", index + 2)
            end = size if close < 0 else close + 2
            if text.startswith("/**", index) and close >= 0:
                tokens.append(_Token("doc", text[index + 3:close], index))
            index = end
        elif text.startswith('"""', index):
            close = text.find('"""', index + 3)
            end = size if close < 0 else close + 3
            tokens.append(_Token("string", text[index + 3:(close if close >= 0 else size)], index))
            index = end
        elif char == '"':
            cursor, body = index + 1, []
            while cursor < size:
                if text[cursor] == "\\" and cursor + 1 < size:
                    body.append(text[cursor:cursor + 2])
                    cursor += 2
                    continue
                if text[cursor] == '"':
                    cursor += 1
                    break
                body.append(text[cursor])
                cursor += 1
            tokens.append(_Token("string", _unquote("".join(body)), index))
            index = cursor
        elif char == "'":
            cursor = index + 1
            while cursor < size:
                if text[cursor] == "\\":
                    cursor += 2
                    continue
                if text[cursor] == "'":
                    cursor += 1
                    break
                cursor += 1
            index = cursor
        else:
            match = _WORD.match(text, index)
            if match:
                tokens.append(_Token("word", match.group(0), index))
                index = match.end()
            else:
                tokens.append(_Token("symbol", char, index))
                index += 1
    return tokens


# --------------------------------------------------------------------------- annotation arguments

def _close(tokens: list[_Token], index: int, opening: str, closing: str) -> int:
    """Index just past the delimiter matching ``tokens[index] == opening``."""
    depth = 0
    while index < len(tokens):
        token = tokens[index]
        if token.kind == "symbol":
            if token.value == opening:
                depth += 1
            elif token.value == closing:
                depth -= 1
                if depth == 0:
                    return index + 1
        index += 1
    return len(tokens)


def _split(tokens: tuple[_Token, ...], separator: str) -> list[tuple[_Token, ...]]:
    parts: list[tuple[_Token, ...]] = []
    current: list[_Token] = []
    depth = 0
    for token in tokens:
        if token.kind == "symbol":
            if token.value in "({[":
                depth += 1
            elif token.value in ")}]":
                depth -= 1
            elif token.value == separator and depth == 0:
                parts.append(tuple(current))
                current = []
                continue
        current.append(token)
    parts.append(tuple(current))
    return parts


def _arguments(tokens: tuple[_Token, ...]) -> dict[str, tuple[_Token, ...]]:
    """``value = "/x"``, ``{"/a", "/b"}`` and a bare positional string, all read the same way."""
    args: dict[str, tuple[_Token, ...]] = {}
    positional: list[_Token] = []
    for part in _split(tokens, ","):
        if not part:
            continue
        if part[0].kind == "word" and len(part) > 1 and part[1].value == "=":
            args[part[0].value] = part[2:]
        else:
            positional.extend(part)
    if positional:
        args[""] = tuple(positional)
    return args


def _strings(tokens: tuple[_Token, ...]) -> list[str]:
    return [token.value for token in tokens if token.kind == "string"]


def _expression(tokens: tuple[_Token, ...]) -> str:
    """The tokens as the source wrote them, close enough to name the expression in a reason."""
    out = ""
    for token in tokens:
        piece = f'"{token.value}"' if token.kind == "string" else token.value
        if out and piece != "." and not out.endswith("."):
            out += " "
        out += piece
    return out


def _elements(tokens: tuple[_Token, ...]) -> list[tuple[_Token, ...]]:
    """The path arguments: one bare expression, or the members of an array initialiser."""
    body = tokens
    if body and body[0].value == "{" and body[-1].value == "}":
        body = body[1:-1]
    return [part for part in _split(tuple(body), ",") if part]


def _path_argument(annotation: _Annotation) -> tuple[list[str], str] | None:
    """The literal paths a mapping names, or the expression it names instead of one.

    Returns ``None`` when the annotation gives no path at all (``@PostMapping``, or
    ``@RequestMapping(method = GET)``), a list when every element is a string literal, and an empty
    list plus the expression's text when it is not. An empty list is never a route at ``/``.
    """
    for key in ("value", "path", ""):
        if key in annotation.args:
            elements = _elements(annotation.args[key])
            if elements and all(len(element) == 1 and element[0].kind == "string"
                                for element in elements):
                return [element[0].value for element in elements], ""
            return [], _expression(annotation.args[key])
    return None


def _extends(header: tuple[_Token, ...]) -> str | None:
    """The type a class header extends, as written (``com.example.BaseController``)."""
    for index, token in enumerate(header):
        if token.kind != "word" or token.value != "extends":
            continue
        parts: list[str] = []
        for following in header[index + 1:]:
            if following.kind == "word" and following.value == "implements":
                break
            if following.kind == "word":
                parts.append(following.value)
            elif following.kind == "symbol" and following.value == ".":
                parts.append(".")
            else:
                break
        name = "".join(parts).strip(".")
        return name or None
    return None


def _implements(header: tuple[_Token, ...]) -> tuple[str, ...]:
    """The types a class header implements, as written, in order (``[BookingApi, Audited]``).

    Spring serves a class-level ``@RequestMapping`` declared on an interface the controller
    implements, so these types matter to the caller exactly as much as ``extends`` does. Generic
    arguments are skipped (the name is what identifies the type); the list ends at anything that is
    not a name, a dot, a comma, or a generic bracket.
    """
    for index, token in enumerate(header):
        if token.kind != "word" or token.value != "implements":
            continue
        names: list[str] = []
        parts: list[str] = []
        depth = 0
        for following in header[index + 1:]:
            if following.kind == "symbol" and following.value == "<":
                depth += 1
                continue
            if following.kind == "symbol" and following.value == ">":
                depth = max(depth - 1, 0)
                continue
            if depth:
                continue
            if following.kind == "word":
                parts.append(following.value)
            elif following.kind == "symbol" and following.value == ".":
                parts.append(".")
            elif following.kind == "symbol" and following.value == ",":
                name = "".join(parts).strip(".")
                if name:
                    names.append(name)
                parts = []
            else:
                break
        name = "".join(parts).strip(".")
        if name:
            names.append(name)
        return tuple(names)
    return ()


def _verbs(tokens: tuple[_Token, ...]) -> list[str]:
    """``RequestMethod.GET`` and ``{RequestMethod.GET, RequestMethod.POST}`` -> ``["GET", ...]``."""
    out: list[str] = []
    for index, token in enumerate(tokens):
        if token.kind != "word":
            continue
        qualified = index > 0 and tokens[index - 1].value == "."
        if qualified or token.value.upper() in ("GET", "POST", "PUT", "PATCH", "DELETE",
                                                "HEAD", "OPTIONS", "TRACE"):
            value = token.value.upper()
            if value in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE"):
                out.append(value)
    return out


# --------------------------------------------------------------------------- parsing

class _Parser:
    def __init__(self, tokens: list[_Token], source: str,
                 inherited: tuple[str, ...] | None = None,
                 unresolved: tuple[str, str] | None = None):
        self.tokens = tokens
        self.source = source
        self.inherited = inherited          # a superclass prefix, read by the caller
        self.unresolved = unresolved        # (reason, detail) when it could not be
        self.index = 0
        self.routes: list[Route] = []
        self.unread: list[Unread] = []
        self.type_name: str | None = None
        self.superclass: str | None = None
        self.interfaces: tuple[str, ...] = ()
        self.own_prefix: tuple[str, ...] | None = None
        self.class_problem: tuple[str, str] | None = None

    # -- token helpers

    def _at(self, value: str, kind: str | None = None) -> bool:
        if self.index >= len(self.tokens):
            return False
        token = self.tokens[self.index]
        return token.value == value and (kind is None or token.kind == kind)

    def _annotation(self) -> _Annotation | None:
        self.index += 1                                   # '@'
        parts: list[str] = []
        while self.index < len(self.tokens) and self.tokens[self.index].kind == "word":
            parts.append(self.tokens[self.index].value)
            self.index += 1
            if self._at("."):
                self.index += 1
                continue
            break
        if not parts:
            return None
        args: dict[str, tuple[_Token, ...]] = {}
        if self._at("("):
            end = _close(self.tokens, self.index, "(", ")")
            args = _arguments(tuple(self.tokens[self.index + 1:end - 1]))
            self.index = end
        return _Annotation(parts[-1], args)

    # -- structure

    def parse(self) -> Reading:
        self._scope(depth=0, prefixes=(), unresolved=self.unresolved)
        return Reading(self.type_name, self.superclass, self.own_prefix,
                       tuple(self.routes), tuple(self.unread), self.class_problem,
                       self.interfaces)

    def _scope(self, depth: int, prefixes: tuple[str, ...],
               unresolved: tuple[str, str] | None) -> None:
        """Walk declarations until the scope's closing brace (or the end of the file)."""
        doc: str | None = None
        annotations: list[_Annotation] = []
        while self.index < len(self.tokens):
            token = self.tokens[self.index]
            if token.kind == "symbol" and token.value == "}":
                self.index += 1
                return
            if token.kind == "doc":
                doc = token.value
                self.index += 1
                continue
            if token.kind == "symbol" and token.value == "@":
                annotation = self._annotation()
                if annotation is not None:
                    annotations.append(annotation)
                continue
            if token.kind == "word" and (token.value in TYPE_KEYWORDS or self._type_ahead()):
                keyword = self.index if token.value in TYPE_KEYWORDS else self._type_ahead()
                kind = self.tokens[keyword].value
                self.index = keyword + 1
                header: list[_Token] = []
                while self.index < len(self.tokens) and not self._at("{") and not self._at(";"):
                    header.append(self.tokens[self.index])
                    self.index += 1
                name = header[0].value if header and header[0].kind == "word" else None
                extends = _extends(tuple(header)) if kind in ("class", "interface") else None
                implements = _implements(tuple(header)) if kind == "class" else ()
                child_prefixes, child_unresolved = self._type_prefixes(
                    depth, prefixes, annotations, unresolved)
                if depth == 0:
                    self.type_name, self.superclass = name, extends
                    self.interfaces = implements
                if self._at("{"):
                    self.index += 1
                    self._scope(depth + 1, child_prefixes, child_unresolved)
                elif self._at(";"):
                    self.index += 1
                doc, annotations = None, []
                continue
            self._member(prefixes, unresolved, doc, annotations)
            doc, annotations = None, []

    def _type_prefixes(self, depth: int, prefixes: tuple[str, ...],
                       annotations: list[_Annotation],
                       unresolved: tuple[str, str] | None
                       ) -> tuple[tuple[str, ...], tuple[str, str] | None]:
        """The prefix methods under this type carry, and the reason when there is none to carry.

        The prefix is the type's own ``@RequestMapping`` when it has one. A type with none inherits
        its superclass's - but only the caller can read that superclass, so at the top level this
        returns *no* prefix and the caller re-reads the file with ``inherited`` or ``unresolved``.
        """
        own: tuple[str, ...] | None = None
        problem: tuple[str, str] | None = None
        for annotation in annotations:
            if annotation.name != "RequestMapping":
                continue
            found = _path_argument(annotation)
            if found is None:
                own = ("",)
            else:
                paths, expression = found
                if paths:
                    own = tuple(paths)
                else:
                    problem = (REASON_CLASS_PATH_CONSTANT, expression)
            break
        if depth > 0:
            if problem is not None:
                return (), problem
            return (own if own is not None else prefixes), None
        self.own_prefix, self.class_problem = own, problem
        if own is not None:
            return own, None
        if problem is not None:
            return (), problem
        if unresolved is not None:
            return (), unresolved
        return self.inherited or (), None

    def _type_ahead(self) -> int:
        """Index of a type keyword this declaration carries, past its modifiers; 0 when there is none.

        ``public final class X`` declares a type just as ``class X`` does: the modifiers sit in front
        of the keyword, so the scope looks through them rather than mistaking the declaration for a
        field and skipping its body unread.
        """
        index = self.index
        while index < len(self.tokens) and self.tokens[index].kind == "word":
            if self.tokens[index].value in TYPE_KEYWORDS:
                return index
            index += 1
        return 0

    def _member(self, prefixes: tuple[str, ...], unresolved: tuple[str, str] | None,
                doc: str | None, annotations: list[_Annotation]) -> None:
        """One declaration: a method (read for its route and its claim), or something to skip."""
        declared: str | None = None      # the identifier immediately before the parameter list
        while self.index < len(self.tokens):
            token = self.tokens[self.index]
            if token.kind == "symbol" and token.value == "(":
                previous = self.tokens[self.index - 1] if self.index else None
                if declared is None and previous is not None and previous.kind == "word":
                    declared = previous.value
                self.index = _close(self.tokens, self.index, "(", ")")
                continue
            if token.kind == "symbol" and token.value == "{":
                self.index = _close(self.tokens, self.index, "{", "}")
                if declared is not None:
                    self._routes(declared, prefixes, unresolved, doc, annotations)
                return
            if token.kind == "symbol" and token.value == ";":
                self.index += 1
                if declared is not None:
                    self._routes(declared, prefixes, unresolved, doc, annotations)
                return                    # a field, an import, or an abstract/interface method
            if token.kind == "symbol" and token.value == "}":
                return                    # let the enclosing scope consume it
            self.index += 1

    # -- routes and claims

    def _routes(self, name: str, prefixes: tuple[str, ...],
                unresolved: tuple[str, str] | None, doc: str | None,
                annotations: list[_Annotation]) -> None:
        mapping = next((annotation for annotation in annotations if annotation.name in MAPPINGS), None)
        if mapping is None:
            return                        # a method, not a surface: it exposes nothing
        # A prefix this file cannot supply makes the mapping unreadable, not routeless: emitting it
        # at the method path would report a route the class does not serve (TESTOPS-74 AC1).
        if unresolved is not None:
            self.unread.append(Unread(self.source, name, unresolved[0], unresolved[1]))
            return
        found = _path_argument(mapping)
        paths: list[str]
        if found is None:
            paths = [""]                  # no path argument is a mapping at the class prefix itself
        else:
            paths, expression = found
            if not paths:
                # A path this reader cannot resolve is unread, never a route at ``/`` (AC2).
                self.unread.append(Unread(self.source, name, REASON_PATH_CONSTANT, expression))
                return
        claims = self._claims(name, doc, annotations)
        verbs = [MAPPINGS[mapping.name]] if MAPPINGS[mapping.name] else (
            _verbs(mapping.args.get("method", ())) or [ANY])
        for prefix in prefixes or ("",):
            for path in paths:
                for verb in verbs:
                    self.routes.append(Route(verb, _join(prefix, path), tuple(claims), name,
                                             self.source))

    @staticmethod
    def _claims(name: str, doc: str | None, annotations: list[_Annotation]) -> list[str]:
        """What the code says it does, in order: a summary, the Javadoc, then the method's name."""
        for annotation in annotations:
            if annotation.name == "Operation":
                summary = _strings(annotation.args.get("summary", ()))
                if summary:
                    return [first_sentence(summary[0])]
        sentence = first_sentence(_javadoc_text(doc or ""))
        if sentence:
            return [sentence]
        humanised = _humanise(name)
        return [humanised] if humanised else []


# --------------------------------------------------------------------------- prose

def _join(prefix: str, path: str) -> str:
    """``/booking`` + ``/`` is ``/booking``; ``/booking`` + ``/{id}`` is ``/booking/{id}``."""
    prefix = (prefix or "").rstrip("/")
    path = path or ""
    if not prefix:
        return path if path.startswith("/") else f"/{path}" if path else "/"
    if path in ("", "/"):
        return prefix
    return prefix + (path if path.startswith("/") else f"/{path}")


def _javadoc_text(raw: str) -> str:
    """The prose of a Javadoc comment: leading asterisks gone, block tags and their text dropped."""
    lines: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("*"):
            line = line[1:].strip()
        if line.startswith("@"):
            break
        if line:
            lines.append(line)
    return " ".join(lines)


def first_sentence(text: str) -> str:
    """The first sentence of a paragraph, whitespace collapsed."""
    text = " ".join(text.split())
    for stop in (". ", "; "):
        if stop in text:
            return text.split(stop)[0].strip()
    return text.strip()


def _humanise(name: str) -> str:
    """``getBooking`` -> ``get booking``: a method name said as words, not as an identifier."""
    return " ".join(_CAMEL.sub(" ", name).replace("_", " ").split()).lower()


def read(text: str, source: str = "", *,
         inherited: tuple[str, ...] | None = None,
         unresolved: tuple[str, str] | None = None) -> Reading | None:
    """Everything this file declares, or ``None`` when it could not be lexed as Java.

    ``None`` is not an empty reading: a file whose delimiters do not balance was not read, and the
    caller must not count it as a file that was read and held nothing.

    ``inherited`` is a class-level prefix the *caller* read from this file's superclass in the same
    repository; ``unresolved`` is the reason it could not. Both exist for one level of inheritance,
    which is the depth this reader can see without pretending to compile the project.
    """
    tokens = lex(text)
    depth = 0
    for token in tokens:
        if token.kind != "symbol":
            continue
        if token.value in "({[":
            depth += 1
        elif token.value in ")}]":
            depth -= 1
            if depth < 0:
                return None
    if depth != 0:
        return None
    return _Parser(tokens, source, inherited, unresolved).parse()


def routes(text: str, source: str = "") -> list[Route] | None:
    """The routes this file declares on its own, with no inherited prefix applied.

    A convenience for callers that only want the routes; :func:`read` is the honest reading, because
    it also says which declarations could not be placed and which superclass the caller must look at.
    """
    reading = read(text, source)
    return None if reading is None else list(reading.routes)
