# Migration de Zarma vers Hausa

La copie Hausa part du commit source `e927aa02fe5de208bc3da39e796e1162c6444f3d`.
Le projet original voisin n'est pas modifie. Un repere Git local
`backup/pre-hausa-20260731-e927aa0` conserve le point de depart.

## Renommages et modifications

- `packages/zarma_numbers` est devenu `packages/hausa_numbers` et son contenu a
  ete remplace par les regles Hausa.
- Les classes, fichiers Flutter, identifiants Android et imports utilisent
  `hausa`/`Hausa`; les contrats JSON utilisent `hausa_text`.
- FastAPI conserve les routes `/health` et `/api/v1/*`, ainsi que le flux de
  consentement, l'historique, le feedback et le stockage audio.
- Le service vocal actif utilise `NCAIR1/Hausa-ASR`; les anciens chemins de
  modele et le decodeur specifique a la langue source ont ete retires.
- La restitution garde l'interface de banque WAV et ajoute une interface TTS
  configurable. Aucun WAV de la langue source n'est actif.

## Fichiers conserves sans changement architectural

Les modeles SQLAlchemy/Alembic, abstractions de stockage, limites de debit,
gestion du consentement, capture micro, navigation et theme Flutter sont
conserves. Les noms linguistiques de colonnes et champs ont ete adaptes dans la
copie; un deploiement avec une base existante doit planifier sa migration de
donnees avant bascule.

## Fichiers retires dans la copie

- corpus, outils d'entrainement et resultats propres a la langue source deja
  absents de la copie initiale ;
- documentation produit et stories devenues linguistiquement fausses ;
- anciens WAV, fixtures ASR et scripts Omnilingual/decodeur contraint.

## Nouveaux composants

- `hausa_numbers.normalize_hausa_text`, `hausa_words_to_number`,
  `number_to_hausa` et `parse_hausa_operation` ;
- `services/asr/app/hausa_asr.py` ;
- messages Hausa centralises et protocole `HausaTtsProvider` ;
- tests Hausa pour les nombres, operations, erreurs et formats audio.

## A valider

Un locuteur Hausa doit valider les variantes d'operateurs, les formulations de
messages vocaux et la convention de rattachement de `da` aux grandes echelles.
Il doit aussi enregistrer/valider la banque TTS avant une publication vocale.
