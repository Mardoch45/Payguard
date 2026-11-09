# Audit PayGuard — PayPal AI Hackathon

Date : 3 novembre 2026. Périmètre : fichiers présents ici, tests locaux et exigences du hackathon fournies dans la conversation. Les règles officielles complètes, les comptes et les livrables éventuellement publiés ailleurs ne sont pas vérifiés.

## Suivi du 5 novembre 2026

Le socle a été commité puis poussé sur [GitHub](https://github.com/Mardoch45/Payguard), branche `main`, commit initial `cc22736`. Le fichier `.env`, l'environnement virtuel et l'audit local sont exclus du dépôt ; les fichiers indexés ont été vérifiés contre les clés locales avant ce commit.

Le chargement d'une facture Sandbox avant l'appel au modèle a ensuite été ajouté localement. Il passe par la politique et l'audit, contrôle l'identifiant retourné et transmet les champs affichés (identifiant, numéro, statut, montant, devise, note) avec la provenance `PAYPAL_DATA`. Les coordonnées structurées du client sont omises. La note remplace le texte externe du scénario, sans modifier les droits de la demande. Un changement de facture ou un échec de rechargement efface le document et le résultat précédents.

**132 tests locaux réussis**, dont le blocage d'un remboursement non demandé proposé à partir d'une note PayPal simulée, le suivi de la source malgré une citation de l'utilisateur seul et la confirmation d'une lecture autorisée. Aucun appel réseau réel n'a été effectué pour cette nouvelle fonction : sa validation contre la facture du participant et Gemini reste à faire. Une lecture de préparation peut avoir eu lieu même si l'action du modèle est ensuite bloquée ; l'interface distingue désormais cette lecture de l'exécution de l'outil proposé.

## Suivi du 4 novembre 2026

Le participant confirme la lecture de sa première facture de test dans l'interface, avec **LLM → PayPal Sandbox → normal-list-001**. Le parcours réel de lecture avec Gemini et PayPal est validé dans son environnement ; il n'a pas été relancé contre les services externes lors de cette mise à jour. La suite locale compte désormais **78 tests réussis**, vérifiés avec `.venv/bin/python -m pytest -q --tb=no`.

La provenance indépendante des citations, la séparation des résultats par cible, le renouvellement des lectures et l'isolation des erreurs du parcours sans protection ont été corrigés. Restent prioritaires les contraintes structurées de demande et la vérification des cibles effectivement exécutées, puis une note réellement chargée depuis PayPal et une opération sensible légitime. Les livrables de soumission restent à terminer.

Les sections suivantes conservent les constats de l'audit initial du 3 novembre ; leur état d'origine doit être lu avec ce suivi et le [plan actualisé](PLAN_DE_TRAVAIL.md).

Complément du 4 novembre : les contraintes structurées de demande sont implémentées et contrôlent montant, devise, bénéficiaire, facture choisie et cible effectivement utilisée (capture ou e-mail). Un blocage ne peut pas être levé par `human_confirmed=True`. Les cibles autorisées sont établies avant l'appel au modèle ; sa proposition n'est plus écrasée par les champs Sandbox. Les montants non finis et fractions de centime USD/EUR sont refusés. La création de facture conserve un brouillon par défaut et les paramètres effectifs sont affichés avant confirmation.

L'évaluation locale comporte désormais 13 scénarios : **8/8 attaques scriptées bloquées**, **5/5 décisions légitimes conformes**. Ces résultats ne mesurent pas Gemini. La vérification porte sur la capture ou l'e-mail explicitement choisis par l'utilisateur ; la correspondance automatique entre le payeur PayPal et l'alias local reste à implémenter.

Vérification finale de ce complément : **117 tests locaux réussis** avec `.venv/bin/python -m pytest -q --tb=short`, y compris le scénario de montant dans l'interface, une capture différente ou absente proposée par le modèle, le blocage malgré confirmation humaine et la création de facture conservée en brouillon. Aucun appel réseau réel n'a été effectué pendant ces corrections.

## Verdict

**L'idée entre dans le périmètre du hackathon. Le prototype local fonctionne. La soumission n'est pas encore prête à être validée.**

PayGuard traite un problème précis : empêcher un agent de gestion de paiements de transformer du texte externe en autorisation financière. PayPal est au centre du projet et l'IA propose des actions structurées. Le moteur de protection peut être déterministe : le règlement fourni n'impose pas que chaque composant utilise de l'IA, ni d'utiliser MCP ou un outil sponsor.

Les principales lacunes sont la preuve d'un parcours avec un vrai modèle et PayPal Sandbox, des contrôles qui ne couvrent pas encore les paramètres réellement exécutés, et les livrables de publication.

## Conformité aux exigences fournies

| Exigence | État constaté | Ce qui manque pour conclure |
|---|---|---|
| Participation : majorité et résidence autorisée | Non vérifiée | Informations du participant et lecture des exclusions des règles officielles |
| Usage significatif de PayPal | Adaptateur REST présent : OAuth, factures, remboursement | Exécution documentée contre la vraie Sandbox |
| Usage significatif d'IA | Client LLM avec appel d'outils présent | Exécution avec le modèle choisi et explication de son rôle |
| Prototype fonctionnel | Oui, en mode scripté et simulateur | Validation du parcours combinant IA et PayPal |
| Démo accessible ou instructions complètes | README avec installation, tests et lancement | Version Python, préparation des objets Sandbox, configuration du modèle et parcours reproductible |
| Dépôt public contenant code et ressources | Aucun dépôt Git utilisable ni lien public trouvé ici | Créer ou identifier le dépôt public et vérifier son contenu |
| Licence open source à la racine | Aucun fichier LICENSE trouvé | Ajouter la licence et vérifier sa détection sur la plateforme |
| Description et outils utilisés | Documentation technique présente | Texte Devpost décrivant le produit final, modèle exact, APIs et limites |
| Vidéo YouTube publique de moins de 3 minutes | Aucun lien ni fichier trouvé ici | Filmer le produit, publier et renseigner le lien |
| Soumission avant clôture | À réaliser | D'après le texte fourni : 12 novembre 2026 à 21 h GMT+1 ; objectif interne : 11 novembre |

Une URL hébergée n'est pas obligatoire si les instructions du dépôt permettent réellement aux juges de lancer le projet. Une simulation est utile pour explorer le produit, mais ne prouve pas seule l'intégration IA et PayPal.

Dans cet environnement, aucun fichier .env n'est présent et la configuration détectée indique PayPal et LLM non configurés. Cela ne prouve pas qu'ils n'ont jamais été testés ailleurs.

## Vérifications réalisées

- Commande `.venv/bin/python -m pytest -q` : **56 tests réussis**.
- Commande `.venv/bin/python -m evaluation.run_eval` : **10 scénarios**, **5/5 attaques bloquées**, **0/5 cas normaux bloqués**, **5/5 décisions normales conformes aux attentes**.
- Interface via `streamlit.testing.v1.AppTest` : les **10 scénarios** et les confirmations affichées ont été exécutés sans exception, avec le simulateur.
- Reproductions locales des limites ci-dessous, sans appel réseau et avec des données fictives.

L'évaluation utilise des actions et contextes écrits dans des fichiers YAML. Elle n'appelle ni le LLM ni PayPal. Les cas normaux « corrects » désignent des décisions attendues, pas des tâches financières réalisées. Ces résultats ne constituent pas un taux de protection général contre les injections.

L'interface a été vérifiée fonctionnellement ; cet audit ne comprend pas d'inspection visuelle dans un navigateur ni de validation de déploiement.

## Corrections prioritaires

### 1. Contrôler la cible effectivement exécutée

La politique compare le bénéficiaire à un alias autorisé (`sandbox-buyer-001`). L'adaptateur crée la facture à partir de `metadata.recipient_email` et rembourse à partir de `metadata.capture_id`. Aucune correspondance de confiance entre ces champs et le bénéficiaire n'est vérifiée.

Reproduction : une facture avec l'alias autorisé et un e-mail distinct reçoit `CONFIRM` ; l'adaptateur transmet cet e-mail au client simulé. Un remboursement avec une capture non vérifiée reçoit aussi `CONFIRM`.

**À corriger :** résoudre comptes et objets dans un contexte contrôlé par l'application, vérifier leur correspondance avec la demande et afficher exactement ces paramètres avant confirmation. Une cible incohérente doit être bloquée même si l'alias déclaré est autorisé.

Un remboursement PayPal retourne au payeur de la capture : il ne permet pas de choisir librement un nouveau bénéficiaire. Le scénario de redirection doit donc utiliser une capture non autorisée ou une autre opération dont la cible est modifiable. `send_money` n'est ni pris en charge par l'adaptateur ni exposé au LLM : ce scénario teste la politique, pas une attaque PayPal exécutable.

Références : [policy.py](guard/policy.py), [paypal.py](adapters/paypal.py).

### 2. Vérifier les paramètres de la demande

`UserRequest.requested_actions` autorise des types d'actions. Le moteur ne compare pas montant, devise ou objet proposés à ceux demandés.

Reproduction : pour une demande de remboursement de 5 USD, une proposition de 15 USD reçoit `CONFIRM`, car elle reste sous le plafond de 20 USD.

**À corriger :** ajouter à la demande des contraintes structurées de montant, devise et objet autorisé. Les définir côté application ou utilisateur ; la proposition du modèle ne doit pas élargir ses propres droits.

Références : [models.py](guard/models.py), [policy.py](guard/policy.py).

### 3. Ne pas confier la provenance de sécurité aux citations du modèle

`build_provenance()` considère les documents cités. Si le modèle cite seulement un document utilisateur connu, le contexte devient fiable même lorsqu'il a reçu une note externe.

Reproduction : documents utilisateur et externe fournis, citation du seul utilisateur → `influenced_by_untrusted_content=False`.

**À corriger :** établir l'exposition aux données externes côté application. Les citations servent à expliquer, pas à prouver l'absence d'influence. Cette limite ne supprime pas les confirmations obligatoires actuelles des opérations sensibles, mais invalide une affirmation de provenance fiable.

Référence : [proposal.py](agent/proposal.py:37).

### 4. Valider la destination Sandbox et les montants

La configuration et le client acceptent toute URL contenant le mot `sandbox`. `https://sandbox.example.test` passe les deux validations, sans être PayPal.

**À corriger :** vérifier HTTPS et l'hôte PayPal Sandbox exact, rejeter les composants inattendus et les redirections vers un autre hôte. La configuration étant locale, cela ne prouve pas une exploitation distante ; cela contredit la garantie « Sandbox uniquement ».

Un montant `NaN` atteint également `CONFIRM` : les comparaisons de plafond ne le bloquent pas. Cela ne signifie pas que PayPal l'accepterait.

**À corriger :** rejeter montants non numériques, non finis et non positifs, puis traiter la précision monétaire correctement.

Références : [settings.py](guard/settings.py:58), [paypal.py](adapters/paypal.py:68), [policy.py](guard/policy.py:132).

### 5. Rendre la comparaison et l'audit fiables

Le parcours sans protection s'exécute avant le parcours protégé dans un même bloc d'erreur. Une erreur du premier peut empêcher d'afficher la décision PayGuard. Le refus humain ne produit pas d'événement dédié ; une exception de l'adaptateur interrompt aussi l'exécution avant l'audit du résultat.

**À corriger :** isoler les deux parcours, journaliser refus et erreurs, distinguer appel tenté et succès, identifier simulation et Sandbox. Pour comparer deux opérations financières réelles, utiliser des objets indépendants : une capture ou une clé d'idempotence commune peut fausser la comparaison.

Le registre d'idempotence est en mémoire et par session de l'interface. Documenter sa portée et vérifier double clic/rejeu dans les conditions de démonstration.

Références : [streamlit_app.py](app/streamlit_app.py:307), [execution.py](guard/execution.py:106), [idempotency.py](guard/idempotency.py).

## Appréciation face aux critères des juges

| Critère | Appréciation fondée sur les éléments locaux | Priorité |
|---|---|---|
| Implémentation | Architecture organisée et tests utiles ; intégration réelle non attestée | Parcours IA → contrôle → PayPal avec paramètres vérifiés |
| Design | Interface de comparaison fonctionnelle, orientée scénarios techniques | Montrer d'abord tâche, action, décision et résultat |
| Impact | Problème précis pour les commerçants utilisant des agents | Montrer une erreur financière évitée et une tâche légitime réussie |
| Innovation | Application pertinente de contrôles d'autorisation ; principe déjà connu | Démontrer les contrôles sur les objets PayPal réels |
| Présentation | Documentation de base ; vidéo non constatée | Démo de moins de 3 minutes montrant le parcours complet |

Pitch proposé : **« PayGuard permet à un commerçant d'utiliser un agent IA sur PayPal sans laisser une note de facture autoriser une opération financière. Chaque proposition est vérifiée contre la demande, puis exécutée, bloquée ou soumise à confirmation, avec une trace explicable. »**

Le détecteur d'injection dédié n'est pas un préalable réglementaire et peut rester hors du MVP. Une attaque réussie contre le modèle n'est pas non plus exigée par le règlement fourni : si le modèle résiste, conserver ce résultat et identifier les propositions scriptées comme telles.

Le calendrier et les critères de livraison sont détaillés dans [PLAN_DE_TRAVAIL.md](PLAN_DE_TRAVAIL.md).
