# Regles de numeration Hausa

## Formes canoniques

- zero : `sifili` ; unites : `ɗaya`, `biyu`, `uku`, `huɗu`, `biyar`,
  `shida`, `bakwai`, `takwas`, `tara` ;
- 10 : `goma`; 11--19 : `goma sha <unite>` ;
- dizaines : `ashirin`, `talatin`, `arba'in`, `hamsin`, `sittin`, `saba'in`,
  `tamanin`, `tasa'in` ;
- 21--99 : `<dizaine> da <unite>` ;
- centaines : `ɗari [multiplicateur] [da reste]` ;
- milliers : `jikka [multiplicateur] [da reste]` ;
  `jikka` (k gemine) est la forme retenue pour 1 000 (hausa du Niger).
  `jika` et `dubu` (standard du Nigeria) restent acceptes **en entree** mais
  ne sont jamais produits ;
- grandes echelles : `miliyan`, `biliyan`, `tiriliyan`, suivies du
  multiplicateur et eventuellement de `da` puis du reste.

`tasa'in` est l'unique sortie canonique pour 90. `tasa in`, `tasa’in`,
`tasain`, `tisa'in` et `casa'in` sont seulement des alias d'entree.

## Alias et normalisation

Les apostrophes deviennent `'`, la casse et les espaces sont normalises, et les
alias complets tels que `daya` -> `ɗaya`, `hudu` -> `huɗu`, `dari` ->
`ɗari`, `sifiri` -> `sifili`, `dubu` et `jika` -> `jikka` sont appliques sur des frontieres de mots. Un
mot inconnu n'est jamais modifie par rapprochement flou.

## `sha` et `da`

`sha` n'est admis que pour 11--19, avec ou sans `goma` en entree. `da` compose
les dizaines, les centaines et les groupes d'echelle. Il n'est donc jamais
considere seul comme une addition. Les operateurs explicites (`a ƙara`,
`a hidda`, `sau`, `a raba chi sau`) sont reconnus avant evaluation.

Exemples :

```text
23    ashirin da uku
250   ɗari biyu da hamsin
2523  jikka biyu da ɗari biyar da ashirin da uku
90    tasa'in
99    tasa'in da tara
```
