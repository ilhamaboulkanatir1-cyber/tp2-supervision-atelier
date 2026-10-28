class AtelierError(Exception):
    """Erreur générale liée à la supervision de l'atelier."""
    pass


class FichierInvalide(AtelierError):
    """Erreur liée à un fichier invalide."""
    pass


class ReleveInvalide(AtelierError):
    """Erreur liée à un relevé invalide."""

    def __init__(self, message: str, ligne: int, champ: str):
        self.message = message
        self.ligne = ligne
        self.champ = champ

        super().__init__(
            f"ligne {ligne}, champ '{champ}' : {message}"
        )