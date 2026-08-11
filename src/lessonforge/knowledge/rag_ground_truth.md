# Ground Truth: Retrieval-Augmented Generation (RAG)

This file is the **grounding source** for the evaluator. The LLM judge checks every
factual claim in a generated lesson against the statements below. A claim that
contradicts this file fails the `accuracy_grounded` check. A claim that goes beyond
this file without hedging fails `no_unsupported_claims`.

Keep this file boring, short, and true. It is a contract, not a lesson.

---

## FACT-01 — What RAG stands for

RAG stands for **Retrieval-Augmented Generation**. It is a technique for improving
the answers of a large language model (LLM) by giving it relevant external text at
question time.

## FACT-02 — The problem RAG solves

A base LLM only knows what was in its training data. This creates three concrete
problems:

1. **Knowledge cutoff** — it does not know about events or documents created after
   training finished.
2. **No private knowledge** — it has never seen your company's internal documents,
   your notes, or your personal files.
3. **Hallucination** — when it does not know an answer, it may produce a fluent,
   confident, and wrong one.

RAG addresses all three by supplying the model with real source text at the moment
the question is asked.

## FACT-03 — The three steps

RAG has three steps, in this order:

1. **Retrieve** — search a collection of documents for the pieces most relevant to
   the user's question.
2. **Augment** — paste those retrieved pieces into the prompt alongside the original
   question.
3. **Generate** — the LLM writes its answer using the supplied text.

The name is literally the recipe: *Retrieval*, *Augmented*, *Generation*.

## FACT-04 — Chunking

Documents are split into smaller pieces called **chunks** before they are stored.
Chunks are used because (a) a whole document is usually too large to fit in the
prompt, and (b) smaller pieces make it easier to find the specific passage that
answers a question. Typical chunks are a few sentences to a few paragraphs.

## FACT-05 — Embeddings

An **embedding** is a list of numbers that represents the meaning of a piece of
text. Texts with similar meanings get similar lists of numbers. A separate model
called an **embedding model** produces them. Embeddings let a computer compare
meaning rather than compare exact words, so "How do I reset my password?" can match
a document that says "Steps to change your login credentials."

## FACT-06 — Vector database

A **vector database** stores embeddings and finds the ones closest to a query
embedding, quickly, even across millions of chunks. Examples include FAISS,
Chroma, Pinecone, Weaviate, Qdrant, and pgvector. A vector database is a common
implementation choice, not a strict requirement — small systems can use plain
keyword search or a simple in-memory list.

## FACT-07 — Indexing happens before questions

Splitting documents into chunks, embedding them, and storing them in a vector
database is called **indexing**. Indexing happens once, ahead of time. Retrieval
happens later, every time a user asks a question. These are two separate phases.

## FACT-08 — What RAG does NOT do

RAG **does not change the model's weights**. The model itself is not modified,
retrained, or fine-tuned. The retrieved text is placed in the prompt and is
forgotten as soon as the request finishes. This is the single most important
distinction between RAG and fine-tuning, and it is the most common beginner
misconception.

## FACT-09 — RAG vs fine-tuning

- **RAG** supplies *knowledge* at question time. Good for facts that change, private
  documents, and anything that must be cited.
- **Fine-tuning** adjusts the model's weights by further training. Good for teaching
  a *style, format, or behaviour*, not for injecting fresh facts.

They solve different problems and can be used together.

## FACT-10 — Citations

Because the answer is written from retrieved passages, a RAG system can show the
user which source each part of the answer came from. This makes answers checkable.
A plain LLM cannot do this reliably.

## FACT-11 — Top-k retrieval

Retrieval usually returns a small fixed number of the closest chunks, commonly
called **top-k** (for example, the top 3 or top 5). Retrieving more gives the model
more to work with but costs more and can add irrelevant noise.

## FACT-12 — Known failure modes

RAG is not magic. It fails when:

- The answer is not in the documents at all — retrieval returns the closest thing,
  which may still be wrong.
- Retrieval returns the wrong chunks, so the model answers from irrelevant text.
- The documents themselves are out of date or incorrect — RAG faithfully repeats bad
  sources.
- Chunks are split badly, cutting an answer in half.

Good RAG systems are judged on retrieval quality as much as on generation quality.

## FACT-13 — Where it is used

Common real-world uses: customer-support assistants answering from a help centre,
internal document search over company wikis, chat-with-your-PDF tools, and coding
assistants that read a specific codebase.

---

## Forbidden claims (auto-fail if asserted)

These statements are **false**. A lesson that asserts any of them must fail
`accuracy_grounded`:

- "RAG retrains the model" / "RAG updates the model's weights" / "RAG stores documents
  inside the model."
- "RAG eliminates hallucination completely" / "RAG guarantees correct answers."
- "RAG requires a vector database" (it is the common choice, not a requirement).
- "RAG and fine-tuning are the same thing" / "RAG is a type of fine-tuning."
- "The model permanently remembers the retrieved documents after answering."
- "RAG works without any external documents."
- "Embeddings are compressed copies of the text" (they represent meaning; the original
  text is not recoverable from them).
