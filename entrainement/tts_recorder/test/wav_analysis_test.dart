import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:tts_recorder/wav_analysis.dart';

import 'support/wav_factory.dart';

void main() {
  test('valide et mesure un master PCM 24 kHz mono 16 bits', () async {
    final directory = await Directory.systemTemp.createTemp('tts-wav-');
    addTearDown(() => directory.delete(recursive: true));
    final file = File('${directory.path}/master.wav');
    final bytes = makePcmWav(sampleRate: 24000);
    await file.writeAsBytes(bytes);

    final metrics = await inspectWav(file.path, expectedSampleRate: 24000);

    expect(metrics.formatValid, isTrue);
    expect(metrics.pcmMono16, isTrue);
    expect(metrics.sampleRate, 24000);
    expect(metrics.durationSeconds, closeTo(1, 0.001));
    expect(metrics.leadingSilenceSeconds, closeTo(0.1, 0.001));
    expect(metrics.trailingSilenceSeconds, closeTo(0.4, 0.001));
    expect(metrics.peak, closeTo(0.4, 0.01));
    expect(metrics.noiseFloorRms, 0);
    expect(await file.readAsBytes(), bytes);
  });

  test('le même analyseur accepte 16 kHz en ASR et le refuse en TTS', () async {
    final directory = await Directory.systemTemp.createTemp('tts-wav-');
    addTearDown(() => directory.delete(recursive: true));
    final file = File('${directory.path}/example.wav');
    await file.writeAsBytes(makePcmWav(sampleRate: 16000));

    final asrMetrics = await inspectWav(file.path, expectedSampleRate: 16000);
    final ttsMetrics = await inspectWav(file.path, expectedSampleRate: 24000);

    expect(asrMetrics.pcmMono16, isTrue);
    expect(asrMetrics.sampleRate, 16000);
    expect(asrMetrics.formatValid, isTrue);
    expect(ttsMetrics.formatValid, isFalse);
  });
}
