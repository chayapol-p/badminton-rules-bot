// The chat page: a question box, then the answer with its [n] markers and a numbered source list.
// Slices 1 and 2 of docs/specs/ask-a-rules-question.md: the steps show as they arrive, and the answer shows once the
// stream's "answer" event arrives, whole (record 0028); then the steps fold into one line (record 0033).
// Clickable markers with PDF links (slice 3), refusals (slice 5) and error messages (slice 6) come later.

import { EventSourceParserStream } from "eventsource-parser/stream";
import { useEffect, useRef, useState, type FormEvent } from "react";


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

// The fields of ProgressUpdate (answer_flows/shared/progress_updates.py) that the page shows
interface ProgressUpdate {
  step: string;
  message: string;
}


// ===== Asking =====

// Posts the question to /chat, hands each "progress" event to onProgress as it comes, and returns the answer from the
// stream's "answer" event, read with eventsource-parser (record 0032)
async function askChat(question: string, onProgress: (update: ProgressUpdate) => void): Promise<RulesAnswer> {
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

  // Pass on each progress update, and return the first "answer" event.
  // A while loop, because a stream has no length: read until the server closes it
  while (true) {
    const { done, value: event } = await eventReader.read();
    if (done) {
      throw new Error("The /chat stream ended without an answer event");
    }
    if (event.event === "progress") {
      onProgress(JSON.parse(event.data) as ProgressUpdate);
    }
    if (event.event === "answer") {
      return JSON.parse(event.data) as RulesAnswer;
    }
  }
}


// ===== The steps =====

// Returns the steps with one more update: a "still writing" tick replaces the tick before it, so they don't pile up
// (record 0033)
function addStep(steps: ProgressUpdate[], update: ProgressUpdate): ProgressUpdate[] {
  const lastStep = steps.at(-1);
  const replacesLastTick = update.step === "still_writing" && lastStep?.step === "still_writing";
  if (replacesLastTick) {
    return [...steps.slice(0, -1), update];
  }
  return [...steps, update];
}

// The steps so far, each with a tick when done; while the bot works, the newest step has a spinner instead.
// The tick and the spinner are hidden from screen readers, so the status region reads only the messages
function StepList({ steps, isWorking }: { steps: ProgressUpdate[]; isWorking: boolean }) {
  const runningStepNumber = isWorking ? steps.length - 1 : -1;

  return (
    <ol className="steps">
      {/* The position is the key, because steps only ever add to the end or replace the last one */}
      {steps.map((step, i) => {
        const isRunning = i === runningStepNumber;
        return (
          <li key={i} className={isRunning ? "step step-running" : "step"} aria-current={isRunning ? "step" : undefined}>
            {isRunning
              ? <span className="step-marker step-spinner" aria-hidden="true" />
              : <span className="step-marker" aria-hidden="true">✓</span>}
            <span className="step-message">{step.message}</span>
          </li>
        );
      })}
    </ol>
  );
}

// The line the steps fold into after the answer, e.g. "Checked 3 steps in 12 s"
function describeCheckedSteps(stepCount: number, secondsTaken: number): string {
  const stepWord = stepCount === 1 ? "step" : "steps";
  return `Checked ${stepCount} ${stepWord} in ${secondsTaken} s`;
}


// ===== The page =====

// The whole page: holds the question as typed, the steps so far, and the answer once it arrives
export function ChatPage() {
  const [question, setQuestion] = useState("");
  const [isWaiting, setIsWaiting] = useState(false);
  const [steps, setSteps] = useState<ProgressUpdate[]>([]);
  const [secondsTaken, setSecondsTaken] = useState(0);
  const [rulesAnswer, setRulesAnswer] = useState<RulesAnswer | null>(null);
  const askedAt = useRef(0);

  // While the bot works, count the seconds up once a second, so the wait shows it is still going
  useEffect(() => {
    if (!isWaiting) {
      return;
    }
    const timer = setInterval(() => setSecondsTaken(Math.round((Date.now() - askedAt.current) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [isWaiting]);

  // Clears the last answer, shows each step as it comes, then shows the answer and how long it took
  async function askQuestion(event: FormEvent) {
    event.preventDefault();
    askedAt.current = Date.now();
    setRulesAnswer(null);
    setSteps([]);
    setSecondsTaken(0);
    setIsWaiting(true);

    const newAnswer = await askChat(question, (update) => setSteps((stepsSoFar) => addStep(stepsSoFar, update)));

    setSecondsTaken(Math.round((Date.now() - askedAt.current) / 1000));
    setIsWaiting(false);
    setRulesAnswer(newAnswer);
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

      {/* While waiting: a seconds counter, then a status region, so screen readers announce each new step without
          moving focus. The counter is hidden from them, or they would read it out every second */}
      {isWaiting && (
        <div className="progress">
          <p className="progress-timer" aria-hidden="true">Working · {secondsTaken} s</p>
          <section role="status" aria-label="Progress">
            <StepList steps={steps} isWorking={true} />
          </section>
        </div>
      )}

      {/* After the answer: the steps fold into one closed line that opens on a click */}
      {rulesAnswer !== null && (
        <>
          <details className="progress-summary">
            <summary>{describeCheckedSteps(steps.length, secondsTaken)}</summary>
            <StepList steps={steps} isWorking={false} />
          </details>
          <AnswerWithSources rulesAnswer={rulesAnswer} />
        </>
      )}
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
