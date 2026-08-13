import 'package:flutter/material.dart';
import 'package:hausa_mobile/theme/brand.dart';

/// Pied de page de marque : présent sur chaque écran, toujours visible sans
/// scroller (`bottomNavigationBar`, pas le corps de page).
///
/// L'utilisateur cible ne lit pas — mais le commanditaire, lui, doit être
/// identifiable par quiconque regarde l'écran : logo PTR Niger, mention et
/// numéro de contact.
class BrandFooter extends StatelessWidget {
  const BrandFooter({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      key: const Key('brand-footer'),
      decoration: BoxDecoration(
        gradient: brandGradient,
        border: Border(
          top: BorderSide(
            color: BrandColors.blueLight.withValues(alpha: 0.75),
            width: 2,
          ),
        ),
        boxShadow: <BoxShadow>[
          BoxShadow(
            color: BrandColors.navy.withValues(alpha: 0.28),
            blurRadius: 18,
            offset: const Offset(0, -4),
          ),
        ],
      ),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      child: SafeArea(
        top: false,
        child: Row(
          children: <Widget>[
            Image.asset('assets/brand/ptr_niger.webp', height: 28),
            const SizedBox(width: 8),
            const Expanded(
              child: Text(
                'Fait par PTR Niger',
                style: TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w600,
                  fontSize: 13,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
            const SizedBox(width: 6),
            const Icon(
              Icons.call_rounded,
              color: BrandColors.blueLight,
              size: 16,
            ),
            const SizedBox(width: 4),
            const Text(
              '+227 70 21 21 12',
              key: Key('brand-footer-phone'),
              style: TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w700,
                fontSize: 13,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
