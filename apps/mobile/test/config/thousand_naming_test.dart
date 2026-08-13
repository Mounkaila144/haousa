import 'package:flutter_test/flutter_test.dart';
import 'package:hausa_mobile/config/thousand_naming.dart';

/// `jika` et `dubu` désignent le même montant : seul le mot dit change.
void main() {
  test('la valeur par défaut est jika, forme du hausa du Niger', () {
    expect(defaultThousandNaming, ThousandNaming.jika);
    expect(defaultThousandNaming.wireValue, 'jika');
  });

  test('une valeur inconnue ou absente retombe sur le défaut', () {
    expect(ThousandNaming.fromWire(null), defaultThousandNaming);
    expect(ThousandNaming.fromWire(''), defaultThousandNaming);
    expect(ThousandNaming.fromWire('zambar'), defaultThousandNaming);
  });

  test('les deux appellations ont une valeur transmissible distincte', () {
    expect(ThousandNaming.fromWire('jika'), ThousandNaming.jika);
    expect(ThousandNaming.fromWire('dubu'), ThousandNaming.dubu);
    expect(
      ThousandNaming.values.map((ThousandNaming n) => n.wireValue).toSet(),
      <String>{'jika', 'dubu'},
    );
  });
}
