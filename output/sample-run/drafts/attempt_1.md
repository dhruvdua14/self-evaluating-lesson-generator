# Understanding Retrieval-Augmented Generation (RAG)

## What You Will Learn

In this lesson, you will learn:
- Why basic language models make mistakes or give outdated answers.
- What Retrieval-Augmented Generation (RAG) is.
- How RAG works using a real-world analogy.
- The step-by-step process of preparing data and answering questions.
- The difference between RAG and fine-tuning.
- Common mistakes people make about RAG and how RAG can fail.

---

## Prerequisites: Two Basic Terms

Before we discuss the main topic, we must understand two basic terms.

A **Large Language Model** (or **LLM**) is an artificial intelligence computer program trained on large amounts of text to understand and generate human words.

A **prompt** is the input text, instruction, or question that you give to an LLM.

---

## The Problem: Limits of AI Models

A basic LLM is very smart, but it has three major limitations.

### 1. Knowledge Cutoff
An LLM stops learning once its training finishes. The date when its training stopped is called its **knowledge cutoff**. An LLM does not know about events or documents created after its knowledge cutoff.

### 2. No Private Knowledge
An LLM is trained on public text. It has never seen your private notes, your personal files, or your company's internal documents.

### 3. Hallucination
When an LLM does not know an answer, it does not always say "I do not know." Instead, it often invents a wrong answer that sounds confident and correct. This problem is called **hallucination**.

To solve these three problems, we use a technique called Retrieval-Augmented Generation.

---

## What is RAG?

**Retrieval-Augmented Generation** (or **RAG**) is a method for improving the answers of an LLM by finding relevant external text and giving it to the model when a question is asked.

The name explains the process:
1. **Retrieval**: Search for relevant information in external documents.
2. **Augmented**: Add that information to the user's prompt.
3. **Generation**: Let the LLM write an answer using the added information.

---

## The Core Idea: The Kirana Shop Analogy

To understand RAG, imagine a local *Kirana* (grocery) shop.

In this shop, there is a **shopkeeper** and a **helper boy**.

- The **shopkeeper** is like the **LLM**. He speaks politely to customers and speaks fluent language. However, he cannot remember every customer's exact unpaid balance. He also does not remember today's new wholesale prices.
- The ** ledger book** is like your **external document collection**. It contains all the exact written facts, account balances, and price lists.
- The **helper boy** is the **retrieval system**. His only job is to search the ledger book quickly.

When a customer asks, *"What is my pending bill?"*, the process works like this:

1. **Retrieve**: The helper boy runs to the ledger book. He searches for the page belonging to that customer.
2. **Augment**: The helper boy places that exact ledger page on the counter in front of the shopkeeper.
3. **Generate**: The shopkeeper reads the page and speaks the correct answer to the customer.

The shopkeeper does not permanently memorize the customer's balance. Once the customer leaves, the shopkeeper forgets the page. The shopkeeper's memory has not changed.

---

## How RAG Works Step by Step

RAG has two main phases. Phase 1 happens once in advance. Phase 2 happens every time a user asks a question.

```
PHASE 1: INDEXING (Done once in advance)
[ Large Documents ] ---> [ Chunks ] ---> [ Embeddings ] ---> [ Vector Database ]

PHASE 2: QUESTION TIME (Done for every question)
[ User Question ] ---> [ Search Database ] ---> [ Top Chunks ]
                                                      |
                                                      v
[ Generated Answer ] <--- [ LLM Reads ] <--- [ Assembled Prompt ]
```

---

### Phase 1: Preparation (Indexing)

Before you can answer questions, you must prepare your documents. This preparation phase is called **indexing**.

Indexing has three steps:

#### Step 1: Chunking
A whole document is usually too large to fit inside a single prompt. **Chunking** is the process of splitting long documents into smaller pieces of text called **chunks**. A chunk is usually a few sentences or a few paragraphs long. Smaller chunks make it easier to find specific facts later.

#### Step 2: Embeddings
Computers do not understand human words directly. An **embedding** is a list of numbers that represents the meaning of a piece of text. 

A separate computer program called an **embedding model** converts text chunks into embeddings. Texts with similar meanings get similar lists of numbers. 

For example, the phrase *"How do I reset my password?"* and the phrase *"Steps to change your login credentials"* will produce similar lists of numbers because their meanings are similar.

#### Step 3: Storing in a Vector Database
A **vector database** is a specialized database built to store embeddings and search through them quickly. 

During indexing, all document chunks are turned into embeddings and stored inside the vector database. 

*Note:* A vector database is a common choice for large systems. However, small RAG systems can use simple lists or simple keyword searches instead.

---

### Phase 2: Answering a Question

Once indexing is complete, the system is ready for user questions.

#### Step 1: Retrieve
When a user asks a question, the system turns the question into an embedding using the embedding model.

The system searches the vector database for text chunks whose embeddings are closest in meaning to the question embedding.

The system returns a small fixed number of the best matching chunks. This number is called **top-k**. Common choices for top-k are the top 3 or top 5 chunks.

#### Step 2: Augment
The system takes the retrieved top-k chunks and pastes them into the prompt alongside the user's original question.

#### Step 3: Generate
The system sends the combined prompt to the LLM. The LLM reads the provided text chunks and generates an answer based on those facts.

Because the LLM reads directly from source passages, it can also show **citations**. A citation is a note showing the user exact document sources used for the answer.

---

## Fully Traced Worked Example

Here is an example of a complete RAG system answering a user question about a bank loan.

### Stage 1: The User Search
The user asks a specific question.

> **User Question:** "What is the interest rate for the Shubh Griha home loan scheme in 2024?"

---

### Stage 2: What Was Found (Retrieval)
The system converts the question into an embedding and searches the bank's indexed vector database. It returns the single best matching chunk (top-1).

> **Found Chunk:** "Under the Shubh Griha scheme launched in January 2024, the annual interest rate for home loans is set at 8.5% for loans up to 30 lakhs."  
> *(Source: Internal_Bank_Policy_2024.pdf, Page 4)*

---

### Stage 3: The Assembled Input (Augmentation)
The system combines the retrieved chunk and the original question into a single prompt for the LLM.

> **Assembled Prompt Sent to LLM:**  
> Use only the following provided context to answer the question. If the answer is not in the context, say "I do not know."  
>  
> **Context:**  
> "Under the Shubh Griha scheme launched in January 2024, the annual interest rate for home loans is set at 8.5% for loans up to 30 lakhs."  
>  
> **Question:**  
> What is the interest rate for the Shubh Griha home loan scheme in 2024?

---

### Stage 4: What Came Out (Generation)
The LLM reads the context and generates a precise answer with a citation.

> **Generated Output:**  
> "The annual interest rate for the Shubh Griha home loan scheme in 2024 is 8.5% for loans up to 30 lakhs. [Source: Internal_Bank_Policy_2024.pdf, Page 4]"

---

## What People Get Wrong

### Misconception 1: "RAG retrains the model or updates its internal memory."
**Fact:** RAG does not change the model at all.

Inside an LLM are numerical settings called **weights** that control how it processes information. 

**Fine-tuning** is the process of training an existing LLM further to adjust its internal weights. Fine-tuning is used to teach an LLM a specific style, format, or tone of speaking.

RAG does not use fine-tuning. RAG does not change the model's weights. The retrieved text is placed temporarily into the prompt. Once the answer is generated, the retrieved text is forgotten.

---

### Misconception 2: "RAG guarantees 100% correct answers and completely stops hallucinations."
**Fact:** RAG reduces hallucinations significantly, but it does not completely eliminate them.

If the search step returns incorrect text chunks, the LLM will generate an incorrect answer based on that bad text.

---

### Misconception 3: "RAG requires a vector database."
**Fact:** A vector database is common, but it is not mandatory.

Small systems can perform RAG using simple keyword searching or simple memory lists.

---

### Misconception 4: "Embeddings are compressed copies of the original text."
**Fact:** You cannot recover the original text from an embedding.

An embedding is only a mathematical representation of meaning, not a compressed file like a zip folder.

---

## Where RAG Can Still Fail

RAG is a powerful tool, but it can fail in four specific ways:

1. **Information Missing Entirely:** The answer is not present in your document collection.
2. **Wrong Retrieval:** The retrieval system selects incorrect chunks that do not answer the user's question.
3. **Outdated Source Documents:** The source documents contain false or outdated facts. RAG will repeat those bad facts faithfully.
4. **Poor Chunking:** A long answer gets cut in half across two separate chunks during chunking, destroying the context.

---

## Real-World Applications

RAG is commonly used in many software tools today:
- Customer-support chat assistants that read company help center articles.
- Internal document search tools that read company wikis.
- "Chat-with-your-PDF" applications.
- Coding assistants that read a specific software codebase.

---

## Recap

- **Base LLM Problems:** Base models suffer from knowledge cutoffs, lack private data, and can hallucinate.
- **RAG Definition:** RAG supplies relevant source documents to an LLM inside the prompt at question time.
- **Three Core Steps:** Retrieve relevant chunks, Augment the prompt, Generate the answer.
- **Indexing Phase:** Long documents are broken into chunks, turned into embeddings by an embedding model, and saved in a vector database.
- **No Weight Changes:** RAG does not retrain or fine-tune the LLM. Its internal weights remain unchanged.