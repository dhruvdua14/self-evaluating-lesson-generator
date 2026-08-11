# Introduction to Retrieval-Augmented Generation (RAG)

## What You Will Learn
- Why standard AI models struggle with new or private information.
- What Retrieval-Augmented Generation is and why it exists.
- The three main steps of the RAG process.
- How documents are prepared using chunking, embeddings, and vector databases.
- The difference between RAG and fine-tuning.
- Common failure cases of RAG systems.

## The Problem With Base AI Models

A Large Language Model (LLM) is an AI program trained on large amounts of text to read and write human language.
A prompt is the written instruction or question that you give to an LLM.

A standard LLM is very capable, but it has three major limitations.

First, an LLM has a **knowledge cutoff**.
A **knowledge cutoff** is the fixed date when an LLM finished its training process.
The model does not know about any events or documents created after this cutoff date.

Second, an LLM has no private knowledge.
It has never seen your personal files, company notes, or private bank records.

Third, an LLM can suffer from **hallucination**.
A **hallucination** happens when an LLM produces a fluent and confident answer that is completely wrong.
When an LLM does not know an answer, it often invents facts instead of saying "I do not know."

We need a reliable way to give accurate, updated, and private information to the LLM when we ask a question.

## The Core Idea: The Shopkeeper Analogy

Imagine a local Kirana grocery shopkeeper who has a helper boy.

The shopkeeper is very polite and knows how to talk to customers well.
However, the shopkeeper cannot remember every customer's daily unpaid bills.
The shopkeeper also does not remember today's changing wholesale market prices.

Instead of trying to memorize thousands of changing numbers, the shopkeeper relies on the helper boy.

When a customer comes and asks, "What is my total unpaid bill?", the process begins.

1. The helper boy runs to a ledger book stored in the back room. He finds the exact page for that customer.
2. The helper boy brings that page and places it on the counter in front of the shopkeeper.
3. The shopkeeper reads the page and speaks the correct bill amount to the customer.

Once the customer leaves, the shopkeeper forgets the number on the paper.
The shopkeeper did not change his brain or memorize the bill permanently.
He simply read the sheet placed in front of him.

This is exactly how **Retrieval-Augmented Generation (RAG)** works.
**Retrieval-Augmented Generation (RAG)** is a technique that improves LLM answers by finding relevant documents and adding them to the prompt when a question is asked.

In this analogy:
- The shopkeeper is the LLM.
- The helper boy is the retrieval system.
- The ledger book is the collection of documents.
- Placing the ledger page on the counter is adding context to the prompt.

## How RAG Works: Step by Step

RAG works in three main steps, in a strict order.
The name RAG gives you the exact recipe.

### 1. Retrieve
When a user asks a question, the system searches through a collection of external documents.
To **retrieve** means to search for and find the pieces of text most relevant to the user's question.

### 2. Augment
To **augment** means to add information to something to make it complete.
In RAG, the system pastes the retrieved text pieces into the prompt alongside the original question.

### 3. Generate
To **generate** means to produce text output.
The LLM reads the user question and the pasted source text together.
It writes its final answer using that supplied text.

## Preparing Documents for RAG

Before an AI system can search documents, it must prepare them.
This preparation phase is called **indexing**.
**Indexing** is the process of splitting documents, converting them into numbers, and storing them in a searchable database.

Indexing happens once, ahead of time.
Retrieval happens later, every time a user asks a question.
These are two separate phases.

Here are the concepts used during indexing:

### Chunking
Large documents are usually too long to fit into a prompt.
Therefore, documents are split into smaller pieces called chunks.
**Chunking** is the process of breaking long text documents into smaller segments.
A chunk is usually a few sentences or a few paragraphs long.
Smaller chunks make it easier to find exact matching passages.

### Embeddings and Embedding Models
Computers do not understand human language directly.
They process text using mathematical numbers.
An **embedding** is a list of numbers that represents the meaning of a piece of text.
Texts with similar meanings receive similar lists of numbers.

An **embedding model** is a separate AI program that converts text into an embedding.
For example, the question "How do I reset my password?" gets a similar embedding to "Steps to change your login credentials."
An embedding captures meaning rather than exact words.
An embedding is not a compressed copy of text.
You cannot recover the original text from an embedding.

### Vector Database
A **vector database** is a database designed to store embeddings and search through them rapidly.
It compares the embedding of the user question with stored chunk embeddings to find matching meanings.
Examples of vector databases include FAISS, Chroma, Pinecone, Weaviate, Qdrant, and pgvector.

A vector database is a common choice, but it is not mandatory.
Small systems can use plain keyword search or a simple list in memory.

### Top-k Retrieval
When searching, the system usually retrieves a fixed number of the closest chunks.
This fixed number is called **top-k**.
For example, a top-k value of 3 means the system selects the 3 most relevant chunks.
Retrieving more chunks gives the model more information, but it increases costs and can add irrelevant noise.

### Citations
Because the LLM reads specific source text, a RAG system can show where its answer came from.
A text reference showing the source document is called a citation.
Citations make answers checkable for human users.

## Fully Traced Worked Example

Here is a step-by-step trace of a RAG system answering a user query.

### User Question
"What is the interest rate for the Shubh Griha home loan scheme in 2024?"

### Stage 1: Retrieval
The system converts the user question into an embedding using an embedding model.
It searches a vector database containing bank document chunks.
It finds the single most relevant chunk from an internal bank PDF document.

**Search Query:**
"Shubh Griha home loan interest rate 2024"

**Retrieved Chunk Found:**
"Under the Shubh Griha scheme launched in January 2024, the annual interest rate for home loans is set at 8.5% for loans up to 30 lakhs."

### Stage 2: Augmentation
The system constructs a combined prompt input.
It pastes the retrieved chunk directly alongside the original question.

**Assembled Prompt Input:**
```text
System Instruction: Answer the question using only the provided context below.

Context Document:
"Under the Shubh Griha scheme launched in January 2024, the annual interest rate for home loans is set at 8.5% for loans up to 30 lakhs."

User Question:
What is the interest rate for the Shubh Griha home loan scheme in 2024?
```

### Stage 3: Generation
The LLM processes the assembled prompt input.
It writes the final response using the provided facts.

**Generated Output:**
```text
The interest rate for the Shubh Griha home loan scheme in 2024 is 8.5% for loans up to 30 lakhs.
(Source: Internal Bank Document - Shubh Griha Scheme 2024)
```

## What People Get Wrong: RAG vs Fine-Tuning

The most common beginner misconception is that RAG retrains the LLM or updates its memory permanently.
This is incorrect.

An LLM relies on internal mathematical numbers called **weights**.
**Weights** are the internal values inside an AI model that determine how it processes language.
**Fine-tuning** is the process of training an existing LLM on new text to permanently adjust its internal weights.

RAG **does not change the model's weights**.
The model itself is never modified or retrained during RAG.
The retrieved text is placed into the prompt temporarily.
As soon as the response is generated, the LLM forgets the retrieved text completely.

Here is how to compare RAG and fine-tuning:
- **RAG** supplies fresh knowledge at question time. It is best for changing facts, private files, and checkable citations.
- **Fine-tuning** adjusts internal model weights. It is best for teaching a specific style, format, or writing tone.

RAG and fine-tuning solve different problems and can be used together.

Here are other common errors corrected plainly:
- **Wrong:** "RAG eliminates hallucination completely."
  - **Fact:** RAG reduces hallucination, but it cannot guarantee correct answers every time.
- **Wrong:** "RAG requires a vector database."
  - **Fact:** Vector databases are common, but simple keyword search or simple lists also work.
- **Wrong:** "Embeddings are compressed text copies."
  - **Fact:** Embeddings represent mathematical meaning, not compressed words. Original text cannot be recovered from an embedding.

## Where RAG Still Fails

RAG is a practical tool, but it can fail in four specific ways:

1. **Missing Information:** The answer is not inside the document collection. Retrieval returns the closest chunk, which may be irrelevant.
2. **Wrong Retrieval:** The retrieval step picks the wrong text chunks. The LLM then generates an answer using irrelevant context.
3. **Bad Source Documents:** The source documents contain false or outdated information. RAG will repeat those wrong facts faithfully.
4. **Poor Chunking:** Documents are split poorly, cutting an important sentence in half.

## Where RAG Is Used

RAG is widely used in AI software applications today:
- **Customer Support Assistants:** Answering user questions directly from help center pages.
- **Internal Document Search:** Searching private company files, notes, and wikis.
- **Chat With PDF Tools:** Allowing users to upload a document and ask questions about its content.
- **Coding Assistants:** Reading a private software project to answer developer queries.

## Recap

- **RAG** stands for Retrieval-Augmented Generation.
- It solves knowledge cutoffs, lack of private knowledge, and hallucinations by supplying external source text.
- The three steps in order are **Retrieve** (search chunks), **Augment** (paste into prompt), and **Generate** (write answer).
- **Indexing** happens ahead of time by creating **chunks** and converting them into **embeddings**.
- RAG **does not change the model's weights**. Fine-tuning changes weights; RAG adds text context to the prompt.
- RAG can fail if sources are wrong, chunking is poor, or retrieval selects the wrong chunks.