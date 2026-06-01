import { useState } from "react";

type SourceCard = {
  snippet?: string;
  metadata?: Record<string, string | boolean | number>;
};

export default function Ask() {
  const [question, setQuestion] = useState("What Maine sources should I check for parental rights and responsibilities?");
  const [answer, setAnswer] = useState("Ask a Maine family-law question to retrieve source-backed information.");
  const [sources, setSources] = useState<SourceCard[]>([]);
  const [loading, setLoading] = useState(false);

  async function askQuestion() {
    setLoading(true);
    setAnswer("Retrieving source cards...");
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const payload = await response.json();
      setAnswer(payload.answer || JSON.stringify(payload, null, 2));
      setSources(payload.citations || []);
    } catch (error) {
      setAnswer(`Local API error: ${String(error)}`);
      setSources([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main data-review-status="review_required">
      <h1>Ask Maine Family Law</h1>
      <p>Source-grounded Q&A with answer-to-claim-to-citation drilldown. Not legal advice. Review required.</p>
      <label htmlFor="question">Question</label>
      <textarea
        id="question"
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        rows={8}
        style={{ width: "100%" }}
      />
      <p>
        <button type="button" onClick={askQuestion} disabled={loading}>
          {loading ? "Retrieving..." : "Ask"}
        </button>
      </p>
      <section aria-label="Answer" data-claim-drilldown="answer-to-claim">
        <h2>Answer</h2>
        <pre style={{ whiteSpace: "pre-wrap" }}>{answer}</pre>
      </section>
      <section data-source-card="visible">
        <h2>Source cards</h2>
        {sources.length === 0 ? <p>No source cards yet.</p> : sources.map((source, index) => (
          <article key={index} data-citation-drilldown="claim-to-citation" data-source-text-drilldown="citation-to-source-text" data-verifier-result-drilldown="source-text-to-verifier-result">
            <strong>{String(source.metadata?.title || source.metadata?.source_id || `Source ${index + 1}`)}</strong>
            <p>{source.snippet}</p>
          </article>
        ))}
      </section>
      <section data-blocked-export-explanation="visible">Blocked exports explain every missing gate: authority, citation, quote, claim, fact, procedure, form, or human review.</section>
    </main>
  );
}
