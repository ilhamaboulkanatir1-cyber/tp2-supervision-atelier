"""Supervision d'un atelier : référentiel des machines, relevés capteurs, alertes et rapport."""
import csv
import json
import math
import re
from datetime import datetime
from pathlib import Path

from exceptions import FichierInvalide, ReleveInvalide

COLONNES = ("machine", "horodatage", "temperature", "vibration")

# Un relevé valide est un tuple : (machine, horodatage, temperature, vibration)
Releve = tuple[str, datetime, float, float]


# --- Étape 1 : le référentiel des machines (JSON, dictionnaires, ensembles) --------------------

def charger_machines(chemin: Path) -> dict[str, dict]:
    """Lit machines.json et renvoie un dictionnaire {identifiant: fiche de la machine}.

    Lève FichierInvalide si un identifiant apparaît deux fois.
    """
    with chemin.open("r", encoding="utf-8") as fichier:
        fiches = json.load(fichier)

    machines = {}

    for fiche in fiches:
        identifiant = fiche["id"]

        if identifiant in machines:
            raise FichierInvalide(
                f"identifiant en double : {identifiant}"
            )

        machines[identifiant] = fiche

    return machines




def ateliers(machines: dict[str, dict]) -> set[str]:
    """L'ensemble des ateliers où se trouvent les machines."""
    return {fiche["atelier"] for fiche in machines.values()}


# --- Étape 3 : valider une ligne (exceptions, tuples) -------------------------------------------
def lire_nombre(texte: str, champ: str, numero: int) -> float:
    """Convertit un texte en nombre et vérifie sa validité."""

    texte_nettoye = texte.strip()

    if not texte_nettoye:
        raise ReleveInvalide("valeur manquante", numero, champ)

    # Accepter la virgule ou le point comme séparateur décimal
    texte_nettoye = texte_nettoye.replace(",", ".")

    try:
        valeur = float(texte_nettoye)
    except ValueError:
        raise ReleveInvalide(
            f"non numérique : '{texte.strip()}'",
            numero,
            champ
        )

    if not math.isfinite(valeur):
        raise ReleveInvalide("valeur non finie", numero, champ)

    return valeur

def parser_releve(brut: dict[str, str], numero: int, machines: dict[str, dict]) -> Releve:
    """Transforme une ligne brute en relevé validé."""

    # 1. Vérifier et nettoyer l'identifiant de la machine
    machine = brut.get("machine", "").strip().upper()

    if not machine:
        raise ReleveInvalide("valeur manquante", numero, "machine")

    if machine not in machines:
        raise ReleveInvalide(
            f"machine inconnue : '{machine}'",
            numero,
            "machine"
        )

    # 2. Vérifier le format de la date
    texte_date = brut.get("horodatage", "").strip()

    try:
        horodatage = datetime.strptime(
            texte_date,
            "%Y-%m-%d %H:%M"
        )
    except ValueError:
        raise ReleveInvalide(
            f"horodatage invalide : '{texte_date}'",
            numero,
            "horodatage"
        )

    # 3. Lire et vérifier la température
    temperature = lire_nombre(
        brut.get("temperature", ""),
        "temperature",
        numero
    )

    # 4. Lire et vérifier la vibration
    vibration = lire_nombre(
        brut.get("vibration", ""),
        "vibration",
        numero
    )

    if vibration < 0:
        raise ReleveInvalide(
            f"vibration négative : '{brut.get('vibration', '')}'",
            numero,
            "vibration"
        )

    # 5. Retourner le relevé sous forme de tuple
    return machine, horodatage, temperature, vibration


# --- Étape 4 : lire le fichier (CSV, générateur, collecte des erreurs) ---------------------------
def lignes_csv(chemin: Path):
    """Produit chaque ligne du CSV avec son numéro."""

    with chemin.open("r", encoding="utf-8-sig", newline="") as fichier:
        lecteur = csv.DictReader(fichier, delimiter=";")

        colonnes = lecteur.fieldnames or []

        for colonne in COLONNES:
            if colonne not in colonnes:
                raise FichierInvalide(
                    f"colonne manquante : {colonne}"
                )

        for numero, ligne in enumerate(lecteur, start=2):
            yield numero, ligne

def lire_releves(
    chemin: Path,
    machines: dict[str, dict]
) -> tuple[list[Releve], list[ReleveInvalide]]:
    """Lit les relevés et collecte les erreurs sans arrêter la lecture."""

    releves = []
    erreurs = []

    for numero, brut in lignes_csv(chemin):
        try:
            releve = parser_releve(brut, numero, machines)
            releves.append(releve)

        except ReleveInvalide as erreur:
            erreurs.append(erreur)

    return releves, erreurs


def ecrire_rejets(
    erreurs: list[ReleveInvalide],
    chemin: Path
) -> None:
    """Écrit les erreurs dans un fichier CSV compatible avec Excel."""

    chemin.parent.mkdir(parents=True, exist_ok=True)

    with chemin.open(
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as fichier:
        writer = csv.writer(fichier, delimiter=";")

        writer.writerow(["ligne", "champ", "message"])

        for erreur in erreurs:
            writer.writerow([
                erreur.ligne,
                erreur.champ,
                erreur.message
            ])

# --- Étape 5 : analyser (dictionnaires, compréhensions) ------------------------------------------
def par_machine(releves: list[Releve]) -> dict[str, list[Releve]]:
    """Regroupe les relevés par machine."""

    groupes = {}

    for releve in releves:
        machine = releve[0]

        if machine not in groupes:
            groupes[machine] = []

        groupes[machine].append(releve)

    return groupes


def moyennes(releves: list[Releve]) -> dict[str, tuple[float, float]]:
    """Calcule les moyennes de température et de vibration."""

    groupes = par_machine(releves)
    resultat = {}

    for machine, liste in groupes.items():
        moyenne_temperature = round(
            sum(r[2] for r in liste) / len(liste),
            1
        )

        moyenne_vibration = round(
            sum(r[3] for r in liste) / len(liste),
            2
        )

        resultat[machine] = (
            moyenne_temperature,
            moyenne_vibration
        )

    return resultat

def alertes(
    releves: list[Releve],
    machines: dict[str, dict]
) -> list[tuple[str, datetime, str]]:
    """Détecte les dépassements des seuils."""

    resultat = []

    for machine, horodatage, temperature, vibration in releves:
        fiche = machines[machine]

        seuil_temperature = fiche["temp_max"]
        seuil_vibration = fiche["vib_max"]

        if temperature > seuil_temperature:
            motif = (
                f"température {temperature} > {seuil_temperature}"
            )

            resultat.append((machine, horodatage, motif))

        if vibration > seuil_vibration:
            motif = (
                f"vibration {vibration} > {seuil_vibration}"
            )

            resultat.append((machine, horodatage, motif))

    resultat.sort(key=lambda alerte: (alerte[1], alerte[0]))

    return resultat


def machines_silencieuses(
    releves: list[Releve],
    machines: dict[str, dict]
) -> set[str]:
    """Retourne les machines sans aucun relevé valide."""

    machines_actives = {releve[0] for releve in releves}

    return set(machines.keys()) - machines_actives

# --- Étape 6 : trier ---------------------------------------------------------------------------
def classement(
    releves: list[Releve],
    machines: dict[str, dict]
) -> list[tuple[str, int]]:
    """Classe toutes les machines selon leur nombre d'alertes."""

    liste_alertes = alertes(releves, machines)

    compteurs = {machine: 0 for machine in machines}

    for machine, horodatage, motif in liste_alertes:
        compteurs[machine] += 1

    resultat = list(compteurs.items())

    resultat.sort(key=lambda element: (-element[1], element[0]))

    return resultat


def top_vibrations(
    releves: list[Releve],
    n: int = 3
) -> list[Releve]:
    """Retourne les n relevés ayant les vibrations les plus élevées."""

    return sorted(
        releves,
        key=lambda releve: releve[3],
        reverse=True
    )[:n]


# --- Étape 7 : le rapport JSON ------------------------------------------------------------------
def construire_rapport(
    releves: list[Releve],
    erreurs: list[ReleveInvalide],
    machines: dict[str, dict]
) -> dict:
    """Construit un rapport compatible avec JSON."""

    moyennes_machines = moyennes(releves)
    liste_alertes = alertes(releves, machines)
    classement_machines = classement(releves, machines)
    silencieuses = machines_silencieuses(releves, machines)
    vibrations = top_vibrations(releves)

    rapport = {
        "releves_valides": len(releves),

        "lignes_rejetees": len(erreurs),

        "moyennes": {
            machine: {
                "temperature": moyenne[0],
                "vibration": moyenne[1]
            }
            for machine, moyenne in moyennes_machines.items()
        },

        "alertes": [
            {
                "machine": machine,
                "heure": horodatage.strftime("%H:%M"),
                "motif": motif
            }
            for machine, horodatage, motif in liste_alertes
        ],

        "classement": [
            machine
            for machine, nombre in classement_machines
            if nombre > 0
        ],

        "machines_silencieuses": sorted(silencieuses),

        "top_vibrations": [
            {
                "machine": releve[0],
                "heure": releve[1].strftime("%H:%M"),
                "vibration": releve[3]
            }
            for releve in vibrations
        ]
    }

    return rapport

def ecrire_rapport(rapport: dict, chemin: Path) -> None:
    """Écrit le rapport au format JSON."""

    chemin.parent.mkdir(parents=True, exist_ok=True)

    with chemin.open("w", encoding="utf-8") as fichier:
        json.dump(
            rapport,
            fichier,
            indent=4,
            ensure_ascii=False
        )

# --- Étape 8 (à la maison) : le journal des événements (expressions régulières) ------------------
MOTIF_EVENEMENT = re.compile(
    r"^\d{4}-\d{2}-\d{2} "
    r"(?P<heure>\d{2}:\d{2}:\d{2}) "
    r"\[(?P<machine>M-\d{2})\] "
    r"(?P<type>DEMARRAGE|ARRET|ALARME) "
    r"code=(?P<code>[A-Z0-9]+)"
    r"(?: duree=(?P<duree>\d+))?$"
)

def lire_evenements(chemin: Path):
    """Lit les événements valides du journal."""

    with chemin.open("r", encoding="utf-8-sig") as fichier:
        for ligne in fichier:
            ligne = ligne.strip()

            correspondance = MOTIF_EVENEMENT.fullmatch(ligne)

            if correspondance is None:
                continue

            donnees = correspondance.groupdict()

            duree = donnees["duree"]

            yield {
                "machine": donnees["machine"],
                "type": donnees["type"],
                "code": donnees["code"],
                "heure": donnees["heure"],
                "duree": int(duree) if duree is not None else None
            }


def temps_arret(evenements) -> dict[str, int]:
    """Calcule la durée totale des arrêts par machine."""

    resultat = {}

    for evenement in evenements:
        if evenement["type"] != "ARRET":
            continue

        duree = evenement["duree"]

        if duree is None:
            continue

        machine = evenement["machine"]

        resultat[machine] = resultat.get(machine, 0) + duree

    return resultat