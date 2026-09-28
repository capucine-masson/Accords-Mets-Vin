from enum import Enum


class Couleur(str, Enum):
    ROUGE = "rouge"
    BLANC = "blanc"
    ROSE = "rose"
    EFFERVESCENT = "effervescent"


class StatutBouteille(str, Enum):
    EN_CAVE = "en_cave"
    BUE = "bue"


COULEUR_LABELS = {
    Couleur.ROUGE.value: "Rouges",
    Couleur.BLANC.value: "Blancs",
    Couleur.EFFERVESCENT.value: "Effervescents",
    Couleur.ROSE.value: "Rosés",
}
