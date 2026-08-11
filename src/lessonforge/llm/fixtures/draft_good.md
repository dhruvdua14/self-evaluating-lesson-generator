# RAG: How to Give an AI Model an Open Book

## What you will learn

By the end of this lesson you will know what RAG is, why people use it, and how
it works step by step. You do not need any background. We will start from zero.

## Start with a problem

An AI chat tool is built on a large language model. A large language model is a
program that has read a huge amount of text and learned to predict what words
come next. People shorten this to LLM.

An LLM only knows what it read during training. That creates three problems.

First, it has a cutoff date. It has not read anything published after training
ended.

Second, it has never seen your private files. It has not read your office
handbook or your college notes.

Third, when it does not know something, it may still answer. It can invent a
fact and state it with full confidence. This behaviour has a name. People call
it a hallucination, because the model makes up something that was never there.

## The idea in one picture

Think of it like an exam. A closed-book exam tests only what you memorised. If
you forget a date, you guess. That guess is the hallucination.

Now imagine the same exam, but open book. You may look things up. You find the
right page. You read it. Then you write your answer using that page.

RAG turns a closed-book AI into an open-book AI. The letters stand for
Retrieval-Augmented Generation. Each word is one step. Retrieval means searching
your documents and finding the useful parts. Augmented means adding those parts
to the question. Generation means writing the final answer.

Importantly, the model does not memorise the book. It reads the page, answers,
and forgets. The model itself never changes.

## How it works, step by step

RAG runs in two phases. The first phase happens once, ahead of time. The second
phase happens every time somebody asks a question.

### Phase 1: Get the books ready

You start with your documents. A long document is too big to hand to the model
all at once. So you split it into small pieces. Each small piece is called a
chunk. A chunk is usually a few paragraphs.

Next you turn each chunk into an embedding. An embedding is a list of numbers
that represents the meaning of the text. Two chunks about the same topic get
similar lists of numbers. This lets a computer compare meaning instead of
comparing exact words.

You store all these lists of numbers in a vector database. A vector is just
another name for a list of numbers. A vector database is a store that finds the
closest matches very fast, even across millions of chunks.

Doing all of this in advance is called building an index. An index is your
searchable library, prepared before anyone asks anything.

### Phase 2: Answer a question

Now a real question arrives. Three things happen.

**Retrieve.** The system turns the question into an embedding too. It then
searches the vector database for the chunks whose numbers are closest. It keeps
only a small number of the best matches, often three or five. This small number
has a name. People call it top-k.

**Augment.** The system builds a prompt. A prompt is the text you send to the
model. Here the prompt holds the retrieved chunks and the original question.

**Generate.** The model reads that prompt and writes an answer from the supplied
text.

## A worked example

Let us say you work at a company and you ask: "How many casual leave days do I
get?"

Here is what happens.

The handbook was split into chunks last month. One chunk says: "Full-time
employees receive 12 casual leave days per calendar year. Unused days do not
carry over."

Step one, retrieve. The search finds that chunk, because its meaning is closest
to your question.

Step two, augment. The system builds this prompt:

```
Use only the text below to answer.

TEXT: Full-time employees receive 12 casual leave days per
calendar year. Unused days do not carry over.

QUESTION: How many casual leave days do I get?
```

Step three, generate. The model reads that prompt and replies: "Full-time
employees get 12 casual leave days each year. They do not carry over."

The answer is correct because the real text was in front of the model. The model
did not need to remember anything.

## RAG is not the same as training

People often confuse two different things.

Fine-tuning means further training the model on new text. It adjusts the model
itself. It is good for teaching a style or a format.

RAG adds no training at all. It only supplies text at question time. It is good
for facts that change and for private documents.

## Where RAG still fails

RAG is helpful, but it is not perfect. It fails in a few clear ways.

If the answer is not in your documents, the search returns the nearest thing
anyway. That may be wrong.

If your documents are out of date, the answer repeats the old information.

If a chunk is split badly, half the answer may be missing.

So the quality of a RAG system depends on the quality of the search, not only on
the model.

## Recap

Here are the five points to remember.

1. An LLM alone is a closed-book exam. It can guess and sound confident.
2. RAG makes it an open-book exam by handing it real text.
3. Before questions arrive, you split documents into chunks, turn them into
   embeddings, and store them.
4. When a question arrives, the system runs retrieve, augment, and generate.
5. The model never changes. The text is supplied fresh each time.
