import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';

import 'audio_service.dart';
import 'csv_codec.dart';
import 'models.dart';
import 'wav_analysis.dart';
import 'zip_writer.dart';

class AppController extends ChangeNotifier {
  /// Nom du vocabulaire embarqué. **Sans compte en dur** : il en portait un,
  /// et il a continué d'afficher « 400 consignes » alors que le fichier en
  /// contenait 427 — de quoi conclure que le nouveau CSV n'avait pas été pris
  /// en compte, alors qu'il l'était. Le compte réel est affiché à côté, il n'a
  /// pas à être répété ici où il ne peut que se périmer.
  static const embeddedListName = 'Vocabulaire TTS hausa';
  static const recordingProfile = AudioRecordingProfile.tts;
  static const targetRmsMin = 0.10;
  static const targetRmsMax = 0.20;
  static const targetPeakMax = 0.70;
  static const maximumLevelDriftDb = 3.0;
  static const minimumDriftBaselineTakes = 1;

  final List<Speaker> speakers = <Speaker>[];
  List<Prompt> selectedPrompts = <Prompt>[];
  String selectedListName = embeddedListName;
  Map<String, String> selectedExampleFiles = <String, String>{};
  String selectedExampleSetName = 'Aucun exemple audio (facultatif)';
  Speaker? selectedSpeaker;
  String? vocabularyUpdateMessage;
  bool initialized = false;

  late Directory _root;
  late Directory _recordings;
  late Directory _exports;
  late Directory _examples;
  late File _stateFile;

  bool get selectedExamplesComplete =>
      selectedPrompts.isNotEmpty &&
      selectedPrompts.every(
        (prompt) => selectedExampleFiles.containsKey(prompt.id),
      );

  Future<void> initialize() async {
    final documents = await getApplicationDocumentsDirectory();
    _root = Directory('${documents.path}/tts_recorder');
    final legacyRecordings = Directory('${_root.path}/masters_48khz');
    _recordings = Directory('${_root.path}/masters_wav');
    _exports = Directory('${_root.path}/exports');
    _examples = Directory('${_root.path}/exemples');
    _stateFile = File('${_root.path}/etat.json');
    if (!await _recordings.exists() && await legacyRecordings.exists()) {
      await legacyRecordings.rename(_recordings.path);
    }
    await _recordings.create(recursive: true);
    await _exports.create(recursive: true);
    await _examples.create(recursive: true);
    await useEmbeddedPrompts(notify: false);

    if (await _stateFile.exists()) {
      try {
        final decoded =
            jsonDecode(await _stateFile.readAsString()) as Map<String, Object?>;
        final rawVoices = (decoded['voix'] as List<Object?>?) ?? <Object?>[];
        speakers.addAll(
          rawVoices.map(
            (value) => Speaker.fromJson(value! as Map<String, Object?>),
          ),
        );
      } on Object {
        final backup = File(
          '${_stateFile.path}.illisible-${DateTime.now().millisecondsSinceEpoch}',
        );
        await _stateFile.rename(backup.path);
      }
    }
    final migration = _synchronizeSpeakersWithEmbeddedPrompts();
    if (migration.updatedSpeakers > 0) {
      vocabularyUpdateMessage = migration.discardedTakes == 0
          ? 'Le nouveau vocabulaire a été appliqué aux séances existantes.'
          : 'Le nouveau vocabulaire a été appliqué. '
                '${migration.discardedTakes} ancienne(s) prise(s) dont le '
                'texte a changé ont été écartées de l’export. Les fichiers '
                'WAV originaux restent conservés sur le téléphone.';
      await save();
    }
    if (speakers.isNotEmpty) {
      selectedSpeaker = speakers.first;
    }
    initialized = true;
    notifyListeners();
  }

  Future<void> useEmbeddedPrompts({bool notify = true}) async {
    final source = await rootBundle.loadString('assets/tts_prompts.csv');
    final prompts = parsePromptsCsv(source);
    // Le garde-fou attrape un asset VIDE ou illisible — un CSV tronqué
    // donnerait une séance sans rien signaler.
    //
    // Il comptait auparavant exactement 400 consignes, ce qui figeait le
    // vocabulaire numérique dans le code. Le lot embarqué change désormais
    // selon ce qu'on enregistre (les 400 nombres, puis les consignes système),
    // et une constante ne peut pas suivre : c'est le fichier qui décide.
    if (prompts.isEmpty) {
      throw const FormatException('Le vocabulaire embarqué est vide.');
    }
    if (prompts.any((prompt) => prompt.hausaText.contains('|'))) {
      throw const FormatException(
        'Le caractère | est interdit dans le texte Piper.',
      );
    }
    selectedPrompts = prompts;
    selectedListName = embeddedListName;
    selectedExampleFiles = <String, String>{};
    selectedExampleSetName = 'Aucun exemple audio (facultatif)';
    if (speakers.isNotEmpty) {
      final migration = _synchronizeSpeakersWithEmbeddedPrompts();
      if (migration.updatedSpeakers > 0) {
        vocabularyUpdateMessage = migration.discardedTakes == 0
            ? 'Le nouveau vocabulaire a été appliqué aux séances existantes.'
            : '${migration.discardedTakes} ancienne(s) prise(s) ont été '
                  'écartées car leur texte a changé. Les WAV originaux sont '
                  'conservés hors de l’export.';
        await save();
      }
    }
    if (notify) {
      notifyListeners();
    }
  }

  _VocabularyMigration _synchronizeSpeakersWithEmbeddedPrompts() {
    final newById = <String, Prompt>{
      for (final prompt in selectedPrompts) prompt.id: prompt,
    };
    var updatedSpeakers = 0;
    var discardedTakes = 0;

    for (final speaker in speakers) {
      final oldById = <String, Prompt>{
        for (final prompt in speaker.prompts) prompt.id: prompt,
      };
      final vocabularyChanged =
          oldById.length != newById.length ||
          newById.entries.any((entry) {
            final old = oldById[entry.key];
            return old == null ||
                old.hausaText != entry.value.hausaText ||
                old.display != entry.value.display;
          });
      if (!vocabularyChanged) {
        continue;
      }

      updatedSpeakers++;
      speaker.takes.removeWhere((id, _) {
        final old = oldById[id];
        final current = newById[id];
        // Une prise n'est effacée QUE si son texte a changé : l'audio dit
        // l'ancienne phrase, le garder reviendrait à mal l'étiqueter.
        //
        // En revanche, une consigne simplement RETIRÉE du vocabulaire garde sa
        // prise. `exportSpeaker` ne parcourt que `speaker.prompts` : elle est
        // donc déjà hors de l'export, sans qu'on ait à la supprimer. L'effacer
        // en plus détruisait le journal de 400 prises — 22 minutes de parole —
        // dès qu'on changeait de lot, et remettre l'ancien CSV ne le
        // ramenait pas. Le laisser rend l'opération réversible.
        final texteChange =
            old != null && current != null && old.hausaText != current.hausaText;
        final orphelineEtInconnue = old == null && current == null;
        final mustDiscard = texteChange || orphelineEtInconnue;
        if (mustDiscard) {
          discardedTakes++;
        }
        return mustDiscard;
      });

      // Une banque d'exemples liée à l'ancien texte ne doit jamais guider
      // l'enregistrement d'une consigne mise à jour.
      //
      // L'ORDRE EXISTANT EST CONSERVÉ, les nouvelles consignes vont à la fin.
      //
      // Rebattre les 427 à chaque mise à jour du vocabulaire dispersait les
      // nouvelles au milieu des anciennes : la séance repartait sur la
      // première non enregistrée, puis retombait aussitôt sur des consignes
      // déjà faites. Une personne qui a enregistré 400 prises se voyait
      // redemander les siennes.
      //
      // Le brassage garde son sens à la CRÉATION d'une voix (éviter un effet
      // d'ordre dans le corpus) — il n'en a aucun sur une séance commencée.
      // Les nouvelles venues sont brassées entre elles, pour la même raison.
      speaker
        ..prompts = _appendedPreservingOrder(
          speaker.prompts,
          selectedPrompts,
          speaker.code,
        )
        ..listName = selectedListName
        ..exampleAudio = <String, String>{}
        ..exampleSetName = 'Aucun exemple audio (vocabulaire mis à jour)';
      final firstMissing = speaker.prompts.indexWhere(
        (prompt) => !speaker.takes.containsKey(prompt.id),
      );
      speaker.currentIndex = firstMissing < 0
          ? max(0, speaker.prompts.length - 1)
          : firstMissing;
    }

    return _VocabularyMigration(
      updatedSpeakers: updatedSpeakers,
      discardedTakes: discardedTakes,
    );
  }

  Future<Directory> prepareExampleImportDirectory() async {
    final directory = Directory(
      '${_examples.path}/importe-${DateTime.now().microsecondsSinceEpoch}',
    );
    await directory.create(recursive: true);
    return directory;
  }

  Future<void> discardExampleImport(Directory directory) async {
    if (await directory.exists()) {
      await directory.delete(recursive: true);
    }
  }

  Future<int> useImportedExamples({
    required String manifest,
    required Map<String, String> extractedFiles,
  }) async {
    final rows = parseCsv(manifest);
    if (rows.length < 2) {
      throw const FormatException('Le manifest du ZIP est vide.');
    }
    final headers = rows.first;
    final fileIndex = headers.indexOf('fichier');
    final idIndex = headers.indexOf('identifiant');
    final hausaIndex = headers.indexOf('texte_hausa');
    final speakerIndex = headers.indexOf('locuteur');
    final codeIndex = headers.indexOf('code');
    if (fileIndex < 0 || idIndex < 0 || hausaIndex < 0) {
      throw const FormatException(
        'Le manifest doit contenir fichier, identifiant et texte_hausa.',
      );
    }

    final expected = <String, Prompt>{
      for (final prompt in selectedPrompts) prompt.id: prompt,
    };
    final matched = <String, String>{};
    String? exampleSpeaker;
    String? exampleCode;
    for (var rowIndex = 1; rowIndex < rows.length; rowIndex++) {
      final row = rows[rowIndex];
      final requiredLength = max(fileIndex, max(idIndex, hausaIndex)) + 1;
      if (row.length < requiredLength) {
        throw FormatException('Manifest, ligne ${rowIndex + 1} incomplète.');
      }
      final id = row[idIndex].trim();
      final prompt = expected[id];
      if (prompt == null) {
        throw FormatException(
          'Le ZIP contient « $id », absent du vocabulaire TTS.',
        );
      }
      if (row[hausaIndex].trim() != prompt.hausaText) {
        throw FormatException(
          'Texte hausa différent pour « $id » entre la liste et le ZIP.',
        );
      }
      final fileName = row[fileIndex].trim().split('/').last;
      final path = extractedFiles[fileName];
      if (path == null) {
        throw FormatException('Audio « $fileName » absent du ZIP.');
      }
      if (matched.containsKey(id)) {
        throw FormatException('Identifiant « $id » en double dans le ZIP.');
      }
      final metrics = await inspectWav(
        path,
        expectedSampleRate: recordingProfile.sampleRate,
      );
      if (!metrics.pcmMono16) {
        throw FormatException(
          'Exemple « $fileName » invalide : WAV PCM mono 16 bits requis.',
        );
      }
      matched[id] = path;
      if (speakerIndex >= 0 && speakerIndex < row.length) {
        exampleSpeaker ??= row[speakerIndex].trim();
      }
      if (codeIndex >= 0 && codeIndex < row.length) {
        exampleCode ??= row[codeIndex].trim();
      }
    }
    final missing = expected.keys
        .where((id) => !matched.containsKey(id))
        .toList();
    if (missing.isNotEmpty) {
      throw FormatException(
        '${missing.length} exemple(s) manquant(s), dont « ${missing.first} ».',
      );
    }

    final labelParts = <String>[
      if (exampleSpeaker != null && exampleSpeaker.isNotEmpty) exampleSpeaker,
      if (exampleCode != null && exampleCode.isNotEmpty) exampleCode,
    ];
    selectedExampleSetName = labelParts.isEmpty
        ? 'ZIP audio importé (${matched.length} exemples)'
        : 'Exemples · ${labelParts.join('-')}';
    selectedExampleFiles = matched;
    notifyListeners();
    return matched.length;
  }

  Future<Speaker> addSpeaker(String rawName) async {
    final name = rawName.trim();
    if (name.isEmpty) {
      throw const FormatException('Saisissez le nom de la voix.');
    }
    var slug = _slugify(name);
    if (slug.isEmpty) {
      slug = 'voix';
    }
    final existingCodes = speakers.map((speaker) => speaker.code).toSet();
    final random = Random.secure();
    const alphabet = 'abcdefghjkmnpqrstuvwxyz23456789';
    String code;
    do {
      code = List.generate(
        4,
        (_) => alphabet[random.nextInt(alphabet.length)],
      ).join();
    } while (existingCodes.contains(code));
    final speaker = Speaker(
      name: name,
      slug: slug,
      code: code,
      listName: selectedListName,
      prompts: _shuffled(selectedPrompts, code),
      exampleSetName: selectedExampleSetName,
      exampleAudio: Map<String, String>.of(selectedExampleFiles),
    );
    speakers.add(speaker);
    selectedSpeaker = speaker;
    await save();
    notifyListeners();
    return speaker;
  }

  void selectSpeaker(Speaker speaker) {
    selectedSpeaker = speaker;
    notifyListeners();
  }

  Future<void> restartSpeaker(Speaker speaker) async {
    final directory = speakerDirectory(speaker);
    if (await directory.exists()) {
      await directory.delete(recursive: true);
    }
    speaker
      ..takes.clear()
      ..prompts = _shuffled(selectedPrompts, speaker.code)
      ..listName = selectedListName
      ..exampleSetName = selectedExampleSetName
      ..exampleAudio = Map<String, String>.of(selectedExampleFiles)
      ..currentIndex = 0;
    await save();
    notifyListeners();
  }

  Directory speakerDirectory(Speaker speaker) =>
      Directory('${_recordings.path}/${speaker.folderName}');

  File takeFile(Speaker speaker, Take take) =>
      File('${speakerDirectory(speaker).path}/${take.fileName}');

  String? examplePath(Speaker speaker, Prompt prompt) =>
      speaker.exampleAudio[prompt.id];

  double recordedMinutes(Speaker speaker) =>
      speaker.takes.values.fold<double>(
        0,
        (sum, take) => sum + take.durationSeconds,
      ) /
      60;

  List<Take> _levelReferenceTakes(
    Speaker speaker, {
    String? excludingPromptId,
  }) => speaker.takes.values
      .where(
        (take) =>
            take.promptId != excludingPromptId &&
            take.formatValid &&
            take.sampleRate == recordingProfile.sampleRate &&
            take.rms > 0 &&
            take.peak < 0.98 &&
            take.clippedFraction == 0,
      )
      .toList();

  double? sessionAverageRms(
    Speaker speaker, {
    String? excludingPromptId,
    int minimumTakes = 1,
  }) {
    final takes = _levelReferenceTakes(
      speaker,
      excludingPromptId: excludingPromptId,
    );
    if (takes.length < minimumTakes) {
      return null;
    }
    final averageDb =
        takes.fold<double>(0, (sum, take) => sum + _linearToDb(take.rms)) /
        takes.length;
    return _dbToLinear(averageDb);
  }

  int calibrationSampleCount(Speaker speaker) => speaker.takes.values
      .where((take) => take.meterCalibrationDb != null)
      .length;

  double? meterCalibrationDb(Speaker speaker) {
    final values =
        speaker.takes.values
            .map((take) => take.meterCalibrationDb)
            .whereType<double>()
            .where((value) => value.isFinite)
            .toList()
          ..sort();
    if (values.isEmpty) {
      return null;
    }
    final middle = values.length ~/ 2;
    return values.length.isOdd
        ? values[middle]
        : (values[middle - 1] + values[middle]) / 2;
  }

  double? levelDriftDb(Speaker speaker, Prompt prompt) {
    final take = speaker.takes[prompt.id];
    if (take == null || take.rms <= 0) {
      return null;
    }
    final reference = sessionAverageRms(
      speaker,
      excludingPromptId: prompt.id,
      minimumTakes: minimumDriftBaselineTakes,
    );
    if (reference == null) {
      return null;
    }
    return _linearToDb(take.rms / reference);
  }

  Future<Take> storeTake({
    required Speaker speaker,
    required Prompt prompt,
    required String temporaryPath,
    required bool autoStopped,
    double? meterMeanPeak,
    double? meterMaxPeak,
  }) async {
    final metrics = await inspectWav(
      temporaryPath,
      expectedSampleRate: recordingProfile.sampleRate,
    );
    if (!metrics.formatValid) {
      final invalid = File(temporaryPath);
      if (await invalid.exists()) {
        await invalid.delete();
      }
      throw FormatException(
        'Format réel ${metrics.sampleRate} Hz refusé : '
        'WAV PCM ${recordingProfile.sampleRate ~/ 1000} kHz mono 16 bits requis.',
      );
    }
    final calibrationDb =
        meterMeanPeak != null && meterMeanPeak > 0 && metrics.rms > 0
        ? _linearToDb(metrics.rms / meterMeanPeak)
        : null;
    final directory = speakerDirectory(speaker);
    await directory.create(recursive: true);
    final fileName = fileNameForPrompt(prompt.id);
    final destination = File('${directory.path}/$fileName');
    final source = File(temporaryPath);
    final replacement = File('${destination.path}.nouveau');
    if (await replacement.exists()) {
      await replacement.delete();
    }
    await source.rename(replacement.path);
    if (await destination.exists()) {
      await destination.delete();
    }
    await replacement.rename(destination.path);
    final take = Take(
      promptId: prompt.id,
      fileName: fileName,
      recordedAt: DateTime.now().toUtc(),
      durationSeconds: metrics.durationSeconds,
      rms: metrics.rms,
      peak: metrics.peak,
      leadingSilenceSeconds: metrics.leadingSilenceSeconds,
      trailingSilenceSeconds: metrics.trailingSilenceSeconds,
      noiseFloorRms: metrics.noiseFloorRms,
      dcOffset: metrics.dcOffset,
      clippedFraction: metrics.clippedFraction,
      sampleRate: metrics.sampleRate,
      formatValid: metrics.formatValid,
      meterMeanPeak: meterMeanPeak,
      meterMaxPeak: meterMaxPeak,
      meterCalibrationDb: calibrationDb,
      autoStopped: autoStopped,
    );
    speaker.takes[prompt.id] = take;
    await save();
    notifyListeners();
    return take;
  }

  QualityAssessment assess(Speaker speaker, Prompt prompt) {
    final take = speaker.takes[prompt.id];
    if (take == null) {
      return const QualityAssessment(QualityLevel.missing, <String>[
        'Prise manquante',
      ]);
    }
    final bad = <String>[];
    final warnings = <String>[];
    if (!take.formatValid || take.sampleRate != recordingProfile.sampleRate) {
      bad.add(
        'Le master n’est pas un WAV '
        '${recordingProfile.sampleRate ~/ 1000} kHz mono 16 bits',
      );
    }
    if (take.peak >= 0.98 || take.clippedFraction > 0) {
      bad.add('Saturation détectée');
    }
    if (take.rms < 0.015) {
      bad.add('Voix trop faible (RMS < 0,015)');
    }
    if (take.durationSeconds < 0.35) {
      bad.add('Prise trop courte (< 0,35 s)');
    }
    if (take.durationSeconds > 12) {
      bad.add('Prise trop longue (> 12 s)');
    }

    if (take.rms > 0.25) {
      warnings.add('Niveau moyen très élevé');
    }
    if (take.rms < targetRmsMin) {
      warnings.add(
        'RMS sous la cible TTS '
        '(${take.rms.toStringAsFixed(3)} < 0,10)',
      );
    } else if (take.rms > targetRmsMax) {
      warnings.add(
        'RMS au-dessus de la cible TTS '
        '(${take.rms.toStringAsFixed(3)} > 0,20)',
      );
    }
    if (take.peak > targetPeakMax) {
      warnings.add(
        'Pic au-dessus de la limite TTS '
        '(${take.peak.toStringAsFixed(3)} > 0,70)',
      );
    }
    if (take.leadingSilenceSeconds < 0.08) {
      warnings.add('Début possiblement coupé (< 80 ms)');
    } else if (take.leadingSilenceSeconds > 1) {
      warnings.add('Plus de 1 s de silence au début');
    }
    if (take.trailingSilenceSeconds < 0.15) {
      warnings.add('Fin possiblement coupée (< 150 ms)');
    } else if (take.trailingSilenceSeconds > 1) {
      warnings.add('Plus de 1 s de silence à la fin');
    }
    if (take.noiseFloorRms > 0.02) {
      warnings.add('Bruit de fond élevé');
    }
    if (take.dcOffset.abs() > 0.02) {
      warnings.add('Décalage continu du signal');
    }
    final median = expectedMedian(prompt.wordCount);
    if (take.durationSeconds < median * 0.5 ||
        take.durationSeconds > median * 2) {
      warnings.add(
        'Durée inhabituelle (${take.durationSeconds.toStringAsFixed(2)} s, '
        'attendu ≈ ${median.toStringAsFixed(2)} s)',
      );
    }
    if (take.autoStopped) {
      warnings.add('Arrêt automatique à 15 s');
    }
    final driftDb = levelDriftDb(speaker, prompt);
    if (driftDb != null && driftDb.abs() > maximumLevelDriftDb) {
      final direction = driftDb > 0 ? 'plus forte' : 'plus faible';
      warnings.add(
        'Voix ${driftDb.abs().toStringAsFixed(1)} dB $direction '
        'que la moyenne de la séance : refaire conseillé',
      );
    }
    if (bad.isNotEmpty) {
      return QualityAssessment(QualityLevel.bad, <String>[...bad, ...warnings]);
    }
    if (warnings.isNotEmpty) {
      return QualityAssessment(QualityLevel.warning, warnings);
    }
    return const QualityAssessment(QualityLevel.good, <String>[]);
  }

  double expectedMedian(int wordCount) {
    final durations = <double>[];
    for (final speaker in speakers) {
      for (final prompt in speaker.prompts) {
        final take = speaker.takes[prompt.id];
        if (prompt.wordCount == wordCount &&
            take != null &&
            take.formatValid &&
            take.sampleRate == recordingProfile.sampleRate &&
            take.rms >= 0.015 &&
            take.peak < 0.98) {
          durations.add(take.durationSeconds);
        }
      }
    }
    if (durations.length >= 5) {
      durations.sort();
      final middle = durations.length ~/ 2;
      return durations.length.isOdd
          ? durations[middle]
          : (durations[middle - 1] + durations[middle]) / 2;
    }
    return 0.55 + 0.30 * wordCount;
  }

  Future<void> save() async {
    final payload = jsonEncode(<String, Object?>{
      'version': 2,
      'voix': speakers.map((speaker) => speaker.toJson()).toList(),
    });
    final temporary = File('${_stateFile.path}.nouveau');
    await temporary.writeAsString(payload, flush: true);
    if (await _stateFile.exists()) {
      await _stateFile.delete();
    }
    await temporary.rename(_stateFile.path);
  }

  Future<File> exportSpeaker(Speaker speaker) async {
    final destination = File(
      '${_exports.path}/hausa_tts_${speaker.folderName}.zip',
    );
    final base = 'hausa_tts/${speaker.folderName}';
    final metadata = StringBuffer();
    final manifest = StringBuffer()
      ..writeln(
        csvRow(<String>[
          'fichier',
          'identifiant',
          'texte_hausa',
          'affichage',
          'locuteur',
          'code',
          'date',
          'sample_rate',
          'duree_s',
          'rms',
          'crete',
          'silence_debut_s',
          'silence_fin_s',
          'bruit_rms',
          'decalage_dc',
          'fraction_saturee',
          'qualite',
        ]),
      );
    final entries = <ZipEntrySource>[];
    for (final prompt in speaker.prompts) {
      final take = speaker.takes[prompt.id];
      if (take == null) {
        continue;
      }
      final file = takeFile(speaker, take);
      if (!await file.exists()) {
        continue;
      }
      metadata.writeln(piperMetadataRow(take.fileName, prompt.hausaText));
      manifest.writeln(
        csvRow(<Object>[
          take.fileName,
          prompt.id,
          prompt.hausaText,
          prompt.display,
          speaker.slug,
          speaker.code,
          take.recordedAt.toUtc().toIso8601String(),
          take.sampleRate,
          take.durationSeconds.toStringAsFixed(3),
          take.rms.toStringAsFixed(6),
          take.peak.toStringAsFixed(6),
          take.leadingSilenceSeconds.toStringAsFixed(3),
          take.trailingSilenceSeconds.toStringAsFixed(3),
          take.noiseFloorRms.toStringAsFixed(6),
          take.dcOffset.toStringAsFixed(6),
          take.clippedFraction.toStringAsFixed(8),
          assess(speaker, prompt).manifestValue,
        ]),
      );
      entries.add(ZipEntrySource.fromFile('$base/wavs/${take.fileName}', file));
    }
    entries
      ..add(
        ZipEntrySource.fromBytes(
          '$base/metadata.csv',
          Uint8List.fromList(utf8.encode(metadata.toString())),
        ),
      )
      ..add(
        ZipEntrySource.fromBytes(
          '$base/manifest.csv',
          Uint8List.fromList(utf8.encode(manifest.toString())),
        ),
      );
    return writeStoredZip(destination, entries);
  }

  static String _slugify(String input) {
    const replacements = <String, String>{
      'à': 'a',
      'á': 'a',
      'â': 'a',
      'ä': 'a',
      'ã': 'a',
      'å': 'a',
      'ç': 'c',
      'è': 'e',
      'é': 'e',
      'ê': 'e',
      'ë': 'e',
      'ì': 'i',
      'í': 'i',
      'î': 'i',
      'ï': 'i',
      'ñ': 'n',
      'ò': 'o',
      'ó': 'o',
      'ô': 'o',
      'ö': 'o',
      'õ': 'o',
      'ù': 'u',
      'ú': 'u',
      'û': 'u',
      'ü': 'u',
      'ý': 'y',
      'ÿ': 'y',
    };
    var value = input.toLowerCase();
    replacements.forEach((source, target) {
      value = value.replaceAll(source, target);
    });
    return value
        .replaceAll(RegExp('[^a-z0-9]+'), '-')
        .replaceAll(RegExp('^-+|-+\$'), '');
  }

  /// Nouvelle liste d'une voix DÉJÀ commencée : l'ordre acquis d'abord, les
  /// consignes inédites ensuite.
  ///
  /// Les consignes retirées du vocabulaire disparaissent, celles qui restent
  /// gardent leur rang — c'est ce qui fait que la séance reprend là où elle
  /// s'était arrêtée au lieu de renvoyer la personne au début.
  static List<Prompt> _appendedPreservingOrder(
    List<Prompt> existants,
    List<Prompt> courants,
    String code,
  ) {
    final courantsParId = <String, Prompt>{
      for (final prompt in courants) prompt.id: prompt,
    };
    final dejaVus = <String>{};
    final ordonnes = <Prompt>[];
    for (final ancien in existants) {
      final courant = courantsParId[ancien.id];
      // Le texte à jour, pas l'ancien : c'est le même rang, mais la consigne
      // a pu être reformulée.
      if (courant != null && dejaVus.add(courant.id)) {
        ordonnes.add(courant);
      }
    }
    final inedits = courants.where((p) => !dejaVus.contains(p.id)).toList();
    return <Prompt>[...ordonnes, ..._shuffled(inedits, code)];
  }

  static List<Prompt> _shuffled(List<Prompt> source, String code) {
    var seed = 0x811c9dc5;
    for (final byte in utf8.encode(code)) {
      seed ^= byte;
      seed = (seed * 0x01000193) & 0x7fffffff;
    }
    final prompts = List<Prompt>.of(source);
    prompts.shuffle(Random(seed));
    return prompts;
  }

  static double _linearToDb(double value) => 20 * log(value) / ln10;

  static double _dbToLinear(double value) => pow(10, value / 20).toDouble();
}

class _VocabularyMigration {
  const _VocabularyMigration({
    required this.updatedSpeakers,
    required this.discardedTakes,
  });

  final int updatedSpeakers;
  final int discardedTakes;
}
