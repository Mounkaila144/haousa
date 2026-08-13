/// Modèle partagé des réponses `/recognize` et `/history`.
library;

enum Decision { accept, confirm, repeat }

class RecognitionContractException implements Exception {
  const RecognitionContractException();
}

class RecognitionAlternative {
  const RecognitionAlternative({
    required this.number,
    required this.hausaText,
    required this.score,
    this.spokenText = '',
  });

  factory RecognitionAlternative.fromLiveJson(Map<String, dynamic> json) {
    final Object? number = json['number'];
    final Object? hausaText = json['hausa_text'];
    final Object? spokenText = json['spoken_text'];
    final Object? score = json['score'];
    if ((number != null && number is! num) ||
        hausaText is! String ||
        (spokenText != null && spokenText is! String) ||
        score is! num ||
        score < 0 ||
        score > 1) {
      throw const RecognitionContractException();
    }
    return RecognitionAlternative(
      number: (number as num?)?.toInt(),
      hausaText: hausaText,
      spokenText: spokenText as String? ?? '',
      score: score.toDouble(),
    );
  }

  final int? number;
  final String hausaText;

  /// Forme à **prononcer**, vide si elle coïncide avec [hausaText].
  final String spokenText;
  final double score;
}

/// Opération reconnue et son résultat (story 6.1).
///
/// Champ **optionnel** de la réponse : `null` pour un énoncé « nombre seul »,
/// c'est-à-dire tout le comportement des epics 1–5.
///
/// Aucun calcul n'a lieu côté mobile : le résultat vient du serveur, qui le
/// tient de `hausa_numbers` — source unique. Quand l'opération est comprise
/// mais que sa réponse sort du domaine (résultat négatif, dépassement, division
/// par zéro), [result] est `null` et [refusalCode] dit pourquoi. Rien n'est
/// arrondi ni deviné à l'affichage (FR21).
class RecognizedExpression {
  const RecognizedExpression({
    required this.left,
    required this.operator,
    required this.right,
    required this.hausaText,
    this.spokenText = '',
    this.result,
    this.remainder = 0,
    this.resultHausaText = '',
    this.resultSpokenText = '',
    this.refusalCode,
  });

  factory RecognizedExpression.fromLiveJson(Map<String, dynamic> json) {
    final Object? left = json['left'];
    final Object? operator = json['operator'];
    final Object? right = json['right'];
    final Object? hausaText = json['hausa_text'];
    final Object? spokenText = json['spoken_text'];
    final Object? result = json['result'];
    final Object? remainder = json['remainder'];
    final Object? resultHausaText = json['result_hausa_text'];
    final Object? resultSpokenText = json['result_spoken_text'];
    final Object? refusalCode = json['refusal_code'];

    if (left is! num ||
        right is! num ||
        operator is! String ||
        !_operators.contains(operator) ||
        hausaText is! String ||
        (spokenText != null && spokenText is! String) ||
        (result != null && result is! num) ||
        (remainder != null && remainder is! num) ||
        (resultHausaText != null && resultHausaText is! String) ||
        (resultSpokenText != null && resultSpokenText is! String) ||
        (refusalCode != null && refusalCode is! String)) {
      throw const RecognitionContractException();
    }
    // Un refus et un résultat ne peuvent pas coexister : ce serait un contrat
    // ambigu, donc un risque d'afficher un nombre là où le serveur refuse.
    if (result != null && refusalCode != null) {
      throw const RecognitionContractException();
    }

    return RecognizedExpression(
      left: left.toInt(),
      operator: operator,
      right: right.toInt(),
      hausaText: hausaText,
      spokenText: spokenText as String? ?? '',
      result: (result as num?)?.toInt(),
      remainder: (remainder as num?)?.toInt() ?? 0,
      resultHausaText: resultHausaText as String? ?? '',
      resultSpokenText: resultSpokenText as String? ?? '',
      refusalCode: refusalCode as String?,
    );
  }

  /// Parseur tolérant, réservé aux entrées historiques.
  factory RecognizedExpression.fromJson(Map<String, dynamic> json) {
    return RecognizedExpression(
      left: (json['left'] as num?)?.toInt() ?? 0,
      operator: json['operator'] as String? ?? '+',
      right: (json['right'] as num?)?.toInt() ?? 0,
      hausaText: json['hausa_text'] as String? ?? '',
      spokenText: json['spoken_text'] as String? ?? '',
      result: (json['result'] as num?)?.toInt(),
      remainder: (json['remainder'] as num?)?.toInt() ?? 0,
      resultHausaText: json['result_hausa_text'] as String? ?? '',
      resultSpokenText: json['result_spoken_text'] as String? ?? '',
      refusalCode: json['refusal_code'] as String?,
    );
  }

  static const Set<String> _operators = <String>{'+', '-', '*', '/'};

  final int left;
  final String operator;
  final int right;
  final String hausaText;

  /// Forme à **prononcer**, vide si elle coïncide avec [hausaText].
  ///
  /// Variante a prononcer si le fournisseur vocal la prend en charge.
  final String spokenText;
  final int? result;
  final int remainder;
  final String resultHausaText;

  /// Forme du resultat a **prononcer**, vide si elle coincide avec
  /// [resultHausaText]. `jikka` s'ecrit ainsi mais se lit `jikk ka` : la
  /// synthese embarquee lit des caracteres, et perd la gemination. La valeur
  /// vient du lexique serveur et n'est jamais recomposee sur l'appareil.
  final String resultSpokenText;
  final String? refusalCode;

  /// Le serveur a-t-il pu répondre ?
  bool get answered => result != null;

  /// Le résultat comporte-t-il un reste de division (« 20 reste 3 ») ?
  bool get hasRemainder => remainder != 0;
}

class RecognitionResult {
  const RecognitionResult({
    required this.id,
    required this.recognizedNumber,
    required this.hausaText,
    required this.normalizedText,
    required this.confidence,
    required this.decision,
    required this.modelVersion,
    required this.grammarVersion,
    this.spokenText = '',
    this.alternatives = const <RecognitionAlternative>[],
    this.expression,
    this.latencyTotalMs = 0,
    this.latencyAsrMs = 0,
    this.createdAt,
  });

  /// Parseur tolérant réservé aux entrées historiques existantes.
  factory RecognitionResult.fromJson(Map<String, dynamic> json) {
    final Object? createdAtRaw = json['created_at'];
    final Object? alternativesRaw = json['alternatives'];
    return RecognitionResult(
      id: json['id'] as String? ?? '',
      recognizedNumber: (json['recognized_number'] as num?)?.toInt(),
      hausaText: json['hausa_text'] as String? ?? '',
      spokenText: json['spoken_text'] as String? ?? '',
      normalizedText: json['normalized_text'] as String? ?? '',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
      decision: _historyDecision(json['decision']),
      alternatives: alternativesRaw is List<dynamic>
          ? alternativesRaw
                .whereType<Map<String, dynamic>>()
                .map(_tolerantAlternative)
                .toList(growable: false)
          : const <RecognitionAlternative>[],
      expression: json['expression'] is Map<String, dynamic>
          ? RecognizedExpression.fromJson(
              json['expression'] as Map<String, dynamic>,
            )
          : null,
      modelVersion: json['model_version'] as String? ?? '',
      grammarVersion: json['grammar_version'] as String? ?? '',
      latencyTotalMs: (json['latency_total_ms'] as num?)?.toInt() ?? 0,
      latencyAsrMs: (json['latency_asr_ms'] as num?)?.toInt() ?? 0,
      createdAt: createdAtRaw is String
          ? DateTime.tryParse(createdAtRaw)
          : null,
    );
  }

  /// Parseur strict pour une réponse live `200` de `/recognize`.
  factory RecognitionResult.fromLiveJson(Map<String, dynamic> json) {
    final Object? id = json['id'];
    final Object? number = json['recognized_number'];
    final Object? hausaText = json['hausa_text'];
    final Object? spokenText = json['spoken_text'];
    final Object? normalizedText = json['normalized_text'];
    final Object? confidence = json['confidence'];
    final Object? decisionRaw = json['decision'];
    final Object? alternativesRaw = json['alternatives'];
    final Object? modelVersion = json['model_version'];
    final Object? grammarVersion = json['grammar_version'];
    final Object? expressionRaw = json['expression'];
    final Object? latencyTotal = json['latency_total_ms'];
    final Object? latencyAsr = json['latency_asr_ms'];

    if (expressionRaw != null && expressionRaw is! Map<String, dynamic>) {
      throw const RecognitionContractException();
    }

    if (id is! String ||
        id.isEmpty ||
        (number != null && number is! num) ||
        hausaText is! String ||
        (spokenText != null && spokenText is! String) ||
        normalizedText is! String ||
        confidence is! num ||
        confidence < 0 ||
        confidence > 1 ||
        decisionRaw is! String ||
        alternativesRaw is! List<dynamic> ||
        modelVersion is! String ||
        modelVersion.isEmpty ||
        grammarVersion is! String ||
        grammarVersion.isEmpty ||
        latencyTotal is! num ||
        latencyTotal < 0 ||
        latencyAsr is! num ||
        latencyAsr < 0) {
      throw const RecognitionContractException();
    }

    final RecognizedExpression? expression = expressionRaw == null
        ? null
        : RecognizedExpression.fromLiveJson(
            expressionRaw as Map<String, dynamic>,
          );

    final Decision decision = _liveDecision(decisionRaw);
    // Un `accept` doit porter quelque chose de montrable — un nombre, ou une
    // opération. Sans cela l'écran n'aurait rien à afficher (ni à prononcer).
    if (decision == Decision.accept &&
        ((number == null && expression == null) || hausaText.trim().isEmpty)) {
      throw const RecognitionContractException();
    }

    final List<RecognitionAlternative> alternatives = alternativesRaw
        .map((dynamic item) {
          if (item is! Map<String, dynamic>) {
            throw const RecognitionContractException();
          }
          return RecognitionAlternative.fromLiveJson(item);
        })
        .toList(growable: false);

    return RecognitionResult(
      id: id,
      recognizedNumber: (number as num?)?.toInt(),
      hausaText: hausaText,
      spokenText: spokenText as String? ?? '',
      normalizedText: normalizedText,
      confidence: confidence.toDouble(),
      decision: decision,
      alternatives: alternatives,
      expression: expression,
      modelVersion: modelVersion,
      grammarVersion: grammarVersion,
      latencyTotalMs: latencyTotal.toInt(),
      latencyAsrMs: latencyAsr.toInt(),
    );
  }

  final String id;
  final int? recognizedNumber;
  final String hausaText;

  /// Forme à **prononcer** de [hausaText], vide si elle lui est identique.
  ///
  /// Concerne l'énoncé « nombre seul », qui n'a pas d'[expression] : `jikka`
  /// s'écrit ainsi mais se lit `jikk ka`, la synthèse embarquée lisant des
  /// caractères et perdant la gémination. Valeur issue du lexique serveur,
  /// jamais recomposée ici.
  final String spokenText;
  final String normalizedText;
  final double confidence;
  final Decision decision;
  final List<RecognitionAlternative> alternatives;

  /// Opération reconnue, `null` pour un énoncé « nombre seul » (story 6.1).
  final RecognizedExpression? expression;
  final String modelVersion;
  final String grammarVersion;
  final int latencyTotalMs;
  final int latencyAsrMs;
  final DateTime? createdAt;
}

Decision _liveDecision(String value) {
  switch (value) {
    case 'accept':
      return Decision.accept;
    case 'confirm':
      return Decision.confirm;
    case 'repeat':
      return Decision.repeat;
    default:
      throw const RecognitionContractException();
  }
}

Decision _historyDecision(Object? value) {
  if (value == 'accept') {
    return Decision.accept;
  }
  if (value == 'repeat') {
    return Decision.repeat;
  }
  return Decision.confirm;
}

RecognitionAlternative _tolerantAlternative(Map<String, dynamic> json) {
  return RecognitionAlternative(
    number: (json['number'] as num?)?.toInt(),
    hausaText: json['hausa_text'] as String? ?? '',
    score: (json['score'] as num?)?.toDouble() ?? 0,
  );
}
