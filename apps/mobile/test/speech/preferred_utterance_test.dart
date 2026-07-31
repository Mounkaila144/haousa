import 'package:flutter_test/flutter_test.dart';
import 'package:hausa_mobile/speech/voice_bank.dart';

void main() {
  test('préfère la forme parlée complète quand elle existe', () {
    expect(
      preferredUtterance('biyu ƙara uku', 'biyu a ƙara uku'),
      utteranceFromHausa('biyu a ƙara uku'),
    );
  });

  test('sans forme parlée, conserve la forme canonique', () {
    expect(preferredUtterance('ɗari', ''), utteranceFromHausa('ɗari'));
  });
}
