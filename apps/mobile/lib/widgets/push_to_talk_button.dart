/// Bouton « parler en maintenant », sur le modèle des messages vocaux.
///
/// Un appui démarre la capture, un relâchement l'envoie et un glissement vers
/// le haut l'annule. Le retour visuel, haptique et sonore rend le geste clair
/// même dans un environnement bruyant.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

enum PushToTalkOutcome { released, cancelled }

/// Petite marge pour ne pas couper la dernière syllabe au relâchement.
const Duration queueApresRelache = Duration(milliseconds: 350);

const Duration _dureeMinimale = Duration(milliseconds: 400);
const double _seuilAnnulation = 90;

class PushToTalkButton extends StatefulWidget {
  const PushToTalkButton({
    super.key,
    required this.onStart,
    required this.onEnd,
    required this.enabled,
    this.playCue,
    this.now = DateTime.now,
  });

  final VoidCallback onStart;
  final void Function(PushToTalkOutcome outcome) onEnd;
  final bool enabled;
  final void Function(bool debut)? playCue;
  final DateTime Function() now;

  @override
  State<PushToTalkButton> createState() => _PushToTalkButtonState();
}

class _PushToTalkButtonState extends State<PushToTalkButton>
    with SingleTickerProviderStateMixin {
  bool _actif = false;
  bool _annuleParGlissement = false;
  DateTime? _debut;
  double? _origine;
  late final AnimationController _pulsation = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 650),
  );
  late final Animation<double> _echelle = Tween<double>(
    begin: 1,
    end: 1.075,
  ).animate(CurvedAnimation(parent: _pulsation, curve: Curves.easeInOut));

  void _demarrer() {
    if (!widget.enabled || _actif) return;
    setState(() {
      _actif = true;
      _annuleParGlissement = false;
    });
    _pulsation.repeat(reverse: true);
    _debut = widget.now();
    unawaited(HapticFeedback.mediumImpact());
    widget.playCue?.call(true);
    widget.onStart();
  }

  void _terminer() {
    if (!_actif) return;
    final Duration tenue = widget.now().difference(_debut ?? widget.now());
    final bool tropCourt = tenue < _dureeMinimale;
    setState(() => _actif = false);
    _pulsation
      ..stop()
      ..reset();
    unawaited(HapticFeedback.lightImpact());
    widget.playCue?.call(false);
    widget.onEnd(
      _annuleParGlissement || tropCourt
          ? PushToTalkOutcome.cancelled
          : PushToTalkOutcome.released,
    );
  }

  void _suivre(double dy) {
    if (!_actif) return;
    final bool franchi = dy <= -_seuilAnnulation;
    if (franchi != _annuleParGlissement) {
      setState(() => _annuleParGlissement = franchi);
      unawaited(HapticFeedback.selectionClick());
    }
  }

  @override
  void dispose() {
    _pulsation.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final ColorScheme couleurs = Theme.of(context).colorScheme;
    final bool annule = _annuleParGlissement;
    final double taille = _actif ? 190 : 170;

    return Semantics(
      button: true,
      label: 'Maintenir pour parler',
      hint:
          'Appuyez et gardez le doigt, parlez, puis relâchez. '
          'Glissez vers le haut pour annuler.',
      child: Listener(
        onPointerDown: (PointerDownEvent event) {
          _origine = event.position.dy;
          _demarrer();
        },
        onPointerMove: (PointerMoveEvent event) =>
            _suivre(event.position.dy - (_origine ?? event.position.dy)),
        onPointerUp: (_) => _terminer(),
        onPointerCancel: (_) => _terminer(),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            AnimatedBuilder(
              key: const Key('recording-pulse'),
              animation: _pulsation,
              builder: (BuildContext context, Widget? child) {
                return Transform.scale(
                  key: const Key('recording-pulse-transform'),
                  scale: _actif ? _echelle.value : 1,
                  child: child,
                );
              },
              child: AnimatedContainer(
                key: const Key('push-to-talk'),
                duration: const Duration(milliseconds: 120),
                width: taille,
                height: taille,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: !widget.enabled
                      ? couleurs.surfaceContainerHighest
                      : _actif
                      ? couleurs.error
                      : couleurs.primaryContainer,
                  border: _actif
                      ? Border.all(
                          color: couleurs.error.withValues(alpha: 0.45),
                          width: 8,
                        )
                      : null,
                  boxShadow: _actif
                      ? <BoxShadow>[
                          BoxShadow(
                            color: couleurs.error.withValues(
                              alpha: 0.25 + 0.2 * _pulsation.value,
                            ),
                            blurRadius: 28 + 16 * _pulsation.value,
                            spreadRadius: 8 + 12 * _pulsation.value,
                          ),
                        ]
                      : null,
                ),
                child: Icon(
                  annule ? Icons.close_rounded : Icons.mic_rounded,
                  size: taille * 0.45,
                  color: _actif
                      ? couleurs.onError
                      : couleurs.onPrimaryContainer,
                ),
              ),
            ),
            if (_actif) ...<Widget>[
              const SizedBox(height: 20),
              ExcludeSemantics(
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    Icon(
                      Icons.keyboard_arrow_up_rounded,
                      color: couleurs.onSurfaceVariant,
                    ),
                    Text(
                      annule ? 'Relâchez pour annuler' : 'Glissez pour annuler',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
