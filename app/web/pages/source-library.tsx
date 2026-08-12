export default function SourceLibrary() {
  return (
    <main data-review-status="review_required">
      <h1>Maine Authority Library</h1>
      <p>Browse official Maine source cards, inspect exact spans, and see whether a source is fresh enough to support current-law language.</p>
      <section data-source-card="visible">Source cards show jurisdiction, authority status, freshness, citation, hash, retrieval date, parser status, and exact span preview.</section>
      <section data-claim-drilldown="answer-to-claim">Answer → claim drilldown is available where answers or drafts are shown.</section>
      <section data-citation-drilldown="claim-to-citation">Claim → citation drilldown is available for every legal assertion.</section>
      <section data-source-text-drilldown="citation-to-source-text">Citation → source text drilldown opens official source text when the external authority store is populated.</section>
      <section data-verifier-result-drilldown="source-text-to-verifier-result">Source text → verifier result drilldown shows citation, quote, claim-support, freshness, and jurisdiction checks.</section>
      <section data-blocked-export-explanation="visible">Blocked exports explain every missing gate: authority, citation, quote, claim, fact, procedure, form, or human review.</section>
      <section data-update-official-sources="available">Use the desktop workbench to run an explicit official-source update with network acknowledgement, fixture mode, and cancel support.</section>
    </main>
  );
}
