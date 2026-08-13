import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hausa_mobile/config/thousand_naming.dart';
import 'package:hausa_mobile/screens/home_screen.dart';
import 'package:hausa_mobile/widgets/country_flag.dart';

/// Choix du pays sur l'accueil : Niger dit `jika`, Nigeria dit `dubu`.
///
/// Le drapeau est le seul repère utilisable par quelqu'un qui ne lit pas. Ces
/// tests verrouillent surtout le lien pays → mot prononcé : les inverser
/// ferait dire « dubu » à un utilisateur nigérien sans qu'aucune erreur ne
/// soit visible nulle part.
void main() {
  Future<void> pumpHome(WidgetTester tester) async {
    await tester.pumpWidget(
      const ProviderScope(child: MaterialApp(home: HomeScreen())),
    );
    await tester.pump();
  }

  testWidgets('l’accueil propose le choix du pays, drapeau à l’appui', (
    tester,
  ) async {
    await pumpHome(tester);

    expect(find.byKey(const Key('country-picker')), findsOneWidget);
    expect(find.byType(CountryFlag), findsWidgets);
  });

  testWidgets('le Niger est proposé par défaut et dit jika', (tester) async {
    await pumpHome(tester);

    final DropdownButton<ThousandNaming> picker = tester
        .widget<DropdownButton<ThousandNaming>>(
          find.byKey(const Key('country-picker')),
        );
    expect(picker.value, ThousandNaming.jika);
    expect(picker.value!.countryLabel, 'Niger');
    expect(picker.value!.wireValue, 'jika');
  });

  testWidgets('choisir le Nigeria bascule la voix sur dubu', (tester) async {
    late WidgetRef captured;
    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          home: Consumer(
            builder: (BuildContext context, WidgetRef ref, _) {
              captured = ref;
              return const HomeScreen();
            },
          ),
        ),
      ),
    );
    await tester.pump();

    expect(captured.read(thousandNamingProvider), ThousandNaming.jika);

    await tester.tap(find.byKey(const Key('country-picker')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('country-dubu')).last);
    await tester.pumpAndSettle();

    expect(captured.read(thousandNamingProvider), ThousandNaming.dubu);
    expect(captured.read(thousandNamingProvider).wireValue, 'dubu');
  });

  test('chaque pays est lié à une seule appellation, sans doublon', () {
    // Une source de vérité unique : le pays n'est pas un second réglage
    // parallèle, il désigne la même préférence.
    expect(ThousandNaming.jika.countryLabel, 'Niger');
    expect(ThousandNaming.dubu.countryLabel, 'Nigeria');
    expect(
      ThousandNaming.values.map((ThousandNaming n) => n.countryLabel).toSet(),
      hasLength(ThousandNaming.values.length),
    );
  });
}
