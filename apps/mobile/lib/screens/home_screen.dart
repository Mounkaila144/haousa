import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hausa_mobile/config/thousand_naming.dart';
import 'package:hausa_mobile/navigation/app_routes.dart';
import 'package:hausa_mobile/theme/brand.dart';
import 'package:hausa_mobile/widgets/brand_app_bar.dart';
import 'package:hausa_mobile/widgets/brand_footer.dart';
import 'package:hausa_mobile/widgets/country_flag.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      key: const Key('home-screen'),
      appBar: BrandAppBar(
        title: 'Calculatrice Hausa',
        automaticallyImplyLeading: false,
        actions: <Widget>[
          IconButton(
            key: const Key('open-settings-button'),
            icon: const Icon(Icons.settings_outlined),
            tooltip: 'Paramètres',
            onPressed: () => Navigator.of(context).pushNamed(AppRoutes.settings),
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
            final double buttonDiameter = constraints.biggest.shortestSide
                .clamp(220, 260)
                .toDouble();
            return Stack(
              fit: StackFit.expand,
              alignment: Alignment.center,
              children: <Widget>[
                Positioned(
                  top: 16,
                  left: 16,
                  right: 16,
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(16),
                    child: Image.asset(
                      'brand-source/logo.png',
                      key: const Key('home-brand-logo'),
                      fit: BoxFit.fitWidth,
                    ),
                  ),
                ),
                Center(
                  child: Semantics(
                    button: true,
                    label: 'Démarrer un enregistrement audio',
                    child: ExcludeSemantics(
                      child: SizedBox(
                        width: buttonDiameter,
                        height: buttonDiameter,
                        child: FilledButton(
                          key: const Key('start-recording-button'),
                          onPressed: () => Navigator.of(
                            context,
                          ).pushNamed(AppRoutes.recording),
                          style: FilledButton.styleFrom(
                            shape: const CircleBorder(),
                            backgroundColor: BrandColors.blue,
                            elevation: 6,
                          ),
                          child: const Column(
                            mainAxisSize: MainAxisSize.min,
                            children: <Widget>[
                              Icon(Icons.mic, size: 96, color: Colors.white),
                              SizedBox(height: 8),
                              Text(
                                'Enregistrer',
                                style: TextStyle(
                                  fontSize: 24,
                                  fontWeight: FontWeight.w800,
                                  color: Colors.white,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
                Positioned(
                  left: 16,
                  right: 16,
                  bottom: 16,
                  child: Center(child: _CountryPicker()),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

/// Choix du pays — donc de l'appellation du millier prononcée par la voix.
///
/// Niger dit `jika`, Nigeria dit `dubu` ; les deux valent 1 000 F CFA. Le choix
/// ne change **que** ce que l'application dit : elle continue de comprendre les
/// deux mots à l'écoute, afin qu'un drapeau mal choisi ne la rende jamais
/// sourde à son utilisateur.
class _CountryPicker extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ThousandNaming selected = ref.watch(thousandNamingProvider);

    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        child: DropdownButtonHideUnderline(
          child: DropdownButton<ThousandNaming>(
            key: const Key('country-picker'),
            value: selected,
            borderRadius: BorderRadius.circular(12),
            // Le drapeau est le repère ; le nom du pays ne sert qu'à ceux qui
            // lisent, et à la synthèse vocale d'accessibilité.
            items: <DropdownMenuItem<ThousandNaming>>[
              for (final ThousandNaming naming in ThousandNaming.values)
                DropdownMenuItem<ThousandNaming>(
                  key: Key('country-${naming.wireValue}'),
                  value: naming,
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      CountryFlag(naming: naming, height: 26),
                      const SizedBox(width: 10),
                      Text(
                        naming.countryLabel,
                        style: const TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
            ],
            onChanged: (ThousandNaming? chosen) {
              if (chosen != null) {
                ref.read(thousandNamingProvider.notifier).select(chosen);
              }
            },
          ),
        ),
      ),
    );
  }
}
