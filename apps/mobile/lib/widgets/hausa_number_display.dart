import 'package:flutter/material.dart';
import 'package:hausa_mobile/theme/brand.dart';

/// Affiche un nombre reconnu — gros et seul (partagé entre écrans).
///
/// L'utilisateur cible ne lit pas : la forme hausa n'est **jamais** affichée
/// à l'écran, seulement dite (voir `HausaSpeaker`). Ce widget ne montre donc
/// que le chiffre, en aussi grand que possible.
class HausaNumberDisplay extends StatelessWidget {
  const HausaNumberDisplay({super.key, this.number});

  final int? number;

  @override
  Widget build(BuildContext context) {
    return Text(
      number?.toString() ?? '—',
      style: Theme.of(context).textTheme.displayLarge?.copyWith(
        fontWeight: FontWeight.w800,
        color: BrandColors.navy,
      ),
    );
  }
}
