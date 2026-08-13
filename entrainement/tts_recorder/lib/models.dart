enum QualityLevel { good, warning, bad, missing }

class Prompt {
  const Prompt({
    required this.id,
    required this.hausaText,
    required this.display,
  });

  final String id;
  final String hausaText;
  final String display;

  int get wordCount => hausaText
      .trim()
      .split(RegExp(r'\s+'))
      .where((word) => word.isNotEmpty)
      .length;

  Map<String, Object?> toJson() => <String, Object?>{
    'id': id,
    'texte_hausa': hausaText,
    'affichage': display,
  };

  factory Prompt.fromJson(Map<String, Object?> json) => Prompt(
    id: json['id']! as String,
    hausaText: json['texte_hausa']! as String,
    display: json['affichage']! as String,
  );
}

class Take {
  const Take({
    required this.promptId,
    required this.fileName,
    required this.recordedAt,
    required this.durationSeconds,
    required this.rms,
    required this.peak,
    required this.leadingSilenceSeconds,
    required this.trailingSilenceSeconds,
    required this.noiseFloorRms,
    required this.dcOffset,
    required this.clippedFraction,
    required this.sampleRate,
    required this.formatValid,
    this.meterMeanPeak,
    this.meterMaxPeak,
    this.meterCalibrationDb,
    this.autoStopped = false,
  });

  final String promptId;
  final String fileName;
  final DateTime recordedAt;
  final double durationSeconds;
  final double rms;
  final double peak;
  final double leadingSilenceSeconds;
  final double trailingSilenceSeconds;
  final double noiseFloorRms;
  final double dcOffset;
  final double clippedFraction;
  final int sampleRate;
  final bool formatValid;
  final double? meterMeanPeak;
  final double? meterMaxPeak;
  final double? meterCalibrationDb;
  final bool autoStopped;

  Map<String, Object?> toJson() => <String, Object?>{
    'prompt_id': promptId,
    'fichier': fileName,
    'date': recordedAt.toUtc().toIso8601String(),
    'duree_s': durationSeconds,
    'rms': rms,
    'crete': peak,
    'silence_debut_s': leadingSilenceSeconds,
    'silence_fin_s': trailingSilenceSeconds,
    'bruit_rms': noiseFloorRms,
    'decalage_dc': dcOffset,
    'fraction_saturee': clippedFraction,
    'sample_rate': sampleRate,
    'format_valide': formatValid,
    'vu_crete_moyenne': meterMeanPeak,
    'vu_crete_max': meterMaxPeak,
    'calibration_db': meterCalibrationDb,
    'arret_automatique': autoStopped,
  };

  factory Take.fromJson(Map<String, Object?> json) {
    final formatValid = json['format_valide']! as bool;
    return Take(
      promptId: json['prompt_id']! as String,
      fileName: json['fichier']! as String,
      recordedAt: DateTime.parse(json['date']! as String),
      durationSeconds: (json['duree_s']! as num).toDouble(),
      rms: (json['rms']! as num).toDouble(),
      peak: (json['crete']! as num).toDouble(),
      leadingSilenceSeconds: (json['silence_debut_s']! as num).toDouble(),
      trailingSilenceSeconds: (json['silence_fin_s']! as num).toDouble(),
      noiseFloorRms: (json['bruit_rms']! as num).toDouble(),
      dcOffset: (json['decalage_dc']! as num).toDouble(),
      clippedFraction: (json['fraction_saturee']! as num).toDouble(),
      // Les états antérieurs à la version 1.1 venaient de la campagne 48 kHz.
      sampleRate:
          (json['sample_rate'] as num?)?.toInt() ?? (formatValid ? 48000 : 0),
      formatValid: formatValid,
      meterMeanPeak: (json['vu_crete_moyenne'] as num?)?.toDouble(),
      meterMaxPeak: (json['vu_crete_max'] as num?)?.toDouble(),
      meterCalibrationDb: (json['calibration_db'] as num?)?.toDouble(),
      autoStopped: json['arret_automatique'] as bool? ?? false,
    );
  }
}

class Speaker {
  Speaker({
    required this.name,
    required this.slug,
    required this.code,
    required this.listName,
    required this.prompts,
    this.exampleSetName = '',
    Map<String, String>? exampleAudio,
    Map<String, Take>? takes,
    this.currentIndex = 0,
  }) : exampleAudio = exampleAudio ?? <String, String>{},
       takes = takes ?? <String, Take>{};

  final String name;
  final String slug;
  final String code;
  String listName;
  List<Prompt> prompts;
  String exampleSetName;
  Map<String, String> exampleAudio;
  final Map<String, Take> takes;
  int currentIndex;

  String get folderName => '$slug-$code';
  bool get hasStarted => takes.isNotEmpty;
  bool get isComplete =>
      prompts.every((prompt) => takes.containsKey(prompt.id));

  Map<String, Object?> toJson() => <String, Object?>{
    'nom': name,
    'slug': slug,
    'code': code,
    'liste': listName,
    'consignes': prompts.map((prompt) => prompt.toJson()).toList(),
    'banque_exemples': exampleSetName,
    'audios_exemples': exampleAudio,
    'prises': takes.map((id, take) => MapEntry(id, take.toJson())),
    'index': currentIndex,
  };

  factory Speaker.fromJson(Map<String, Object?> json) {
    final prompts = (json['consignes']! as List<Object?>)
        .cast<Map<String, Object?>>()
        .map(Prompt.fromJson)
        .toList();
    final rawTakes =
        (json['prises'] as Map<String, Object?>?) ?? <String, Object?>{};
    final rawExamples =
        (json['audios_exemples'] as Map<String, Object?>?) ??
        <String, Object?>{};
    return Speaker(
      name: json['nom']! as String,
      slug: json['slug']! as String,
      code: json['code']! as String,
      listName: json['liste']! as String,
      prompts: prompts,
      exampleSetName: json['banque_exemples'] as String? ?? '',
      exampleAudio: rawExamples.map(
        (id, value) => MapEntry(id, value! as String),
      ),
      takes: rawTakes.map(
        (id, value) =>
            MapEntry(id, Take.fromJson(value! as Map<String, Object?>)),
      ),
      currentIndex: (json['index'] as num?)?.toInt() ?? 0,
    );
  }
}

class QualityAssessment {
  const QualityAssessment(this.level, this.reasons);

  final QualityLevel level;
  final List<String> reasons;

  String get manifestValue => switch (level) {
    QualityLevel.good => 'ok',
    QualityLevel.warning => 'douteux',
    QualityLevel.bad => 'inutilisable',
    QualityLevel.missing => 'manquant',
  };
}
