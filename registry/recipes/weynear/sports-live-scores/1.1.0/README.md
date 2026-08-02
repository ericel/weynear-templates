# Live Sports Scores 1.1

Publishes one native score card per match and updates the same post when the
official provider state changes. An unchanged provider snapshot produces no
post action.

The installer chooses a managed publishing bot, an audience, and a saved
provider credential for live deployments. Raw credentials are stored outside
the catalog and are never passed to the automation script.
