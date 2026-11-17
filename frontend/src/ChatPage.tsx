// The chat page: a question box, then the answer with its [n] markers and a numbered source list.
// Slice 1 of docs/specs/ask-a-rules-question.md: the answer shows once the stream's "answer" event arrives, whole
// (record 0028). Progress lines (slice 2), clickable markers with PDF links (slice 3), refusals (slice 5) and
// error messages (slice 6) come later.

import { EventSourceParserStream } from "eventsource-parser/stream";
import { useState, type FormEvent } from "react";


// ===== The answer, as /chat sends it =====

// The fields of RulesAnswer (answer_flows/shared/answer_shape.py) that the page shows
interface Citation {
  chunk_id: string;
  quote: string;
  source_name: string;
}

interface AnswerSentence {
  is_gap: boolean;
  text: string;
}

interface RulesAnswer {
  refused: boolean;
  answer: string;
  citations: Citation[];
  answer_sentences: AnswerSentence[];
}


// ===== Asking =====

// Posts the question to /chat and returns the answer from the stream's "answer" event, read with eventsource-parser
// (record 0032)
async function askChat(question: string): Promise<RulesAnswer> {
  const response = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });

  // Turn the body into a stream of server-sent events
  if (response.body === null) {
    throw new Error("The /chat response has no body to read");
  }
  const eventReader = response.body
    .pipeThrough(new TextDecoderStream())
    .pipeThrough(new EventSourceParserStream())
    .getReader();

  // Return the first "answer" event. A while loop, because a stream has no length: read until the server closes it
  while (true) {
    const { done, value: event } = await eventReader.read();
    if (done) {
      throw new Error("The /chat stream ended without an answer event");
    }
    if (event.event === "answer") {
      return JSON.parse(event.data) as RulesAnswer;
    }
  }
}


// ===== The page =====

// The whole page: holds the question as typed and the answer once it arrives
export function ChatPage() {
  const [question, setQuestion] = useState("");
  const [rulesAnswer, setRulesAnswer] = useState<RulesAnswer | null>(null);

  // Clears the last answer, then shows the new one when it arrives
  async function askQuestion(event: FormEvent) {
    event.preventDefault();
    setRulesAnswer(null);
    setRulesAnswer(await askChat(question));
  }

  return (
    <main className="chat-page">
      <h1>Badminton rules</h1>
      <form className="question-form" onSubmit={askQuestion}>
        <label htmlFor="question">Your question</label>
        <div className="question-row">
          <input id="question" value={question} onChange={(event) => setQuestion(event.target.value)} />
          <button type="submit">Ask</button>
        </div>
      </form>
      {rulesAnswer !== null && <AnswerWithSources rulesAnswer={rulesAnswer} />}
    </main>
  );
}


// The answer text, then the numbered sources: marker [n] in the text is citations[n - 1]
function AnswerWithSources({ rulesAnswer }: { rulesAnswer: RulesAnswer }) {
  const answerText = rulesAnswer.answer_sentences.map((sentence) => sentence.text).join(" ");

  return (
    <section className="answer" aria-label="Answer">
      <p className="answer-text">{answerText}</p>
      <h2 id="sources-heading">Sources</h2>
      <ol className="sources" aria-labelledby="sources-heading">
        {/* The position is the key, because the list never reorders and a clause can be cited twice */}
        {rulesAnswer.citations.map((citation, i) => (
          <li key={i}>
            <span className="source-number">[{i + 1}]</span>
            <q className="source-quote">{citation.quote}</q>
            <span className="source-name">{citation.source_name}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
