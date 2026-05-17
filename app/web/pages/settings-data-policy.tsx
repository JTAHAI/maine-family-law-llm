export default function SettingsDataPolicy() {
  return (
    <main data-review-status="review_required">
      <h1>Settings / Data Policy</h1>
      <p>Data boundaries and private training controls.</p>
      <section data-source-card="visible">Source cards show jurisdiction, authority status, freshness, citation, and quote span availability.</section>
      <section data-claim-drilldown="answer-to-claim">Answer → claim drilldown is available where answers or drafts are shown.</section>
      <section data-citation-drilldown="claim-to-citation">Claim → citation drilldown is available for every legal assertion.</section>
      <section data-source-text-drilldown="citation-to-source-text">Citation → source text drilldown opens official source text when the external authority store is populated.</section>
      <section data-verifier-result-drilldown="source-text-to-verifier-result">Source text → verifier result drilldown shows citation, quote, claim-support, freshness, and jurisdiction checks.</section>
      <section data-blocked-export-explanation="visible">Blocked exports explain every missing gate: authority, citation, quote, claim, fact, procedure, form, or human review.</section>
    </main>
  );
}
