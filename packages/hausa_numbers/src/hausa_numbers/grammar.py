"""Automate fini compact pour le decodage contraint de nombres hausa."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType

from .expressions import HAUSA_OPERATORS, parse_expression, render_expression
from .generator import SCALES, generate
from .loader import Lexicon, load_lexicon
from .normalizer import normalize_hausa_text
from .parser import parse


class _Nfa:
    def __init__(self) -> None:
        self.edges: list[dict[str, set[int]]] = []
        self.epsilon: list[set[int]] = []

    def state(self) -> int:
        self.edges.append({})
        self.epsilon.append(set())
        return len(self.edges) - 1

    def edge(self, source: int, token: str, target: int) -> None:
        self.edges[source].setdefault(token, set()).add(target)

    def eps(self, source: int, target: int) -> None:
        self.epsilon[source].add(target)


def _insert(nfa: _Nfa, root: int, tokens: tuple[str, ...]) -> int:
    state = root
    for token in tokens:
        targets = nfa.edges[state].get(token)
        if targets and len(targets) == 1:
            state = next(iter(targets))
        else:
            target = nfa.state()
            nfa.edge(state, token, target)
            state = target
    return state


def _below_thousand(nfa: _Nfa) -> tuple[int, set[int]]:
    root = nfa.state()
    terminals = {_insert(nfa, root, tuple(generate(value).split())) for value in range(1_000)}
    return root, terminals


def _number_language(nfa: _Nfa) -> tuple[int, set[int]]:
    lower_root, lower_terminals = _below_thousand(nfa)
    current_root, current_terminals = lower_root, set(lower_terminals)
    # Échelles lues du lexique, de la plus petite à la plus grande. Les écrire
    # ici en dur ferait de ce module une source de vérité concurrente : c'est
    # ainsi que 1 000 a pu rester « dubu » dans la grammaire alors que le
    # lexique disait autre chose.
    for scale_value, scale in sorted((value, word) for value, word in SCALES):
        root = nfa.state()
        nfa.eps(root, current_root)
        after_scale = nfa.state()
        nfa.edge(root, scale, after_scale)

        multiplier_root, multiplier_terminals = _below_thousand(nfa)
        terminals = set(current_terminals)
        if scale_value == 1_000:
            # 1 000 a une forme canonique courte, sans multiplicateur.
            terminals.add(after_scale)
        nfa.eps(after_scale, multiplier_root)
        terminals.update(multiplier_terminals)
        for terminal in multiplier_terminals:
            nfa.edge(terminal, "da", current_root)
        current_root, current_terminals = root, terminals
    return current_root, current_terminals


def _expression_language(nfa: _Nfa) -> tuple[int, set[int], frozenset[str]]:
    left_root, left_terminals = _number_language(nfa)
    operator_tokens: set[str] = set()
    right_root, right_terminals = _number_language(nfa)
    for terminal in left_terminals:
        for aliases in HAUSA_OPERATORS.values():
            for alias in aliases:
                tokens = tuple(normalize_hausa_text(alias).split())
                operator_tokens.update(tokens)
                state = terminal
                for token in tokens:
                    target = nfa.state()
                    nfa.edge(state, token, target)
                    state = target
                nfa.eps(state, right_root)
    return left_root, right_terminals, frozenset(operator_tokens)


def _closure(nfa: _Nfa, states: frozenset[int]) -> frozenset[int]:
    result = set(states)
    stack = list(states)
    while stack:
        state = stack.pop()
        for target in nfa.epsilon[state]:
            if target not in result:
                result.add(target)
                stack.append(target)
    return frozenset(result)


def _determinize(
    nfa: _Nfa, root: int, terminals: set[int]
) -> tuple[tuple[dict[str, int], ...], frozenset[int]]:
    start = _closure(nfa, frozenset({root}))
    ids = {start: 0}
    queue = deque([start])
    transitions: list[dict[str, int]] = []
    accepting: set[int] = set()
    while queue:
        subset = queue.popleft()
        state_id = ids[subset]
        while len(transitions) <= state_id:
            transitions.append({})
        if subset & terminals:
            accepting.add(state_id)
        by_token: dict[str, set[int]] = {}
        for state in subset:
            for token, targets in nfa.edges[state].items():
                by_token.setdefault(token, set()).update(targets)
        for token, targets in by_token.items():
            closed = _closure(nfa, frozenset(targets))
            if closed not in ids:
                ids[closed] = len(ids)
                queue.append(closed)
            transitions[state_id][token] = ids[closed]
    return tuple(transitions), frozenset(accepting)


@dataclass(frozen=True)
class NumberGrammar:
    _transitions: tuple[dict[str, int], ...]
    _accepting: frozenset[int]
    pronunciations: dict[str, tuple[str, ...]]
    grammar_version: str
    kind: str = "numbers"
    operator_tokens: frozenset[str] = frozenset()
    start: int = 0

    @property
    def tokens(self) -> frozenset[str]:
        return frozenset(token for edges in self._transitions for token in edges)

    @property
    def state_count(self) -> int:
        return len(self._transitions)

    def transitions(self, state: int) -> dict[str, int]:
        return self._transitions[state] if 0 <= state < self.state_count else {}

    def step(self, state: int, token: str) -> int | None:
        canonical = self.canonical_token(token)
        return None if canonical is None else self.transitions(state).get(canonical)

    def is_accepting(self, state: int) -> bool:
        return state in self._accepting

    def walk(self, tokens: list[str]) -> tuple[int | None, tuple[str, ...]]:
        state = self.start
        canonical: list[str] = []
        for token in tokens:
            mapped = self.canonical_token(token)
            if mapped is None or mapped not in self.transitions(state):
                return None, tuple(canonical)
            canonical.append(mapped)
            state = self.transitions(state)[mapped]
        return state, tuple(canonical)

    def canonical_token(self, token: str) -> str | None:
        if token in self.tokens:
            return token
        for canonical, forms in self.pronunciations.items():
            if token in forms:
                return canonical
        return None

    def accepts(self, text: str, *, allow_pronunciations: bool = True) -> bool:
        tokens = normalize_hausa_text(text).split() if allow_pronunciations else text.split()
        state, _ = self.walk(tokens)
        return state is not None and self.is_accepting(state)

    def canonical_form(self, text: str) -> str | None:
        if self.kind == "expressions":
            expression = parse_expression(text)
            return render_expression(expression) if expression is not None else None
        if self.kind == "calculator":
            number = parse(text)
            if number is not None:
                return generate(number)
            expression = parse_expression(text)
            return render_expression(expression) if expression is not None else None
        number = parse(text)
        return generate(number) if number is not None else None


def _pronunciations(lexicon: Lexicon) -> dict[str, tuple[str, ...]]:
    result: dict[str, set[str]] = {}
    for surface, canonical in lexicon.linguistic_variant_map().items():
        if " " not in surface and " " not in canonical:
            result.setdefault(canonical, {canonical}).add(surface)
    # Mots d'échelle du lexique + connecteurs et particules d'opérateur, qui
    # n'ont pas de variante propre mais doivent exister comme tokens.
    for _value, scale_word in SCALES:
        result.setdefault(scale_word, {scale_word})
    for token in ("sha", "da", "a", "chi", "sau"):
        result.setdefault(token, {token})
    return {key: tuple(sorted(values)) for key, values in result.items()}


def _build(kind: str, lexicon: Lexicon | None = None) -> NumberGrammar:
    lexicon = lexicon or load_lexicon()
    nfa = _Nfa()
    operator_tokens = frozenset()
    if kind == "expressions":
        root, terminals, operator_tokens = _expression_language(nfa)
    elif kind == "calculator":
        root = nfa.state()
        number_root, number_terminals = _number_language(nfa)
        expression_root, expression_terminals, operator_tokens = _expression_language(nfa)
        nfa.eps(root, number_root)
        nfa.eps(root, expression_root)
        terminals = number_terminals | expression_terminals
    else:
        root, terminals = _number_language(nfa)
    transitions, accepting = _determinize(nfa, root, terminals)
    return NumberGrammar(
        transitions,
        accepting,
        MappingProxyType(_pronunciations(lexicon)),
        lexicon.grammar_version,
        kind,
        operator_tokens,
    )


def build_grammar(lexicon: Lexicon | None = None) -> NumberGrammar:
    return _build("numbers", lexicon)


def build_expression_grammar(lexicon: Lexicon | None = None) -> NumberGrammar:
    return _build("expressions", lexicon)


def build_calculator_grammar(lexicon: Lexicon | None = None) -> NumberGrammar:
    return _build("calculator", lexicon)


@lru_cache(maxsize=1)
def load_grammar() -> NumberGrammar:
    return build_grammar()


@lru_cache(maxsize=1)
def load_expression_grammar() -> NumberGrammar:
    return build_expression_grammar()


@lru_cache(maxsize=1)
def load_calculator_grammar() -> NumberGrammar:
    return build_calculator_grammar()


__all__ = [
    "NumberGrammar",
    "build_calculator_grammar",
    "build_expression_grammar",
    "build_grammar",
    "load_calculator_grammar",
    "load_expression_grammar",
    "load_grammar",
]
