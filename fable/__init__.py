"""fable-collector — marine weather collection & GO/NO-GO window detection.

Collects Open-Meteo forecast + marine data for Tunisian coastal spots,
publishes per-spot JSON feeds on GitHub Pages, and detects safe
"Family GO" outing windows (Transit–Anchor–Transit) for the home port.

© RB Power Consulting. All rights reserved.
"""

__version__ = "2.8.4"
USER_AGENT = f"fable-collector/{__version__} (+github actions)"
