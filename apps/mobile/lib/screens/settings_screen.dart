import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hausa_mobile/config/thousand_naming.dart';
import 'package:hausa_mobile/widgets/brand_app_bar.dart';
import 'package:hausa_mobile/widgets/brand_footer.dart';

/// Réglages de l'application.
///
/// Un seul réglage aujourd'hui : l'appellation du millier. `jika` et `dubu`
/// désignent le même montant (1 000 F CFA) mais ne se disent pas dans les
/// mêmes régions. Le choix ne porte que sur ce que l'application **dit** —
/// elle continue de comprendre les deux, afin qu'un réglage mal choisi ne
/// rende jamais l'application sourde.
class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ThousandNaming selected = ref.watch(thousandNamingProvider);
    final TextTheme textTheme = Theme.of(context).textTheme;

    return Scaffold(
      key: const Key('settings-screen'),
      appBar: const BrandAppBar(title: 'Paramètres'),
      bottomNavigationBar: const BrandFooter(),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: <Widget>[
            Text('Comment dire 1 000 francs', style: textTheme.titleLarge),
            const SizedBox(height: 8),
            Text(
              'Les deux mots désignent le même montant. Choisissez celui que '
              'vous employez : l’application le dira ainsi. Elle comprendra '
              'l’autre de toute façon.',
              style: textTheme.bodyMedium,
            ),
            const SizedBox(height: 16),
            RadioGroup<ThousandNaming>(
              groupValue: selected,
              onChanged: (ThousandNaming? chosen) {
                if (chosen != null) {
                  ref.read(thousandNamingProvider.notifier).select(chosen);
                }
              },
              child: Column(
                children: <Widget>[
                  for (final ThousandNaming naming in ThousandNaming.values)
                    RadioListTile<ThousandNaming>(
                      key: Key('thousand-naming-${naming.wireValue}'),
                      value: naming,
                      title: Text(naming.label, style: textTheme.titleMedium),
                      subtitle: Text(_exampleFor(naming)),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Exemple parlant : 5 000 F, montant courant au marché.
  String _exampleFor(ThousandNaming naming) {
    return switch (naming) {
      ThousandNaming.jika => '5 000 F se dit « jikka biyar »',
      ThousandNaming.dubu => '5 000 F se dit « dubu biyar »',
    };
  }
}
