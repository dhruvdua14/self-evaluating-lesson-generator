# Introduction to Retrieval-Augmented Generation (RAG)

## What You Will Learn
- Why standard AI models struggle with new or private information.
- What Retrieval-Augmented Generation (RAG) is and how it works.
- How documents are prepared using chunking and embeddings.
- The difference between RAG and fine-tuning.
- Common reasons why a RAG system can still fail.

---

## Prerequisites

Before we begin, we must understand two fundamental terms.

A **Large Language Model** (LLM) is a computer program trained on vast amounts of text to read and generate human language.

A **prompt** is the text input or instruction that you give to an LLM.

---

## The Problem: Why Base AI Models Struggle

A base LLM only knows the text it saw during its training. This creates three big problems.

First, an LLM has a **knowledge cutoff**. A **knowledge cutoff** is the date when the model's training ended. The model knows nothing about events or documents created after this date.

Second, an LLM has no private knowledge. It has never seen your company's internal files, personal notes, or private reports.

Third, an LLM can suffer from **hallucination**. A **hallucination** happens when an LLM gives a confident answer that is completely wrong.

We need a way to give fresh, private, and correct facts to the LLM when we ask a question.

---

## The Core Idea: A Kirana Shop Analogy

Imagine a local Kirana shopkeeper and a helper boy. 

The shopkeeper knows how to speak politely to customers. But he cannot remember every customer's unpaid bill. He also does not know today's new wholesale prices.

Instead of trying to memorize thousands of changing pages, the shopkeeper relies on the helper boy.

When a customer asks, "What is my pending bill?", three things happen:

1. The helper boy runs to a physical ledger book and finds the exact page for that customer.
2. The helper boy places that page on the counter directly in front of the shopkeeper.
3. The shopkeeper reads the page and tells the customer the exact amount.

Once the customer leaves, the shopkeeper forgets the bill amount. He does not memorize it permanently.

This exact process is how RAG works:
- The **shopkeeper** is the Large Language Model (LLM).
- The **ledger book** is your collection of documents.
- The **helper boy** is the retrieval system.
- Placing the ledger page on the counter is passing retrieved text into the prompt.

---

## What is RAG?

**Retrieval-Augmented Generation** (RAG) is a technique for improving LLM answers by giving the model relevant external text when a question is asked.

The name explains the three-step recipe:

1. **Retrieve**: Search a collection of external documents for pieces relevant to the user's question.
2. **Augment**: Paste those retrieved pieces into the prompt alongside the question.
3. **Generate**: The LLM writes its answer using the provided text.

---

## How It Works: Step by Step

Using RAG involves two separate phases: **Indexing** and **Retrieval**.

### Phase 1: Indexing (Preparing the Documents)

**Indexing** is the process of splitting, converting, and storing documents ahead of time. Indexing happens once, before any user asks a question.

First, large documents are split into smaller pieces. This splitting process is called **chunking**. Each small piece of text is called a **chunk**. Typical chunks are a few sentences to a few paragraphs.

Chunking is necessary because whole documents are usually too large to fit inside a prompt. Smaller chunks also make it easier to find exact answers.

Second, each chunk is converted into an **embedding**. An **embedding** is a list of numbers that represents the meaning of a piece of text.

A separate computer model called an **embedding model** creates these embeddings.

Texts with similar meanings get similar lists of numbers. For example, "How do I reset my password?" gets a list similar to "Steps to change your login credentials." An embedding is not a compressed copy of the text. You cannot convert the numbers back into the original text.

Third, the chunks and their embeddings are stored in a **vector database**. A **vector database** is a database designed to store embeddings and search them quickly by meaning.

Examples of vector databases include FAISS, Chroma, Pinecone, Weaviate, Qdrant, and pgvector. A vector database is a common choice, but not a strict requirement. Small systems can use plain keyword search or a simple list in memory.

### Phase 2: Retrieval and Generation (Answering the Question)

Retrieval happens every time a user asks a question.

1. The user asks a question.
2. The embedding model converts the question into a new embedding list.
3. The system searches the vector database for the closest matching chunks. This search process is called **top-k retrieval**. **Top-k** refers to the small fixed number of best chunks returned, such as the top 3 or top 5 chunks.
4. The system pastes those top chunks into the prompt alongside the user's question.
5. The LLM reads the prompt and generates an answer.

Because the answer comes from specific chunks, the system can display **citations**. A **citation** is a note showing which source document a specific answer came from. Citations make answers easy to check.

---

## Worked Example: Traced End to End

Let us follow a complete example of a bank assistant answering a customer.

### Stage 1: What was searched
The user submits the following question:
> "What is the interest rate for the Shubh Griha home loan scheme in 2024?"

The system converts this question into an embedding using the embedding model.

### Stage 2: What was found
The vector database searches all stored chunks. It finds the single most relevant chunk from an internal bank PDF:

> **Found Chunk:**
> "Under the Shubh Griha scheme launched in January 2024, the home loan interest rate is 8.5% for loans up to 30 lakhs."

### Stage 3: Assembled Input (The Prompt)
The system pastes the retrieved chunk into the prompt sent to the LLM:

> **System Instruction:**
> Answer the question using only the context below.
> If the answer is not in the context, say "I do not know."
>
> **Context:**
> Under the Shubh Griha scheme launched in January 2024, the home loan interest rate is 8.5% for loans up to 30 lakhs.
>
> **Question:**
> What is the interest rate for the Shubh Griha home loan scheme in 2024?

### Stage 4: What came out
The LLM reads the assembled prompt and produces the final answer:

> **Output Answer:**
> "The interest rate for the Shubh Griha home loan scheme in 2024 is 8.5% for loans up to 30 lakhs. [Source: Internal Bank PDF, Chunk #42]"

---

## RAG vs Fine-Tuning

An LLM relies on internal numerical values called **weights**. **Weights** are the internal parameters inside the model that determine how it processes language.

**Fine-tuning** is the process of further training an existing model to adjust its weights.

Here is how RAG and fine-tuning differ:

- **RAG** supplies dynamic facts at question time. It does not modify the model.
- **Fine-tuning** changes the model's weights to teach it a specific style, format, or tone.

---

## What People Get Wrong

- **Wrong Belief:** "RAG retrains the AI model or updates its weights permanently."
- **Why it is wrong:** RAG does not change the model's weights at all. The retrieved text is placed temporarily in the prompt. The model forgets the text as soon as the answer is generated.

- **Wrong Belief:** "RAG completely eliminates wrong answers and hallucinations."
- **Why it is wrong:** RAG reduces hallucinations, but it cannot eliminate them completely. If retrieved text is confusing or wrong, the model can still generate an incorrect answer.

- **Wrong Belief:** "RAG strictly requires a vector database."
- **Why it is wrong:** A vector database is a common choice, but not mandatory. Simple systems can use plain keyword search.

- **Wrong Belief:** "Embeddings are compressed copies of original text."
- **Why it is wrong:** Embeddings represent mathematical meaning, not compressed words. You cannot restore original text from an embedding list.

---

## Where It Still Fails

RAG is not magic. It can fail in four specific ways:

1. **Missing Information:** The correct answer is not present in your documents.
2. **Wrong Retrieval:** The document contains the answer, but the search fails to find the correct chunk.
3. **Bad Source Documents:** The source document itself contains out-of-date or incorrect facts. RAG faithfully repeats bad sources.
4. **Poor Chunking:** A document is split poorly, cutting an important sentence in half across two chunks.

---

## Real-World Applications

RAG is widely used today in real-world systems:
- **Customer Support Assistants:** Answering customer questions directly from company help articles.
- **Internal Document Search:** Searching through private company wikis and reports.
- **Chat With PDF Tools:** Letting users ask direct questions about long uploaded documents.
- **Coding Assistants:** Helping programmers write code by reading a specific codebase.

---

## Recap

- **RAG** stands for Retrieval-Augmented Generation.
- It solves three problems: knowledge cutoff, lack of private knowledge, and hallucinations.
- The three steps of RAG are **Retrieve**, **Augment**, and **Generate**.
- **Indexing** splits documents into **chunks**, creates **embeddings**, and stores them in a **vector database**.
- **Retrieval** uses **top-k** matching to find relevant chunks when a question is asked.
- RAG does **not** modify or retrain the model's **weights**.
- Fine-tuning changes model style, while RAG provides fresh knowledge.