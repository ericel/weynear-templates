# Live Sports Scores

Publishes one native score card per match and updates the same post when the
official provider state changes. An unchanged provider snapshot produces no
post action.

The installer chooses a managed publishing bot and binds `score-posts` to
everyone, the bot's followers, or a saved subscriber/topic audience. The
template never receives subscriber profile IDs.

This entry remains `preview` until the bootstrap source revision is replaced
with a real reviewed commit and the digest-qualified artifact has a valid
signature, SLSA provenance, and SPDX SBOM.
