import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hausa_mobile/feedback/feedback_models.dart';
import 'package:hausa_mobile/models/recognition_result.dart';
import 'package:hausa_mobile/navigation/app_routes.dart';
import 'package:hausa_mobile/speech/hausa_speaker.dart';
import 'package:hausa_mobile/speech/voice_bank.dart';
import 'package:hausa_mobile/widgets/brand_app_bar.dart';
import 'package:hausa_mobile/widgets/brand_footer.dart';
import 'package:hausa_mobile/widgets/hausa_number_display.dart';

/// Écran Résultat d'un énoncé « nombre seul ».
///
/// Le nombre reconnu est **prononcé** à l'affichage : l'utilisateur cible ne
/// lit pas, et la forme hausa n'est jamais écrite à l'écran (cf.
/// `HausaNumberDisplay`) — sans restitution vocale, cet écran ne lui rendrait
/// rien. La forme dite vient du serveur ([RecognitionResult.spokenText]) et
/// n'est jamais recomposée ici : `jikka` s'écrit ainsi mais se dit `jikk ka`.
class ResultScreen extends ConsumerStatefulWidget {
  const ResultScreen({super.key, required this.result, this.confirmed});

  /// Reconnaissance d'origine (décision serveur inchangée).
  final RecognitionResult result;

  /// Choix confirmé en 3.4 : le nombre/forme retenus peuvent différer de la
  /// proposition principale (alternative choisie). `null` sur le chemin `accept`.
  final ConfirmedResult? confirmed;

  @override
  ConsumerState<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends ConsumerState<ResultScreen> {
  bool _spoken = false;

  int? get _number =>
      widget.confirmed?.number ?? widget.result.recognizedNumber;

  String get _hausaText =>
      widget.confirmed?.hausaText ?? widget.result.hausaText;

  String get _spokenText =>
      widget.confirmed?.spokenText ?? widget.result.spokenText;

  @override
  Widget build(BuildContext context) {
    // Dit une seule fois : contrairement au calcul, l'écran reste affiché et
    // l'utilisateur peut relancer un enregistrement quand il veut.
    final HausaSpeaker? speaker = ref.watch(hausaSpeakerProvider);
    if (!_spoken && speaker != null && _hausaText.trim().isNotEmpty) {
      _spoken = true;
      final List<VoiceSegment> utterance = speaker.preferred(
        _hausaText,
        _spokenText,
      );
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          unawaited(speaker.speak(utterance));
        }
      });
    }

    return Scaffold(
      key: const Key('result-screen'),
      appBar: const BrandAppBar(title: 'Résultat'),
      bottomNavigationBar: const BrandFooter(),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              Expanded(
                child: Center(
                  child: Semantics(
                    liveRegion: true,
                    label:
                        'Nombre reconnu $_number. '
                        'En hausa : $_hausaText.',
                    child: ExcludeSemantics(
                      child: Theme(
                        data: Theme.of(context).copyWith(
                          textTheme: Theme.of(context).textTheme.copyWith(
                            titleLarge: Theme.of(
                              context,
                            ).textTheme.displayLarge,
                            bodyMedium: Theme.of(
                              context,
                            ).textTheme.headlineMedium,
                          ),
                        ),
                        child: HausaNumberDisplay(number: _number),
                      ),
                    ),
                  ),
                ),
              ),
              FilledButton.icon(
                key: const Key('record-new-number-button'),
                onPressed: () => Navigator.of(context).pop(),
                icon: const Icon(Icons.mic),
                label: const Text('Enregistrer un nouveau nombre'),
              ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                key: const Key('open-correction-button'),
                onPressed: () => Navigator.of(
                  context,
                ).pushNamed(AppRoutes.correction, arguments: widget.result),
                icon: const Icon(Icons.edit_outlined),
                label: const Text('Corriger'),
              ),
              const SizedBox(height: 12),
              TextButton.icon(
                key: const Key('result-home-button'),
                onPressed: () => Navigator.of(
                  context,
                ).popUntil((Route<dynamic> route) => route.isFirst),
                icon: const Icon(Icons.home_outlined),
                label: const Text('Retour à l’Accueil'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
