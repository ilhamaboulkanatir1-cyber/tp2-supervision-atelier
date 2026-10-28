"""Programme principal : supervision de l'atelier."""

from pathlib import Path

from atelier import (
    charger_machines,
    construire_rapport,
    ecrire_rapport,
    ecrire_rejets,
    lire_releves
)

from exceptions import AtelierError


ICI = Path(__file__).parent
DONNEES = ICI / "donnees"
SORTIES = ICI / "sorties"


def main() -> int:
    """Renvoie 0 si tout s'est bien passé, 1 en cas d'erreur de fichier."""

    try:
        machines = charger_machines(DONNEES / "machines.json")

        releves, erreurs = lire_releves(
            DONNEES / "releves.csv",
            machines
        )

        SORTIES.mkdir(parents=True, exist_ok=True)

        ecrire_rejets(
            erreurs,
            SORTIES / "rejets.csv"
        )

        rapport = construire_rapport(
            releves,
            erreurs,
            machines
        )

        ecrire_rapport(
            rapport,
            SORTIES / "rapport.json"
        )

        print(
            f"{len(releves)} relevés valides, "
            f"{len(erreurs)} lignes rejetées"
        )

        silencieuses = rapport["machines_silencieuses"]

        if silencieuses:
            print("Sans relevé : " + ", ".join(silencieuses))

        return 0

    except (AtelierError, OSError) as erreur:
        print(f"Erreur : {erreur}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())