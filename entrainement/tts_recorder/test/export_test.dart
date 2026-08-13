import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:path_provider_platform_interface/path_provider_platform_interface.dart';
import 'package:tts_recorder/app_controller.dart';
import 'package:tts_recorder/models.dart';

import 'support/wav_factory.dart';

class _FakePathProvider extends PathProviderPlatform {
  _FakePathProvider(this.documentsPath);

  final String documentsPath;

  @override
  Future<String?> getApplicationDocumentsPath() async => documentsPath;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
    'export produces a directly usable single-speaker Piper dataset',
    () async {
      final temporaryDirectory = await Directory.systemTemp.createTemp(
        'tts-recorder-export-',
      );
      final previousPathProvider = PathProviderPlatform.instance;
      PathProviderPlatform.instance = _FakePathProvider(
        temporaryDirectory.path,
      );

      addTearDown(() async {
        PathProviderPlatform.instance = previousPathProvider;
        await temporaryDirectory.delete(recursive: true);
      });

      final controller = AppController();
      await controller.initialize();
      final speaker = await controller.addSpeaker('Voix test');

      final prompt = controller.selectedPrompts.first;
      final sourceWav = File('${temporaryDirectory.path}/capture.wav');
      await sourceWav.writeAsBytes(
        makePcmWav(sampleRate: 24000, toneSeconds: 0.5, amplitude: 0.20),
      );

      final take = await controller.storeTake(
        speaker: speaker,
        prompt: prompt,
        temporaryPath: sourceWav.path,
        autoStopped: false,
        meterMeanPeak: 0.20,
        meterMaxPeak: 0.30,
      );
      expect(take.meterCalibrationDb, isNotNull);
      expect(controller.calibrationSampleCount(speaker), 1);
      expect(controller.meterCalibrationDb(speaker), take.meterCalibrationDb);

      final zip = await controller.exportSpeaker(speaker);
      expect(await zip.exists(), isTrue);

      final datasetRoot = 'hausa_tts/${speaker.folderName}';
      final listing = await Process.run('unzip', ['-Z1', zip.path]);
      expect(listing.exitCode, 0);
      expect(listing.stdout, contains('$datasetRoot/metadata.csv'));
      expect(listing.stdout, contains('$datasetRoot/manifest.csv'));
      expect(listing.stdout, contains('$datasetRoot/wavs/${take.fileName}'));

      final metadata = await Process.run('unzip', [
        '-p',
        zip.path,
        '$datasetRoot/metadata.csv',
      ]);
      expect(metadata.exitCode, 0);
      expect(metadata.stdout, '${take.fileName}|${prompt.hausaText}\n');

      final manifest = await Process.run('unzip', [
        '-p',
        zip.path,
        '$datasetRoot/manifest.csv',
      ]);
      expect(manifest.exitCode, 0);
      expect(manifest.stdout, contains(prompt.id));
      expect(manifest.stdout, contains(prompt.hausaText));
      expect(manifest.stdout, contains(',24000,'));
    },
  );

  test('a vocabulary update never relabels an old recording', () async {
    final temporaryDirectory = await Directory.systemTemp.createTemp(
      'tts-recorder-migration-',
    );
    final previousPathProvider = PathProviderPlatform.instance;
    PathProviderPlatform.instance = _FakePathProvider(temporaryDirectory.path);

    addTearDown(() async {
      PathProviderPlatform.instance = previousPathProvider;
      await temporaryDirectory.delete(recursive: true);
    });

    final controller = AppController();
    await controller.initialize();
    final speaker = await controller.addSpeaker('Voix migration');
    final prompt = controller.selectedPrompts.first;
    final sourceWav = File('${temporaryDirectory.path}/ancienne-prise.wav');
    await sourceWav.writeAsBytes(
      makePcmWav(sampleRate: 24000, amplitude: 0.20),
    );
    await controller.storeTake(
      speaker: speaker,
      prompt: prompt,
      temporaryPath: sourceWav.path,
      autoStopped: false,
    );

    final oldIndex = speaker.prompts.indexWhere(
      (candidate) => candidate.id == prompt.id,
    );
    speaker.prompts[oldIndex] = Prompt(
      id: prompt.id,
      hausaText: 'ancien texte différent',
      display: prompt.display,
    );

    await controller.useEmbeddedPrompts();

    expect(speaker.takes, isNot(contains(prompt.id)));
    expect(
      speaker.prompts.singleWhere((candidate) => candidate.id == prompt.id),
      predicate<Prompt>((candidate) => candidate.hausaText == prompt.hausaText),
    );
    expect(controller.vocabularyUpdateMessage, contains('1 ancienne'));
  });

  test('une mise à jour du vocabulaire ne renvoie pas la personne au début',
      () async {
    // Le vocabulaire était REBATTU à chaque mise à jour : les consignes
    // inédites se dispersaient au milieu des anciennes, et la séance
    // retombait aussitôt sur des prises déjà faites. Quelqu'un qui avait
    // enregistré 400 consignes se voyait redemander les siennes.
    final temporaryDirectory = await Directory.systemTemp.createTemp(
      'tts-recorder-ordre-',
    );
    final previousPathProvider = PathProviderPlatform.instance;
    PathProviderPlatform.instance = _FakePathProvider(temporaryDirectory.path);
    addTearDown(() async {
      PathProviderPlatform.instance = previousPathProvider;
      await temporaryDirectory.delete(recursive: true);
    });

    final controller = AppController();
    await controller.initialize();
    final speaker = await controller.addSpeaker('Voix ordre');

    // On simule une voix qui ne connaît qu'une PARTIE du lot courant : c'est
    // la situation de quelqu'un qui a commencé avant l'ajout de nouvelles
    // consignes.
    final debut = speaker.prompts.take(speaker.prompts.length - 5).toList();
    speaker.prompts = List<Prompt>.of(debut);
    final ordreAvant =
        speaker.prompts.map((prompt) => prompt.id).toList(growable: false);

    // Les trois premières sont enregistrées. Le fichier temporaire est nommé
    // par son RANG, pas par l'identifiant : `tts_40/60` (une division) y
    // glisserait une barre oblique et créerait un sous-dossier.
    for (var i = 0; i < 3; i++) {
      final prompt = speaker.prompts[i];
      final wav = File('${temporaryDirectory.path}/prise-$i.wav');
      await wav.writeAsBytes(makePcmWav(sampleRate: 24000, amplitude: 0.20));
      await controller.storeTake(
        speaker: speaker,
        prompt: prompt,
        temporaryPath: wav.path,
        autoStopped: false,
      );
    }

    await controller.useEmbeddedPrompts();

    // L'ordre acquis est intact, en tête.
    expect(
      speaker.prompts.take(ordreAvant.length).map((prompt) => prompt.id),
      ordreAvant,
    );
    // Les inédites sont GROUPÉES à la fin : c'est ce qui fait qu'on les
    // enchaîne au lieu de retomber sur des consignes déjà faites.
    final inedites = speaker.prompts.skip(ordreAvant.length).toList();
    expect(inedites, hasLength(5));
    expect(
      inedites.every((prompt) => !ordreAvant.contains(prompt.id)),
      isTrue,
    );
    // Aucune prise perdue : le texte n'a pas changé, seul le lot a grossi.
    expect(speaker.takes, hasLength(3));
    // Et la séance reprend sur la première non enregistrée, pas au début.
    expect(speaker.currentIndex, 3);
  });
}
