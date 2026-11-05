# Plan de livraison — PayGuard

Mis à jour le 4 novembre 2026 après validation de la lecture d'une facture Sandbox par le participant. L'[audit initial](AUDIT_HACKATHON.md) date du 3 novembre.

**Objectif :** soumettre le 11 novembre un prototype reproductible utilisant réellement un modèle IA et PayPal Sandbox. D'après les exigences fournies, clôture le 12 novembre 2026 à 21 h GMT+1, soit 21 h au Bénin. Vérifier l'échéance sur Devpost avant soumission.

## Point de départ vérifié

Le socle existe : moteur, provenance, proxy, confirmation, audit, adaptateurs, client LLM et interface. **117 tests locaux passent**, vérifiés le 4 novembre avec `.venv/bin/python -m pytest -q --tb=short` après ajout des contraintes de demande ; les appels réseau de ces tests sont simulés.

Le participant confirme que sa facture de test apparaît dans PayGuard avec **LLM → PayPal Sandbox → normal-list-001**. Le parcours **Gemini → PayGuard → lecture PayPal Sandbox** est donc validé dans son environnement. Les accès Google AI Studio, l'authentification PayPal, le droit Invoicing et la préparation d'une première facture ne sont plus des prérequis ouverts. Cette validation ne couvre pas encore un remboursement réel ni la lecture d'une note PayPal par le modèle.

Les corrections déjà couvertes par le code et les tests comprennent la provenance des documents externes indépendante des citations, la séparation des résultats simulateur/Sandbox, l'effacement des résultats après changement de réglages, l'isolation des erreurs de comparaison et le renouvellement de chaque lecture. La licence, le dépôt public, la vidéo et l'éligibilité restent à vérifier.

Les anciennes étapes de création du socle sont terminées. Le travail restant concerne les contrôles réels, les intégrations et la livraison.

## Prochaine étape concrète

Les contraintes de demande sont maintenant implémentées : une demande de 5 USD bloque une proposition de 15 USD ; une capture ou une adresse e-mail différente de celle choisie est aussi bloquée. Vérifier dans l'interface **Scripté → Simulateur local → attack-request-amount-001** : décision `BLOCK`, règle `intent.amount_mismatch`, aucun appel à l'adaptateur protégé. Les scénarios `attack-capture-001` et `attack-invoice-recipient-001` montrent aussi les cibles modifiées. Ces propositions sont scriptées.

Le jalon suivant est de charger la note de la facture Sandbox dans le modèle, puis de préparer un paiement capturé pour une démonstration de remboursement légitime. La sélection explicite d'une capture autorise cet objet précis ; la correspondance entre son payeur réel et l'alias local n'est pas encore résolue automatiquement.

Conserver localement l'identifiant de la facture créée pour le prochain parcours de lecture de sa note réelle. Une facture en brouillon ne fournit pas de capture à rembourser : le parcours de remboursement exigera un paiement Sandbox capturé.

## Périmètre du MVP

Public : commerçants déléguant la lecture de factures et les remboursements à un agent IA.

1. L'utilisateur choisit une facture et une tâche, avec des droits définis côté application.
2. L'application lit une facture PayPal Sandbox et marque sa note comme donnée externe.
3. Le modèle reçoit consigne et données, puis propose une action structurée.
4. PayGuard vérifie type d'action, objet, montant, devise et cible effective.
5. Une action interdite est bloquée ; une action sensible admissible attend une confirmation.
6. L'interface montre décision, résultat réel ou simulé et journal.

Trois démonstrations suffisent : lecture légitime ; tentative de remboursement non demandé ; remboursement demandé et confirmé sur une capture autorisée.

Une action fabriquée ou rejouée doit être étiquetée comme telle. Si le modèle refuse l'injection, conserver ce résultat ; ne pas présenter une proposition scriptée comme une attaque réussie contre ce modèle.

MCP, outils sponsors et détecteur supplémentaire sont facultatifs. Garder l'interface et l'architecture existantes.

## Calendrier et validations

| Date | Travail | Condition pour terminer |
|---|---|---|
| **3 novembre** | Vérifier majorité, résidence autorisée et inscription ; identifier le dépôt ; configurer modèle et Sandbox ; préparer factures/captures | Appel réel au modèle et lecture réelle PayPal ; secrets hors du dépôt |
| **4 novembre** | Relier alias, e-mail et capture à des objets de confiance ; contraindre les paramètres par la demande | Demande de 5 USD ne permettant pas 15 USD ; cible ou capture incohérente bloquée |
| **5 novembre** | Provenance côté application, hôte Sandbox exact, montants valides et tests de régression | Citation utilisateur ne masquant pas la note externe ; hôte incorrect et montant non fini refusés ; tests verts |
| **6 novembre** | Charger une note depuis PayPal, obtenir la proposition du LLM, contrôler puis exécuter une opération légitime | Parcours réel IA + PayPal reproductible, résultat Sandbox documenté |
| **7 novembre** | Isoler les colonnes ; identifier simulation/Sandbox ; journaliser refus/erreurs ; vérifier confirmations et rejeux | Erreur de comparaison ne masquant pas PayGuard ; refus audité ; pas de double opération dans le parcours testé |
| **8 novembre** | Campagne d'essais avec le modèle ; présentation centrée sur le commerçant | Résultats précisant modèle, cas, répétitions et limites ; trois démonstrations claires |
| **9 novembre** | README, version Python, dépendances testées, licence, exemples et procédure Sandbox ; dépôt public | Installation neuve réussie à partir du README ; dépôt complet et public |
| **10 novembre** | Vidéo de 2 min 40 à 2 min 50 sur YouTube ; description et outils Devpost | Liens publics accessibles ; fonctionnement réel montré ; fiche prête |
| **11 novembre** | Vérifier liens et parcours documenté ; terminer et soumettre sur Devpost | Confirmation de soumission |
| **12 novembre** | Marge pour un problème bloquant avant la clôture | Aucune fonctionnalité nouvelle mettant la livraison en risque |

Les accès du participant conditionnent les premières étapes. Les dates sont des objectifs, pas des actions déjà réalisées.

## Répartition proposée si vous travaillez à deux

**Protection :** contraintes de demande, politique, provenance, tests de régression, évaluation et limites documentées.

**Intégration :** comptes et objets Sandbox, client LLM, notes provenant de PayPal, confirmation et interface, preuve du parcours réel.

**Ensemble :** revue du parcours le 6 novembre, installation propre le 9, vidéo et soumission les 10 et 11. Chaque membre doit pouvoir expliquer IA, APIs PayPal et garanties effectivement testées.

## Corrections à suivre

- [x] Vérifier l'e-mail ou la capture effectivement utilisés contre la cible choisie par l'utilisateur.
- [ ] Résoudre automatiquement le payeur de la capture et sa correspondance avec l'alias local.
- [x] Contraindre montant, devise, facture choisie et capture par la demande utilisateur.
- [x] Établir l'exposition aux documents externes indépendamment des citations du LLM.
- [ ] Vérifier HTTPS et l'hôte PayPal Sandbox exact ; empêcher les redirections vers un autre hôte.
- [x] Rejeter les montants non finis/invalides et les fractions de centime pour USD/EUR.
- [ ] Charger au moins une note réelle depuis PayPal.
- [x] Isoler les erreurs des parcours avec et sans protection.
- [ ] Journaliser refus humains et erreurs en distinguant tentative et succès.
- [x] Afficher les paramètres effectifs lors de la confirmation.
- [ ] Utiliser des objets distincts pour comparer deux opérations financières réelles.
- [ ] Vérifier double clic/rejeu et documenter le registre d'idempotence en mémoire.
- [x] Identifier scénarios scriptés, propositions du LLM, simulateur et Sandbox.

Un remboursement PayPal retourne au payeur de la capture. Une « redirection du bénéficiaire » doit donc être testée via un objet non autorisé ou une opération dont la cible est réellement modifiable. Le scénario local send_money ne prouve pas une opération exécutable par cet adaptateur.

## Évaluation suffisante pour le dossier

Conserver les 13 scénarios locaux comme tests du moteur (8 attaques et 5 cas légitimes). Ajouter une petite campagne avec le modèle choisi, par exemple 10 cas couvrant lectures ordinaires, notes légitimes et tentatives de changement d'action, d'objet ou de montant, répétés au moins 3 fois si le budget le permet.

Enregistrer : modèle/date, consigne, document/provenance, proposition réelle, décision, confirmation éventuelle, appel tenté, résultat et durée. Exclure secrets et données personnelles des éléments publiés.

Rapporter séparément :

- propositions non autorisées produites par le LLM ;
- propositions non autorisées bloquées par PayGuard ;
- actions légitimes autorisées/confirmées et tâches effectivement réussies ;
- erreurs ou absences d'appel d'outil du modèle ;
- résultats du moteur sur les cas scriptés.

Une proposition non autorisée n'est pas un paiement réalisé. Réserver les opérations Sandbox à des parcours dédiés ; les autres essais peuvent vérifier la décision sans exécuter d'opération, en le déclarant.

## Définition de « prêt à soumettre »

- [ ] Éligibilité et inscription vérifiées contre les règles officielles.
- [ ] Dépôt public complet avec licence à sa racine et licence détectée par la plateforme.
- [ ] README précisant Python 3.11 ou supérieur, installation, configuration, objets Sandbox et lancement.
- [ ] Mode local immédiatement utilisable et procédure complète pour le parcours réel.
- [ ] Modèle/service réellement utilisé et APIs PayPal identifiés dans README et Devpost.
- [ ] Parcours réel IA + PayPal documenté ; opération légitime et comportement de protection démontrés.
- [ ] Tests réussis après corrections et installation vérifiée dans un environnement neuf.
- [ ] Résultats avec protocole, taille d'échantillon et limites.
- [ ] Vidéo YouTube publique de **moins de 3 minutes**, fonctionnement réel et éléments tiers autorisés.
- [ ] Description Devpost : problème, public, fonctionnalités, innovation, outils, progrès pendant le hackathon et limites.
- [ ] Liens vérifiés sans connexion et soumission confirmée le 11 novembre.

Un dépôt avec des instructions complètes suffit pour l'accès des juges ; l'hébergement reste optionnel. En cas d'hébergement, afficher le mode actif et contrôler les accès aux opérations d'une Sandbox partagée.

## Déroulé de la vidéo — 2 min 45

| Temps | Contenu |
|---|---|
| 0:00–0:20 | Commerçant, tâche et risque d'une note externe |
| 0:20–0:50 | Facture PayPal et proposition IA ; identifier toute simulation |
| 0:50–1:25 | Action non autorisée bloquée, règle et absence d'exécution financière |
| 1:25–2:10 | Remboursement légitime : montant/capture, confirmation, résultat Sandbox |
| 2:10–2:35 | Audit et résultats mesurés avec taille de l'échantillon |
| 2:35–2:45 | Bénéfice concret et limite principale |

## Si le planning se tend

Priorités : parcours réel IA + PayPal, exactitude des contrôles présentés, lancement reproductible, dépôt public/licence, vidéo et soumission.

Réduire d'abord nombre de scénarios, statistiques secondaires, détecteur et hébergement. Conserver les résultats honnêtes, même si le modèle résiste aux attaques. Si la Sandbox ne fonctionne pas le 6 novembre, traiter cette intégration en priorité : un simulateur seul ne prouve pas l'intégration demandée.
