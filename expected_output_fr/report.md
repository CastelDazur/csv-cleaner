# Rapport de nettoyage : messy_customers.csv

- Encodage : cp1252, séparateur : ';'
- Lignes en entrée : 39
- Lignes en sortie : 36
- Supprimées : 3 (vides/doublons)
- Valeurs modifiées : 171 (voir changes_log.csv)
- À vérifier manuellement : 6

## Lignes supprimées

- ligne 22: ligne vide
- ligne 39: doublon de la ligne 4
- ligne 40: doublon de la ligne 9

## À vérifier manuellement (aucune valeur n'a été devinée)

- ligne 7 (Luc Dubois): e-mail : format invalide
- ligne 11 (Pierre Weber): date : format non reconnu
- ligne 13 (Anna Rossi): pays : absent du référentiel
- ligne 14 (Marco Rossi): montant : valeur non numérique
- ligne 16 (Luc Kovalenko): pays : absent du référentiel
- ligne 19 (Tom Martin): téléphone : format international impossible
