"""Paquet ``hausa_numbers`` — cœur déterministe texte↔nombre en hausa.

Ce paquet est **autonome** et **sans GPU** : il ne doit jamais importer
FastAPI, httpx, SQLAlchemy ni aucune dépendance ASR (isolation du moteur
linguistique). Il expose le pipeline complet : ``load_lexicon``, ``generate``
(nombre→hausa), ``normalize`` (texte→canonique), ``parse`` (hausa→nombre) et
``validate_invariant`` (preuve ``parse(generate(n)) == n``).
"""

from .exceptions import (
    DomainError,
    ExpressionParseError,
    GenerationError,
    GrammarDerivationError,
    LexiconError,
    LexiconValidationError,
    OutOfRangeError,
    ParseError,
    UnresolvedFormError,
)
from .expressions import (
    HAUSA_OPERATORS,
    Expression,
    ExpressionParseResult,
    ExpressionResult,
    ParsedOperation,
    evaluate,
    evaluate_text,
    parse_expression,
    parse_expression_detailed,
    parse_hausa_operation,
    render_expression,
    render_result,
    render_spoken,
    supported_operators,
    to_spoken,
)
from .generator import MAX_VALUE, MIN_VALUE, generate, generate_combined, number_to_hausa
from .grammar import (
    NumberGrammar,
    build_calculator_grammar,
    build_expression_grammar,
    build_grammar,
    load_calculator_grammar,
    load_expression_grammar,
    load_grammar,
)
from .loader import Lexicon, Operator, load_lexicon
from .money import (
    DEFAULT_THOUSAND_NAMING,
    MAX_MONEY_CFA,
    MIN_MONEY_CFA,
    THOUSAND_CFA,
    THOUSAND_NAMINGS,
    UNIT_CFA,
    ThousandNaming,
    format_money,
    parse_money,
    parse_scalar,
    thousand_word,
)
from .normalizer import (
    HAUSA_NORMALIZATION_ALIASES,
    NormalizationResult,
    normalize,
    normalize_hausa_text,
    normalize_with_trace,
)
from .parser import ParseCandidate, ParseResult, hausa_words_to_number, parse, parse_detailed
from .validator import InvariantReport, validate_invariant

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "Lexicon",
    "Operator",
    "load_lexicon",
    "DEFAULT_THOUSAND_NAMING",
    "MAX_MONEY_CFA",
    "MIN_MONEY_CFA",
    "THOUSAND_CFA",
    "THOUSAND_NAMINGS",
    "UNIT_CFA",
    "ThousandNaming",
    "format_money",
    "parse_money",
    "parse_scalar",
    "thousand_word",
    "generate",
    "generate_combined",
    "number_to_hausa",
    "MAX_VALUE",
    "MIN_VALUE",
    "normalize",
    "normalize_hausa_text",
    "HAUSA_NORMALIZATION_ALIASES",
    "normalize_with_trace",
    "NormalizationResult",
    "parse",
    "hausa_words_to_number",
    "parse_detailed",
    "ParseResult",
    "ParseCandidate",
    "validate_invariant",
    "InvariantReport",
    "NumberGrammar",
    "build_grammar",
    "build_expression_grammar",
    "build_calculator_grammar",
    "load_calculator_grammar",
    "load_grammar",
    "load_expression_grammar",
    "Expression",
    "ParsedOperation",
    "HAUSA_OPERATORS",
    "ExpressionResult",
    "ExpressionParseResult",
    "parse_expression",
    "parse_expression_detailed",
    "parse_hausa_operation",
    "evaluate",
    "evaluate_text",
    "render_expression",
    "render_spoken",
    "to_spoken",
    "render_result",
    "supported_operators",
    "LexiconError",
    "LexiconValidationError",
    "GenerationError",
    "OutOfRangeError",
    "UnresolvedFormError",
    "GrammarDerivationError",
    "ParseError",
    "ExpressionParseError",
    "DomainError",
]
