// The sample answer as /chat sends it, for the page tests: the stub's answer (app/sample_posts_answer.json) with the
// PDF link the server adds to each citation (app/pdf_links.py). Laws clause 1.4 is on page 1.

import samplePostsAnswer from "../../app/sample_posts_answer.json";


export const POSTS_PDF_LINK = "/rule-books/bwf-laws-of-badminton-2025-v5.0.pdf#page=1";

export const SAMPLE_CHAT_ANSWER = {
  ...samplePostsAnswer,
  citations: samplePostsAnswer.citations.map((citation) => ({ ...citation, pdf_link: POSTS_PDF_LINK })),
};
