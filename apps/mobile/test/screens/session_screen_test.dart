import 'dart:async';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hausa_mobile/config/anon_id.dart';
import 'package:hausa_mobile/models/recognition_result.dart';
import 'package:hausa_mobile/recognition/recognition_repository.dart';
import 'package:hausa_mobile/recording/audio_recording_models.dart';
import 'package:hausa_mobile/recording/audio_recording_service.dart';
import 'package:hausa_mobile/recording/microphone_permission.dart';
import 'package:hausa_mobile/recording/recording_controller.dart';
import 'package:hausa_mobile/recording/recording_ticker.dart';
import 'package:hausa_mobile/screens/session_screen.dart';
import 'package:hausa_mobile/speech/hausa_speaker.dart';
import 'package:hausa_mobile/widgets/push_to_talk_button.dart';

import '../support/fake_hausa_tts.dart';

class _AudioService implements AudioRecordingService {
  @override
  Stream<double> amplitudeLevels() => const Stream<double>.empty();

  @override
  Future<void> cancel() async {}

  @override
  Future<void> deleteTemporary(String? path) async {}

  @override
  Future<void> dispose() async {}

  @override
  Future<AudioFileInspection> inspect(String path) async {
    return const AudioFileInspection(
      exists: true,
      sizeBytes: 96044,
      duration: Duration(seconds: 3),
      isFormatValid: true,
    );
  }

  @override
  Future<String> start() async => '/tmp/session.wav';

  @override
  Future<String?> stop() async => '/tmp/session.wav';
}

class _Permission implements MicrophonePermissionGateway {
  @override
  Future<MicrophonePermissionStatus> check() async =>
      MicrophonePermissionStatus.granted;

  @override
  Future<bool> openSettings() async => true;

  @override
  Future<MicrophonePermissionStatus> request() async =>
      MicrophonePermissionStatus.granted;
}

class _Ticker implements RecordingTicker {
  @override
  Stream<Duration> get ticks => const Stream<Duration>.empty();

  @override
  Future<void> dispose() async {}
}

class _SessionRecordingController extends RecordingController {
  _SessionRecordingController(AudioRecordingService service)
    : super(
        service: service,
        permissionGateway: _Permission(),
        tickerFactory: _Ticker.new,
      );

  @override
  Future<void> start() async {
    state = const RecordingState(
      phase: RecordingPhase.recording,
      permission: MicrophonePermissionStatus.granted,
    );
  }

  @override
  Future<void> stop() async {
    state = const RecordingState(
      phase: RecordingPhase.ready,
      permission: MicrophonePermissionStatus.granted,
      elapsed: Duration(seconds: 3),
      handoff: AudioHandoff(
        path: '/tmp/session.wav',
        duration: Duration(seconds: 3),
        sizeBytes: 96044,
      ),
    );
  }
}

class _RecognitionRepository implements RecognitionRepository {
  _RecognitionRepository({this.pending});

  final Completer<RecognitionResult>? pending;
  int calls = 0;

  @override
  Future<RecognitionResult> recognize({
    required AudioHandoff handoff,
    required String anonId,
    required CancelToken cancelToken,
  }) async {
    calls++;
    return pending?.future ?? _result;
  }
}

const RecognitionResult _result = RecognitionResult(
  id: 'recognition-id',
  recognizedNumber: null,
  hausaText: 'ashirin da uku a ƙara goma sha biyar',
  normalizedText: 'ashirin da uku a ƙara goma sha biyar',
  confidence: 0.95,
  decision: Decision.accept,
  modelVersion: 'ctc',
  grammarVersion: 'v1',
  expression: RecognizedExpression(
    left: 23,
    operator: '+',
    right: 15,
    hausaText: 'ashirin da uku a ƙara goma sha biyar',
    result: 38,
    resultHausaText: 'talatin da takwas',
  ),
);

void main() {
  testWidgets('le micro reste en bas à portée du pouce', (
    WidgetTester tester,
  ) async {
    await _pumpSession(tester);

    final double buttonBottom = tester
        .getRect(find.byKey(const Key('push-to-talk')))
        .bottom;
    final double footerTop = tester
        .getRect(find.byKey(const Key('brand-footer')))
        .top;
    expect(buttonBottom, closeTo(footerTop - 20, 1));
  });

  testWidgets('maintenir puis relâcher traite et annonce le calcul', (
    WidgetTester tester,
  ) async {
    final _Harness harness = await _pumpSession(tester);
    await _record(tester);

    expect(harness.recognition.calls, 1);
    expect(find.byKey(const Key('session-answered')), findsOneWidget);
    expect(find.text('23 + 15\n=\n38'), findsOneWidget);
    expect(harness.synthesized, <String>[
      'ashirin da uku a ƙara goma sha biyar '
          'Sakamakon shi ne talatin da takwas',
    ]);
  });

  testWidgets('le traitement est grand, coloré et animé', (
    WidgetTester tester,
  ) async {
    final Completer<RecognitionResult> pending = Completer<RecognitionResult>();
    await _pumpSession(tester, pending: pending);
    await _record(tester, waitForAnswer: false);

    final Finder indicator = find.byKey(
      const Key('modern-processing-indicator'),
    );
    expect(tester.getSize(indicator), const Size(176, 176));
    final Transform before = tester.widget<Transform>(
      find.byKey(const Key('modern-processing-pulse')),
    );
    await tester.pump(const Duration(milliseconds: 200));
    final Transform after = tester.widget<Transform>(
      find.byKey(const Key('modern-processing-pulse')),
    );
    expect(after.transform, isNot(equals(before.transform)));

    pending.complete(_result);
    await tester.pump();
    await tester.pump();
    expect(find.byKey(const Key('session-answered')), findsOneWidget);
  });
}

class _Harness {
  const _Harness({required this.recognition, required this.synthesized});

  final _RecognitionRepository recognition;
  final List<String> synthesized;
}

Future<_Harness> _pumpSession(
  WidgetTester tester, {
  Completer<RecognitionResult>? pending,
}) async {
  final _AudioService service = _AudioService();
  final _SessionRecordingController recording = _SessionRecordingController(
    service,
  );
  final _RecognitionRepository recognition = _RecognitionRepository(
    pending: pending,
  );
  final List<String> synthesized = <String>[];
  final HausaSpeaker speaker = fakeHausaSpeaker(
    played: <Uint8List>[],
    synthesized: synthesized,
  );

  await tester.pumpWidget(
    ProviderScope(
      overrides: <Override>[
        recordingControllerProvider.overrideWith((ref) => recording),
        recognitionRepositoryProvider.overrideWithValue(recognition),
        anonIdProvider.overrideWithValue('anon-id'),
        hausaSpeakerProvider.overrideWithValue(speaker),
        recordingCuePlayerProvider.overrideWithValue((Uint8List wav) async {}),
      ],
      child: const MaterialApp(home: SessionScreen()),
    ),
  );
  await tester.pump();
  return _Harness(recognition: recognition, synthesized: synthesized);
}

Future<void> _record(WidgetTester tester, {bool waitForAnswer = true}) async {
  final PushToTalkButton button = tester.widget<PushToTalkButton>(
    find.byType(PushToTalkButton),
  );
  button.onStart();
  await tester.pump();
  button.onEnd(PushToTalkOutcome.released);
  await tester.pump(queueApresRelache);
  for (
    int attempt = 0;
    attempt < 20 &&
        (waitForAnswer
            ? find.byKey(const Key('session-answered')).evaluate().isEmpty
            : find.byKey(const Key('session-processing')).evaluate().isEmpty);
    attempt++
  ) {
    await tester.pump(const Duration(milliseconds: 1));
  }
}
