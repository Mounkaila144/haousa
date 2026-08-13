import 'package:flutter_test/flutter_test.dart';
import 'package:tts_recorder/app_controller.dart';
import 'package:tts_recorder/models.dart';

const prompt = Prompt(id: 'tts_1', hausaText: 'afo', display: '1');
final date = DateTime.utc(2026, 7, 30);

void main() {
  test('une prise TTS propre est verte', () {
    final controller = AppController();
    final speaker = _speaker(_take());
    controller.speakers.add(speaker);

    expect(controller.assess(speaker, prompt).level, QualityLevel.good);
  });

  test('la saturation rend la prise inutilisable', () {
    final controller = AppController();
    final speaker = _speaker(_take(peak: 0.98, clippedFraction: 0.0001));
    controller.speakers.add(speaker);

    expect(controller.assess(speaker, prompt).level, QualityLevel.bad);
  });

  test('un bruit de fond élevé rend la prise douteuse', () {
    final controller = AppController();
    final speaker = _speaker(_take(noiseFloorRms: 0.021));
    controller.speakers.add(speaker);

    expect(controller.assess(speaker, prompt).level, QualityLevel.warning);
  });

  test('un RMS hors de la bande TTS rend la prise douteuse', () {
    final controller = AppController();
    final speaker = _speaker(_take(rms: 0.08));
    controller.speakers.add(speaker);

    final assessment = controller.assess(speaker, prompt);
    expect(assessment.level, QualityLevel.warning);
    expect(assessment.reasons, contains(contains('RMS sous la cible TTS')));
  });

  test('un pic supérieur à 0,70 rend la prise douteuse', () {
    final controller = AppController();
    final speaker = _speaker(_take(peak: 0.71));
    controller.speakers.add(speaker);

    final assessment = controller.assess(speaker, prompt);
    expect(assessment.level, QualityLevel.warning);
    expect(
      assessment.reasons,
      contains(contains('Pic au-dessus de la limite TTS')),
    );
  });

  test('une dérive de plus de 3 dB rejoint le QualityLevel existant', () {
    const prompts = <Prompt>[
      Prompt(id: 'p1', hausaText: 'afo', display: '1'),
      Prompt(id: 'p2', hausaText: 'ihinka', display: '2'),
      Prompt(id: 'p3', hausaText: 'ihinza', display: '3'),
      Prompt(id: 'p4', hausaText: 'itaci', display: '4'),
    ];
    final speaker = Speaker(
      name: 'Voix',
      slug: 'voix',
      code: 'abcd',
      listName: 'TTS',
      prompts: prompts,
      takes: <String, Take>{
        'p1': _take(promptId: 'p1'),
        'p2': _take(promptId: 'p2'),
        'p3': _take(promptId: 'p3'),
        'p4': _take(promptId: 'p4', rms: 0.09),
      },
    );
    final controller = AppController()..speakers.add(speaker);

    final drift = controller.levelDriftDb(speaker, prompts.last);
    final assessment = controller.assess(speaker, prompts.last);

    expect(drift, closeTo(-4.44, 0.05));
    expect(assessment.level, QualityLevel.warning);
    expect(assessment.reasons, contains(contains('moyenne de la séance')));
  });
}

Take _take({
  String promptId = 'tts_1',
  double rms = 0.15,
  double peak = 0.5,
  double clippedFraction = 0,
  double noiseFloorRms = 0.005,
}) => Take(
  promptId: promptId,
  fileName: '$promptId.wav',
  recordedAt: date,
  durationSeconds: 0.85,
  rms: rms,
  peak: peak,
  leadingSilenceSeconds: 0.1,
  trailingSilenceSeconds: 0.3,
  noiseFloorRms: noiseFloorRms,
  dcOffset: 0,
  clippedFraction: clippedFraction,
  sampleRate: 24000,
  formatValid: true,
);

Speaker _speaker(Take take) => Speaker(
  name: 'Voix',
  slug: 'voix',
  code: 'abcd',
  listName: 'TTS',
  prompts: const <Prompt>[prompt],
  takes: <String, Take>{prompt.id: take},
);
