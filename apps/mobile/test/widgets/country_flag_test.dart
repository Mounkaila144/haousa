import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hausa_mobile/config/thousand_naming.dart';
import 'package:hausa_mobile/widgets/country_flag.dart';

/// Le drapeau porte le sens pour quelqu'un qui ne lit pas : il doit être
/// réellement **peint**, pas seulement présent dans l'arbre.
///
/// Régression : les bandes étaient construites avec `ColoredBox` dans un
/// `Column` sans `crossAxisAlignment.stretch`. Le Column donne alors des
/// contraintes lâches en largeur, un `ColoredBox` sans enfant s'y effondre à
/// zéro, et le drapeau du Niger ne montrait plus qu'un point orange sur fond
/// blanc. Un test de présence ne voyait rien : les widgets étaient bien là.
void main() {
  Future<void> pumpFlag(WidgetTester tester, ThousandNaming naming) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Center(child: CountryFlag(naming: naming, height: 30)),
        ),
      ),
    );
  }

  /// Surfaces réellement peintes par les bandes du drapeau.
  ///
  /// Restreint aux descendants de [CountryFlag] : le `Scaffold` peint lui aussi
  /// un `ColoredBox` plein écran, qui masquerait un drapeau effondré.
  List<Size> paintedBands(WidgetTester tester) {
    final Finder bands = find.descendant(
      of: find.byType(CountryFlag),
      matching: find.byType(ColoredBox),
    );
    return tester
        .widgetList<ColoredBox>(bands)
        .map((ColoredBox box) => tester.getSize(find.byWidget(box)))
        .toList();
  }

  testWidgets('le Niger peint trois bandes horizontales non vides', (
    tester,
  ) async {
    await pumpFlag(tester, ThousandNaming.jika);

    final List<Size> bands = paintedBands(tester);
    expect(bands, hasLength(3));
    for (final Size band in bands) {
      expect(band.width, greaterThan(0), reason: 'bande effondrée en largeur');
      expect(band.height, greaterThan(0));
    }
    // Bandes horizontales : chacune est plus large que haute.
    expect(bands.every((Size b) => b.width > b.height), isTrue);
  });

  testWidgets('le Nigeria peint trois bandes verticales non vides', (
    tester,
  ) async {
    await pumpFlag(tester, ThousandNaming.dubu);

    final List<Size> bands = paintedBands(tester);
    expect(bands, hasLength(3));
    for (final Size band in bands) {
      expect(band.width, greaterThan(0));
      expect(band.height, greaterThan(0), reason: 'bande effondrée en hauteur');
    }
    // Bandes verticales : chacune est plus haute que large.
    expect(bands.every((Size b) => b.height > b.width), isTrue);
  });

  testWidgets('chaque drapeau garde les proportions de son pays', (
    tester,
  ) async {
    await pumpFlag(tester, ThousandNaming.jika);
    final Size niger = tester.getSize(find.byType(CountryFlag));
    expect(niger.width / niger.height, closeTo(7 / 6, 0.01));

    await pumpFlag(tester, ThousandNaming.dubu);
    final Size nigeria = tester.getSize(find.byType(CountryFlag));
    expect(nigeria.width / nigeria.height, closeTo(2, 0.01));
  });
}
