import 'package:flutter/material.dart';
import 'package:hausa_mobile/config/thousand_naming.dart';

/// Drapeau du pays associé à une appellation du millier.
///
/// Dessiné, et non pris dans une police emoji : sur plusieurs surcouches
/// Android les drapeaux emoji retombent sur les deux lettres du code pays
/// (« NE », « NG »). Pour un utilisateur qui ne lit pas, ce repli ne veut
/// strictement rien dire — c'est justement le drapeau qui porte le sens ici.
class CountryFlag extends StatelessWidget {
  const CountryFlag({super.key, required this.naming, this.height = 24});

  final ThousandNaming naming;
  final double height;

  static const Color _nigerOrange = Color(0xFFE05206);
  static const Color _nigerGreen = Color(0xFF0DB02B);
  static const Color _nigeriaGreen = Color(0xFF008751);

  @override
  Widget build(BuildContext context) {
    // Proportions officielles : 6:7 pour le Niger, 1:2 pour le Nigeria.
    final double width = switch (naming) {
      ThousandNaming.jika => height * 7 / 6,
      ThousandNaming.dubu => height * 2,
    };
    return Semantics(
      label: 'Drapeau du ${naming.countryLabel}',
      child: ExcludeSemantics(
        child: SizedBox(
          width: width,
          height: height,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(2),
            child: DecoratedBox(
              decoration: BoxDecoration(
                border: Border.all(color: Colors.black26, width: 0.5),
              ),
              child: switch (naming) {
                ThousandNaming.jika => _niger(),
                ThousandNaming.dubu => _nigeria(),
              },
            ),
          ),
        ),
      ),
    );
  }

  /// Trois bandes horizontales, disque orange centré sur la bande blanche.
  Widget _niger() {
    return Stack(
      fit: StackFit.expand,
      children: <Widget>[
        // `stretch` est indispensable : par defaut un Column donne des
        // contraintes LACHES en largeur, et un ColoredBox sans enfant s'y
        // effondre a zero — le drapeau ne montrait plus que le disque.
        const Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Expanded(child: ColoredBox(color: _nigerOrange)),
            Expanded(child: ColoredBox(color: Colors.white)),
            Expanded(child: ColoredBox(color: _nigerGreen)),
          ],
        ),
        Center(
          child: SizedBox(
            width: height / 3.4,
            height: height / 3.4,
            child: const DecoratedBox(
              decoration: BoxDecoration(
                color: _nigerOrange,
                shape: BoxShape.circle,
              ),
            ),
          ),
        ),
      ],
    );
  }

  /// Trois bandes verticales, vert-blanc-vert.
  Widget _nigeria() {
    // Meme raison que pour le Niger : sans `stretch`, les bandes verticales
    // n'auraient aucune hauteur.
    return const Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Expanded(child: ColoredBox(color: _nigeriaGreen)),
        Expanded(child: ColoredBox(color: Colors.white)),
        Expanded(child: ColoredBox(color: _nigeriaGreen)),
      ],
    );
  }
}
