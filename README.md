# PayGuard

Pare-feu transactionnel expérimental pour agents IA utilisant PayPal Sandbox.

## État actuel

Le socle local de PayGuard est opérationnel et reste indépendant du modèle IA :

- contrat de données pour les demandes, actions et décisions ;
- politique YAML avec blocage par défaut ;
- contrôles d'intention, montant, devise, cible effective et idempotence ;
- provenance des données externes ;
- journal d'audit JSONL sans secrets ;
- proxy d'exécution avec confirmation humaine ;
- huit attaques et cinq cas légitimes automatisés.

Le périmètre d'intégration est désormais présent :

- adaptateur **PayPal Sandbox** (OAuth, factures, remboursement) ;
- **agent minimal** branché sur un LLM compatible API OpenAI ;
- configuration par défaut **Gemini via Google AI Studio** ;
- **mode scripté** qui rejoue les scénarios sans clé LLM ni identifiants ;
- **interface Streamlit** qui montre la même action sans puis avec PayGuard ;
- adaptateur local qui simule PayPal et prouve qu'une action bloquée n'est
  jamais exécutée.

Le 4 novembre 2026, le participant a confirmé la lecture de sa première facture
avec Gemini et PayPal Sandbox dans l'interface. Les tests locaux utilisent des
réponses simulées et ne remplacent pas cette validation du parcours réel.

Les paramètres autorisés sont définis côté application dans
`UserRequest.constraints`. Une différence de montant, devise, bénéficiaire,
capture, e-mail ou facture choisie est bloquée avant la confirmation humaine.
Les cibles Sandbox sont choisies par l'utilisateur avant l'appel au modèle ;
elles ne remplacent pas sa proposition après coup. Cela vérifie la cible
explicitement autorisée, sans attester automatiquement l'identité du payeur
d'une capture à partir de l'alias local.

Ce qui reste ouvert : chargement d'une note réelle depuis PayPal, démonstration d'une
opération sensible légitime, campagne d'évaluation du modèle, licence, vidéo et
soumission. Le détecteur d'injection dédié reste facultatif.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

## Configuration

| Variable | Rôle |
|---|---|
| `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` | Identifiants de l'application sandbox |
| `PAYPAL_BASE_URL` | URL PayPal ; doit contenir `sandbox`, sinon PayGuard refuse de démarrer |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | Modèle compatible API OpenAI (facultatif) |
| `PAYGUARD_AUDIT_PATH` | Journal d'audit JSONL (défaut `data/audit.jsonl`) |

Sans identifiants, la démonstration reste utilisable : le simulateur local et
l'agent scripté ne font aucun appel réseau.

### Gemini avec Google AI Studio

1. Ouvrir [Google AI Studio](https://aistudio.google.com/apikey), puis créer
   une clé API dans un projet utilisant le **Free Tier**. Ne pas activer la
   facturation pour ce prototype si aucun budget n'est prévu.
2. Dans le fichier `.env` local, renseigner les trois variables suivantes :

   ```dotenv
   LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
   LLM_MODEL=gemini-3.5-flash-lite
   LLM_API_KEY=remplacer_par_la_cle_google_ai_studio
   ```

   Conserver les identifiants PayPal déjà enregistrés. Ne pas publier la clé.
3. Lancer ou redémarrer l'application :

   ```bash
   .venv/bin/streamlit run app/streamlit_app.py
   ```

4. Sélectionner **LLM**, **Simulateur local** et le scénario
   **normal-list-001**, puis cliquer sur **Exécuter le scénario**.
   Cela vérifie une proposition réelle du modèle sans opération PayPal.
   Une fois cet essai réussi, choisir **PayPal Sandbox** pour vérifier aussi
   la lecture des factures du compte de test.

Google documente les appels d'outils via son
[endpoint compatible OpenAI](https://ai.google.dev/gemini-api/docs/openai).
Au 3 novembre 2026, [Gemini 3.5 Flash-Lite est proposé en Free Tier](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite)
pour les entrées et sorties. Les quotas et l'accès effectif dépendent du projet
et du compte ; l'accès gratuit n'est pas illimité. Le client n'effectue aucun
repli automatique vers un fournisseur ou un modèle payant.

Si le service répond **429**, attendre puis vérifier les quotas dans AI Studio.
Pour **503**, le service est temporairement indisponible : réessayer plus tard.
Pour **401/403**, vérifier la clé et les autorisations du projet ; pour **404**,
vérifier le nom du modèle disponible et l'URL. La validation par tests locaux
utilise des réponses simulées ; elle ne remplace pas un essai avec une vraie clé.

Le client conserve la compatibilité avec les autres services acceptant
`/chat/completions` et les appels d'outils, en modifiant les variables `LLM_*`.

### Permission PayPal Invoicing

La lecture des factures exige le droit **Invoicing** sur l'application
**Sandbox** correspondant aux identifiants de `.env`. Après activation de ce
droit, redémarrer Streamlit pour renouveler le client et son jeton local.

Le client demande les nouveaux jetons OAuth avec `ignoreCache=true` : cela
évite qu'un ancien jeton conservé par PayPal masque les permissions récemment
activées. Le jeton est ensuite réutilisé localement jusqu'à son renouvellement.
Une liste de factures vide est un résultat valide pour un compte de test neuf.

### Créer une première facture de test

1. Dans [Sandbox Accounts](https://developer.paypal.com/dashboard/accounts),
   identifier le compte **Business** lié à l'application PayGuard et récupérer
   ses identifiants de connexion de test via **View/Edit Account**. Relever
   aussi l'adresse e-mail d'un compte **Personal** de test pour le destinataire.
2. Se connecter à [PayPal Sandbox](https://www.sandbox.paypal.com) avec le compte
   Business de test, puis ouvrir la facturation (**Invoicing**).
3. Créer une facture de **15 USD**, avec le destinataire de test et un article
   « Prestation de démonstration PayGuard ». Enregistrer comme **brouillon**.
4. Dans PayGuard, sélectionner **LLM**, **PayPal Sandbox**, **normal-list-001**,
   puis exécuter le scénario pour consulter les factures du compte.

Les factures du compte PayPal réel sont distinctes des factures Sandbox.
Chaque lecture autorisée consulte à nouveau l'adaptateur : une ancienne liste
vide n'est pas conservée par le registre d'idempotence. La protection contre
les doubles exécutions reste active pour les opérations qui modifient PayPal.

### Vérifier un montant modifié par l'agent

1. Recharger l'interface, choisir **Scripté (hors-ligne)** et **Simulateur local**.
2. Sélectionner **attack-request-amount-001**, puis **Exécuter le scénario**.
3. Vérifier : demande de **5 USD**, proposition de **15 USD**, décision **BLOCK**
   avec la règle `intent.amount_mismatch`, aucun appel à l'adaptateur protégé.

Le montant proposé reste sous le plafond global de 20 USD, mais ne correspond
pas à la demande. Le blocage précède toute confirmation humaine. Il s'agit
d'une proposition scriptée de test, pas d'un résultat mesuré avec Gemini.
Les scénarios **attack-capture-001** et **attack-invoice-recipient-001** vérifient
également une cible différente malgré un alias de bénéficiaire autorisé.

## Tests

```bash
python -m pytest -q
```

## Évaluation locale

```bash
python -m evaluation.run_eval
```

Les chiffres affichés portent uniquement sur les scénarios locaux présents dans
`attacks/`. Ils ne constituent pas encore une mesure d'un agent réel branché sur
PayPal.

## Démonstration

```bash
streamlit run app/streamlit_app.py
```

L'interface affiche deux colonnes pour la même action : sans protection
(l'agent appelle PayPal directement) puis avec PayGuard (décision, règle
déclenchée, confirmation humaine, journal d'audit).

- Mode **scripté** : rejoue un scénario de `attacks/`. Les chiffres obtenus ne
  sont pas une mesure du LLM.
- Mode **LLM** : le modèle lit la consigne et une note externe non fiable, puis
  propose un outil. La décision porte sur sa proposition réelle : un scénario
  d'attaque peut conduire à une lecture admissible si le modèle ne propose pas
  d'opération financière. Les résultats attendus des scénarios scriptés ne sont
  affichés qu'en mode scripté.
- Les documents externes reçus sont suivis côté application, même si le modèle
  cite uniquement l'utilisateur. Avec la politique actuelle, leur présence
  exige une confirmation ; elle ne prouve pas qu'une injection a réussi.
- Un changement d'agent, de cible ou de paramètres retire le résultat précédent
  de l'écran. Les résultats d'idempotence du simulateur et de la Sandbox sont
  conservés séparément.
- Colonne **sans protection** : simulée par défaut. La désactiver envoie
  réellement l'action à la cible choisie.
- Cible **PayPal Sandbox** : exige un `capture_id` (remboursement) ou un
  `invoice_id` (lecture), saisis dans la barre latérale, car la sandbox
  travaille sur des objets réels de test.
- Les opérations sensibles exigent un montant, une devise, un bénéficiaire et
  une cible explicitement autorisés. Les valeurs locales fictives ne sont pas
  utilisées pour autoriser une opération Sandbox lorsque les champs sont vides.
  Pour une lecture ciblée, fournir l'identifiant de la facture choisie.
- La création d'une facture prépare un **brouillon** par défaut. Son envoi exige
  une autorisation distincte dans les contraintes de la demande.

## Contrat d'intégration

Le point d'entrée commun est `guard.execution.process_action()`. L'agent fournit
une `ProposedAction`, puis le proxy :

1. demande une décision au moteur de politique ;
2. arrête immédiatement une action `BLOCK` ;
3. attend un choix humain pour `CONFIRM` ;
4. applique l'idempotence ;
5. appelle l'adaptateur uniquement si l'action est autorisée ;
6. écrit le résultat dans le journal d'audit.

L'agent retourne un `AgentProposal` (`agent/models.py`) : action proposée,
provenance des documents cités et justification.

Les contraintes de la demande proviennent des champs `constraints` des
scénarios et, pour les cibles Sandbox, du choix de l'utilisateur. Ne jamais les
construire à partir de la proposition du modèle. Pour les montants USD/EUR,
la politique refuse valeurs non finies, non positives ou fractions de centime
et compare les valeurs décimales sans arrondir un montant non autorisé.

## Sécurité

- PayPal Sandbox uniquement : le client et la configuration rejettent toute URL
  non sandbox.
- Aucun secret dans le dépôt ; `.env` est ignoré par Git.
- Toute action inconnue ou non demandée est bloquée par défaut.
- Le journal d'audit refuse les champs ressemblant à des secrets.
