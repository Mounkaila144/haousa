import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hausa_mobile/theme/brand.dart';
import 'package:hausa_mobile/widgets/brand_app_bar.dart';

void main() {
  testWidgets('toutes les pages affichent le grand logo sans le déformer', (
    WidgetTester tester,
  ) async {
    const BrandAppBar appBar = BrandAppBar(title: 'Confidentialité');
    await tester.pumpWidget(
      MaterialApp(
        theme: buildBrandTheme(),
        home: const Scaffold(appBar: appBar),
      ),
    );

    expect(appBar.preferredSize.height, 128);
    final Image logo = tester.widget<Image>(
      find.byKey(const Key('brand-logo')),
    );
    expect((logo.image as AssetImage).assetName, 'assets/brand/logo.webp');
    expect(logo.width, 224);
    expect(logo.height, 82);
    expect(logo.fit, BoxFit.contain);
    expect(find.text('Confidentialité'), findsOneWidget);
  });
}
