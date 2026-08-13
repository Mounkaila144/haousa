/// Parcours vocal principal sur un seul écran.
///
/// Le bandeau et le pied de page restent fixes. Le centre passe naturellement
/// du micro au traitement puis à la réponse, sans demander à l'utilisateur de
/// retrouver ses repères après chaque étape.
library;

import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hausa_mobile/calculation/calculation_view.dart';
import 'package:hausa_mobile/models/recognition_result.dart';
import 'package:hausa_mobile/navigation/app_routes.dart';
import 'package:hausa_mobile/recognition/recognition_controller.dart';
import 'package:hausa_mobile/recording/audio_recording_models.dart';
import 'package:hausa_mobile/recording/recording_controller.dart';
import 'package:hausa_mobile/speech/cues.dart';
import 'package:hausa_mobile/speech/hausa_speaker.dart';
import 'package:hausa_mobile/speech/voice_bank.dart';
import 'package:hausa_mobile/widgets/brand_app_bar.dart';
import 'package:hausa_mobile/widgets/brand_footer.dart';
import 'package:hausa_mobile/widgets/push_to_talk_button.dart';

const int kMaxRepetitions = 3;
const Duration kRepeatDelay = Duration(seconds: 3);

enum SessionPhase { idle, recording, processing, answered }

class SessionScreen extends ConsumerStatefulWidget {
  const SessionScreen({super.key});

  @override
  ConsumerState<SessionScreen> createState() => _SessionScreenState();
}

class _SessionScreenState extends ConsumerState<SessionScreen> {
  SessionPhase _phase = SessionPhase.idle;
  RecognitionResult? _result;
  AudioHandoff? _handoff;
  int _voiceVersion = 0;
  Timer? _repeatTimer;
  bool _canReplay = false;
  String? _failure;

  @override
  void dispose() {
    _stopVoice();
    super.dispose();
  }

  void _stopVoice() {
    _voiceVersion++;
    _repeatTimer?.cancel();
    _repeatTimer = null;
  }

  void _goTo(SessionPhase phase) {
    if (!mounted) return;
    _stopVoice();
    setState(() {
      _phase = phase;
      _canReplay = false;
    });
  }

  void _startRecording() {
    _stopVoice();
    setState(() {
      _phase = SessionPhase.recording;
      _failure = null;
    });
    unawaited(ref.read(recordingControllerProvider.notifier).start());
  }

  Future<void> _finishRecording(PushToTalkOutcome outcome) async {
    if (outcome == PushToTalkOutcome.cancelled) {
      await ref.read(recordingControllerProvider.notifier).cancel();
      _goTo(SessionPhase.idle);
      return;
    }

    await Future<void>.delayed(queueApresRelache);
    if (!mounted) return;
    await ref.read(recordingControllerProvider.notifier).stop();
    if (!mounted) return;

    final RecordingState recording = ref.read(recordingControllerProvider);
    final AudioHandoff? handoff = recording.handoff;
    if (handoff == null) {
      _goTo(SessionPhase.idle);
      final String measurement = recording.elapsed > Duration.zero
          ? ' (${(recording.elapsed.inMilliseconds / 1000).toStringAsFixed(1)} s captées)'
          : '';
      setState(() {
        _failure =
            (recording.message ??
                'L’enregistrement n’a pas abouti. Parlez un peu plus longtemps.') +
            measurement;
      });
      return;
    }

    setState(() => _handoff = handoff);
    _goTo(SessionPhase.processing);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted ||
          _phase != SessionPhase.processing ||
          !identical(_handoff, handoff)) {
        return;
      }
      unawaited(
        ref.read(recognitionControllerProvider(handoff).notifier).start(),
      );
    });
  }

  Future<void> _cancelProcessing() async {
    final AudioHandoff? handoff = _handoff;
    if (handoff != null) {
      await ref.read(recognitionControllerProvider(handoff).notifier).cancel();
    }
    _goTo(SessionPhase.idle);
  }

  Future<void> _speakCurrentAnswer() async {
    final int version = ++_voiceVersion;
    final HausaSpeaker? speaker = ref.read(hausaSpeakerProvider);
    if (speaker == null) return;

    final List<VoiceSegment> utterance = _currentUtterance;
    for (int passage = 0; passage < kMaxRepetitions; passage++) {
      if (!mounted || version != _voiceVersion) return;
      final SpeechOutcome outcome = await speaker.speak(utterance);
      if (!mounted || version != _voiceVersion) return;
      if (outcome != SpeechOutcome.spoken) break;
      if (passage < kMaxRepetitions - 1) {
        await _waitBeforeRepeating();
      }
    }
    if (mounted && version == _voiceVersion) {
      setState(() => _canReplay = true);
    }
  }

  Future<void> _waitBeforeRepeating() {
    final Completer<void> completer = Completer<void>();
    _repeatTimer = Timer(kRepeatDelay, () {
      if (!completer.isCompleted) completer.complete();
    });
    return completer.future;
  }

  List<VoiceSegment> get _currentUtterance {
    final RecognitionResult? result = _result;
    if (result == null) return const <VoiceSegment>[];
    final HausaSpeaker? speaker = ref.read(hausaSpeakerProvider);
    final RecognizedExpression? expression = result.expression;

    if (expression != null) {
      final CalculationView calculation = CalculationView(expression);
      if (calculation.outcome == CalculationOutcome.refused) {
        return calculation.utterance;
      }
      final List<VoiceSegment> operation =
          speaker?.preferred(expression.hausaText, expression.spokenText) ??
          utteranceFromHausa(expression.hausaText);
      return answerUtterance(operation, calculation.utterance);
    }
    if (result.decision == Decision.repeat) return repeatUtterance();
    final List<VoiceSegment> value =
        speaker?.preferred(result.hausaText, result.spokenText) ??
        utteranceFromHausa(result.hausaText);
    return result.decision == Decision.confirm
        ? confirmationUtterance(value)
        : value;
  }

  void _replay() {
    setState(() => _canReplay = false);
    unawaited(_speakCurrentAnswer());
  }

  void _onRecognition(RecognitionState next) {
    if (!mounted || _phase != SessionPhase.processing) return;
    if (next.phase == RecognitionPhase.error) {
      _goTo(SessionPhase.idle);
      setState(() {
        _failure =
            next.failure?.message ?? 'La reconnaissance a échoué. Réessayez.';
      });
      return;
    }
    if (next.phase != RecognitionPhase.success || next.result == null) return;
    setState(() => _result = next.result);
    _goTo(SessionPhase.answered);
    unawaited(_speakCurrentAnswer());
  }

  @override
  Widget build(BuildContext context) {
    final AudioHandoff? handoff = _handoff;
    if (handoff != null) {
      ref.listen<RecognitionState>(
        recognitionControllerProvider(handoff),
        (_, RecognitionState next) => _onRecognition(next),
      );
    }
    ref.watch(recordingControllerProvider);
    ref.watch(hausaSpeakerProvider);
    final WavPlayer cuePlayer = ref.watch(recordingCuePlayerProvider);

    return Scaffold(
      key: const Key('session-screen'),
      appBar: BrandAppBar(
        title: 'Calculatrice Hausa',
        automaticallyImplyLeading: false,
        actions: <Widget>[
          IconButton(
            key: const Key('open-settings-button'),
            onPressed: () =>
                Navigator.of(context).pushNamed(AppRoutes.settings),
            tooltip: 'Paramètres',
            icon: const Icon(Icons.settings_outlined),
          ),
          IconButton(
            key: const Key('open-privacy-button'),
            onPressed: () => Navigator.of(context).pushNamed(AppRoutes.privacy),
            tooltip: 'Confidentialité',
            icon: const Icon(Icons.privacy_tip_outlined),
          ),
        ],
      ),
      bottomNavigationBar: const BrandFooter(),
      body: SafeArea(
        child: LayoutBuilder(
          builder: (BuildContext context, BoxConstraints constraints) {
            return SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
              child: ConstrainedBox(
                constraints: BoxConstraints(
                  minHeight: constraints.maxHeight - 40,
                ),
                child: Align(
                  alignment:
                      _phase == SessionPhase.idle ||
                          _phase == SessionPhase.recording
                      ? Alignment.bottomCenter
                      : Alignment.center,
                  child: switch (_phase) {
                    SessionPhase.idle ||
                    SessionPhase.recording => _rest(cuePlayer),
                    SessionPhase.processing => _processing(),
                    SessionPhase.answered => _answer(),
                  },
                ),
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _rest(WavPlayer cuePlayer) {
    final String? failure = _failure;
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        if (failure != null) ...<Widget>[
          Semantics(
            liveRegion: true,
            child: Container(
              key: const Key('session-failure'),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.errorContainer,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  Icon(
                    Icons.error_outline_rounded,
                    color: Theme.of(context).colorScheme.onErrorContainer,
                  ),
                  const SizedBox(width: 12),
                  Flexible(
                    child: Text(
                      failure,
                      style: TextStyle(
                        fontSize: 18,
                        color: Theme.of(context).colorScheme.onErrorContainer,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),
        ],
        PushToTalkButton(
          enabled: true,
          onStart: _startRecording,
          onEnd: (PushToTalkOutcome outcome) =>
              unawaited(_finishRecording(outcome)),
          playCue: (bool starts) =>
              unawaited(cuePlayer(starts ? startCueWav : stopCueWav)),
        ),
      ],
    );
  }

  Widget _processing() {
    return Semantics(
      label: 'Nous écoutons votre calcul.',
      child: Column(
        key: const Key('session-processing'),
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          const _ModernProcessingIndicator(),
          const SizedBox(height: 48),
          OutlinedButton.icon(
            key: const Key('session-cancel'),
            onPressed: () => unawaited(_cancelProcessing()),
            icon: const Icon(Icons.close_rounded, size: 32),
            label: const Text('Annuler'),
            style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 20),
              textStyle: const TextStyle(fontSize: 22),
            ),
          ),
        ],
      ),
    );
  }

  Widget _answer() {
    final RecognitionResult? result = _result;
    final RecognizedExpression? expression = result?.expression;
    final CalculationView? calculation = expression == null
        ? null
        : CalculationView(expression);
    final bool refused = calculation?.outcome == CalculationOutcome.refused;
    final String answer = calculation == null
        ? '${result?.recognizedNumber ?? ''}'
        : refused
        ? ''
        : '${calculation.operationLabel}\n=\n${calculation.resultLabel}';

    return Semantics(
      label: refused
          ? 'La réponse est donnée à voix haute. Écoutez.'
          : 'Voici la réponse. $answer. Écoutez.',
      child: Column(
        key: const Key('session-answered'),
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          _speaker(),
          if (!refused && answer.isNotEmpty) ...<Widget>[
            const SizedBox(height: 16),
            ExcludeSemantics(
              child: Text(
                answer,
                key: const Key('session-result'),
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.displayMedium?.copyWith(
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
          ],
          const SizedBox(height: 32),
          Semantics(
            button: true,
            label: 'Faire une nouvelle opération',
            child: ExcludeSemantics(
              child: SizedBox(
                width: double.infinity,
                height: 110,
                child: FilledButton.icon(
                  key: const Key('session-restart'),
                  onPressed: () {
                    setState(() {
                      _result = null;
                      _handoff = null;
                      _failure = null;
                    });
                    _goTo(SessionPhase.idle);
                  },
                  icon: const Icon(Icons.mic_rounded, size: 44),
                  label: const Text(
                    'Nouvelle opération',
                    style: TextStyle(fontSize: 30),
                  ),
                  style: FilledButton.styleFrom(
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(20),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _speaker() {
    final ColorScheme colors = Theme.of(context).colorScheme;
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        Icon(Icons.volume_up_rounded, size: 96, color: colors.primary),
        const SizedBox(height: 16),
        SizedBox(
          height: 56,
          child: _canReplay
              ? TextButton.icon(
                  key: const Key('session-replay'),
                  onPressed: _replay,
                  icon: const Icon(Icons.replay_rounded, size: 30),
                  label: const Text('Réécouter'),
                  style: TextButton.styleFrom(
                    textStyle: const TextStyle(fontSize: 20),
                  ),
                )
              : null,
        ),
      ],
    );
  }
}

class _ModernProcessingIndicator extends StatefulWidget {
  const _ModernProcessingIndicator();

  @override
  State<_ModernProcessingIndicator> createState() =>
      _ModernProcessingIndicatorState();
}

class _ModernProcessingIndicatorState extends State<_ModernProcessingIndicator>
    with SingleTickerProviderStateMixin {
  late final AnimationController _animation = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1400),
  )..repeat();

  @override
  void dispose() {
    _animation.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    return SizedBox(
      key: const Key('modern-processing-indicator'),
      width: 176,
      height: 176,
      child: AnimatedBuilder(
        animation: _animation,
        builder: (BuildContext context, Widget? child) {
          final double angle = _animation.value * math.pi * 2;
          final double pulse = 1 + math.sin(angle) * 0.06;
          return Stack(
            alignment: Alignment.center,
            children: <Widget>[
              Transform.rotate(
                angle: angle,
                child: Container(
                  width: 168,
                  height: 168,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: SweepGradient(
                      colors: <Color>[
                        colors.primary,
                        colors.tertiary,
                        colors.error,
                        colors.primary,
                      ],
                    ),
                    boxShadow: <BoxShadow>[
                      BoxShadow(
                        color: colors.primary.withValues(alpha: 0.28),
                        blurRadius: 30,
                        spreadRadius: 5,
                      ),
                    ],
                  ),
                ),
              ),
              Container(
                width: 142,
                height: 142,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: Theme.of(context).scaffoldBackgroundColor,
                ),
              ),
              Transform.scale(
                key: const Key('modern-processing-pulse'),
                scale: pulse,
                child: Container(
                  width: 112,
                  height: 112,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: <Color>[colors.primary, colors.tertiary],
                    ),
                  ),
                  child: Icon(
                    Icons.graphic_eq_rounded,
                    size: 58,
                    color: colors.onPrimary,
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
