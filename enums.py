from enum import Enum


class Couleur(str, Enum):
    ROUGE = "rouge"
    BLANC = "blanc"
    ROSE = "rose"
    EFFERVESCENT = "effervescent"


class StatutBouteille(str, Enum):
    EN_CAVE = "en_cave"
    BUE = "bue"
