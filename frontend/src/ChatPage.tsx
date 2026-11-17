// The chat page: a question box, then the answer with its [n] markers and a numbered source list.
// Slices 1 and 2 of docs/specs/ask-a-rules-question.md: the steps show as they arrive, and the answer shows once the
// stream's "answer" event arrives, whole (record 0028); then the steps fold into one line (record 0033).
// Slice 3: each [n] opens a popover with its source and a link to the PDF page (record 0034).
// Slice 4: a failed answer shows an error instead of waiting for good (record 0035).
// Slice 5: a refusal shows the bot's own words, labelled "Not covered by the rules", with no sources.
// The empty-question message (slice 6) comes later.

import * as Popover from "@radix-ui/react-popover";
import { EventSourceParserStream } from "eventsource-parser/stream";
import { useEffect, useRef, useState, type FormEvent } from "react";


// Constants
// What the page shows when the answer never comes: the request failed, or the stream ended without an answer
const FAILED_ANSWER_MESSAGE = "Couldn't write a checked answer. Please try again.";


// ===== The answer, as /chat sends it =====

// The fields of RulesAnswer (answer_flows/shared/answer_shape.py) that the page shows; the server adds pdf_link
// to each citation (app/pdf_links.py)
interface Citation {
  chunk_id: string;
  quote: string;
  source_name: string;
  pdf_link: string;
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

// The server's "error" event: the bot failed, and the event's message is the one to show
class AnswerFailedError extends Error {}

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
    if (event.event === "error") {
      throw new AnswerFailedError((JSON.parse(event.data) as { message: string }).message);
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
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const askedAt = useRef(0);

  // While the bot works, count the seconds up once a second, so the wait shows it is still going
  useEffect(() => {
    if (!isWaiting) {
      return;
    }
    const timer = setInterval(() => setSecondsTaken(Math.round((Date.now() - askedAt.current) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [isWaiting]);

  // Clears the last answer, shows each step as it comes, then shows the answer and how long it took, or the error
  async function askQuestion(event: FormEvent) {
    event.preventDefault();
    askedAt.current = Date.now();
    setRulesAnswer(null);
    setErrorMessage(null);
    setSteps([]);
    setSecondsTaken(0);
    setIsWaiting(true);

    // Any failure ends the wait with a message: the server's own for an "error" event, the page's for the rest
    try {
      const newAnswer = await askChat(question, (update) => setSteps((stepsSoFar) => addStep(stepsSoFar, update)));
      setSecondsTaken(Math.round((Date.now() - askedAt.current) / 1000));
      setRulesAnswer(newAnswer);
    } catch (error) {
      const isServerMessage = error instanceof AnswerFailedError;
      setErrorMessage(isServerMessage ? error.message : FAILED_ANSWER_MESSAGE);
    } finally {
      setIsWaiting(false);
    }
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

      {/* A failed answer: an alert, so screen readers read it out at once */}
      {errorMessage !== null && <p className="error-message" role="alert">{errorMessage}</p>}

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


// ===== The answer =====

// Returns the page number a PDF link opens at, e.g. 37 for "/rule-books/bwf-itto-2025-v7.0.pdf#page=37"
function readPdfPage(pdfLink: string): string {
  return pdfLink.split("#page=")[1];
}

// The link that opens a source's rule book at its page, in a new tab so the answer stays open
function PdfPageLink({ citation }: { citation: Citation }) {
  return (
    <a className="pdf-link" href={citation.pdf_link} target="_blank" rel="noopener noreferrer">
      Open PDF at page {readPdfPage(citation.pdf_link)}
    </a>
  );
}

// One [n] marker: a button that opens a popover with the quote, the source name and the PDF link (record 0034).
// Radix closes it on Escape or a click outside, and puts focus back on the marker
function CitationMarker({ sourceNumber, citation }: { sourceNumber: number; citation: Citation }) {
  return (
    <Popover.Root>
      <Popover.Trigger className="citation-marker" aria-label={`Source ${sourceNumber}`}>
        [{sourceNumber}]
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className="citation-popover" side="bottom" align="start" sideOffset={6} collisionPadding={16}>
          <q className="source-quote">{citation.quote}</q>
          <span className="source-name">{citation.source_name}</span>
          <PdfPageLink citation={citation} />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

// The answer text with each [n] turned into its marker: marker [n] is citations[n - 1]
function AnswerText({ text, citations }: { text: string; citations: Citation[] }) {
  // Splitting on the marker pattern keeps the captured numbers: text parts sit at even positions, numbers at odd ones
  const parts = text.split(/\[(\d+)\]/);

  return (
    <p className="answer-text">
      {parts.map((part, i) => {
        const isMarkerNumber = i % 2 === 1;
        if (!isMarkerNumber) {
          return part;
        }
        const sourceNumber = Number(part);
        return <CitationMarker key={i} sourceNumber={sourceNumber} citation={citations[sourceNumber - 1]} />;
      })}
    </p>
  );
}

// A refusal: the bot's own words under a label, with no sources, because nothing in the rules answers it
// (criterion 4). Its text keeps its line breaks, so a "Related" line shows on its own line
function RefusalAnswer({ rulesAnswer }: { rulesAnswer: RulesAnswer }) {
  return (
    <section className="answer" aria-label="Answer">
      <p className="refusal-label">Not covered by the rules</p>
      <p className="answer-text refusal-text">{rulesAnswer.answer}</p>
    </section>
  );
}

// The answer text, then the numbered sources, each with the same PDF link as its marker; a refusal has neither
function AnswerWithSources({ rulesAnswer }: { rulesAnswer: RulesAnswer }) {
  if (rulesAnswer.refused) {
    return <RefusalAnswer rulesAnswer={rulesAnswer} />;
  }
  const answerText = rulesAnswer.answer_sentences.map((sentence) => sentence.text).join(" ");

  return (
    <section className="answer" aria-label="Answer">
      <AnswerText text={answerText} citations={rulesAnswer.citations} />
      <h2 id="sources-heading">Sources</h2>
      <ol className="sources" aria-labelledby="sources-heading">
        {/* The position is the key, because the list never reorders and a clause can be cited twice */}
        {rulesAnswer.citations.map((citation, i) => (
          <li key={i}>
            <span className="source-number">[{i + 1}]</span>
            <q className="source-quote">{citation.quote}</q>
            <span className="source-name">{citation.source_name}</span>
            <PdfPageLink citation={citation} />
          </li>
        ))}
      </ol>
    </section>
  );
}
