# Breaking News Feed 1.0.0

Publishes newly discovered articles from a reviewed RSS or Atom feed once per
hour. Version 1.0 accepts BBC News feeds hosted at `feeds.bbci.co.uk`; future
versions can add publishers through review rather than exposing an unrestricted
server-side fetcher.

The automation stores only entry fingerprints for deduplication. Each post
contains the article's canonical HTTPS URL and source provenance. The existing
Weynear post service then generates the same Open Graph/link preview used for
ordinary URL posts, so the template does not scrape article pages or duplicate
preview rendering.

Publishers remain responsible for the source feed's terms, attribution, and any
permissions required for their intended use.
