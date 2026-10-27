"""Reine, ohne GTK testbare Berechnungen für das Overlay."""


def position_koordinaten(rechteck, breite, hoehe, position, abstand):
    x_mitte = rechteck.x + (rechteck.width - breite) // 2
    if position == "oben_mitte":
        return x_mitte, rechteck.y + abstand
    y = rechteck.y + rechteck.height - hoehe - abstand
    if position == "unten_links":
        return rechteck.x + abstand, y
    if position == "unten_rechts":
        return rechteck.x + rechteck.width - breite - abstand, y
    return x_mitte, y
