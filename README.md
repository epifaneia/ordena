# Ordena · Messy orders → Business Central

*Léelo en [español](README.es.md).*

An order that arrives the way real orders arrive, a half-written email or a WhatsApp voice note, lands in Business Central as an **unposted sales order**, with customer, items, quantities and date resolved against the ERP's master data, anything doubtful flagged and the original attached. A person validates it before it counts. Everything runs locally except Business Central itself.

> AI carries risk. Code bounds it. The standard answers for what remains.

**Proof of concept** on Microsoft's demo data (CRONUS): no data from any real company.

[Design philosophy](#design-philosophy) · [The five steps](#the-five-steps-in-this-project) · [Try it](#try-it) · [Design decisions](#design-decisions) · [Limitations](#limitations) · [Security & regulation](#security--regulation)

---

## Design philosophy

Every AI application has five steps. Only step 4 invokes a model; the other four are code: reproducible, testable, offline. Step 5 never patches: it flags and degrades. Full text at [epifaneia.dev](https://epifaneia.dev).

```
 1 CLEANING      2 CONTEXT       3 INPUT GUARDRAIL   4 PROCESS        5 OUTPUT GUARDRAIL
 ■ code          ■ code          ■ code              ▲ model          ■ code
```

## The scenario

A mid-sized manufacturer running Navision on its own server, which has to move to Business Central online because Microsoft is ending support for the server version. Sales reps and customers send orders each in their own way: emails, voice notes, PDFs, paper. Someone types them into the ERP by hand. Confidentiality comes first, and there is no IT department.

## Where AI adds value

Understanding a human message: "the usual, but two more chairs, and have it arrive on Thursday", said in a voice note. That is all the model does. Which customer, which item, which unit, which exact date and whether the price matches the price list are decided by code, against Business Central's master data. And when code is not sure, it says so.

---

## The five steps in this project

★ marks where the improvement lives in this project: **deterministic resolution** and **unposted writing** into the ERP.

| Step | What it does here | |
|---|---|---|
| 1 · Cleaning | `transcribir.py`: Whisper (faster-whisper large-v3-turbo) locally, primed with the customers' and items' vocabulary from the master data; low-confidence segments are flagged. Text comes in as is, with sender and date. | |
| 2 · Context | The message, its date and its sender. The model never sees the price list or the item codes, so it cannot invent them. | |
| 3 · Input guardrail | `esquema.py`: a closed schema (Pydantic) forced on the model's output, at temperature 0. The model is told to copy **verbatim** from the message (the customer's name, the item's description, the date in words) and not to invent codes. Small models do not always obey: step 5 checks it. | |
| 4 · Process | One call per message: Ollama locally by default (qwen2.5:7b on a 6 GB GPU). Gemini and Groq exist only to measure the ceiling on CRONUS data, and have to be asked for. | |
| 5 · Output guardrail | `resolver.py` and `tickets.py`: customer and item are resolved against the master data; if the second candidate is within 8 points of the first, it is **ambiguous** and flagged. A sender found in a customer's record identifies that customer, unless the message names a different one: then neither is chosen and the ticket is flagged with both. Relative dates ("Thursday") are computed from the message date. A price that does not match the price list, or does not appear literally in the message, is flagged, never overwritten. The same goes for the customer, the delivery address and each item description the model copied: if it is not in the message (ignoring case, accents, punctuation and spacing), it is flagged "the model did not copy verbatim", never corrected. A date returned already computed (`2026-11-02`) that the message does not contain is flagged too. A ticket missing a mandatory field is born incomplete. `bc.py` creates the order **unposted**, with the ticket id as external document number (processing the same message twice does not duplicate it), and attaches the original, checking it arrives whole. | ★ |

## The tray

`python web.py` opens a tray at `http://127.0.0.1:8765`, styled after the Navision 2013 Windows client. Drop an email or a voice note, the message is queued and the tickets appear on their own, with doubtful fields in amber, the transcript with its doubtful segments highlighted, and the original audio.

Orders have states: `pending → validated → written`, or `rejected` with a reason. Only a validated order is written to the ERP, and a transition that is not allowed is refused. "Open in the ERP" goes to the order in Business Central's web client.

## Try it

Without a model and without Business Central, from a ready-made interpretation and the demo master data:

```bash
python -m venv .venv && .venv\Scripts\activate          # on Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m ordena_poc.main procesar ejemplos/pedido_ejemplo.txt --interpretacion ejemplos/interpretacion_ejemplo.json --remitente helen.ray@contoso.com
```

With the local model (Ollama running and `ollama pull qwen2.5:7b`):

```bash
python -m ordena_poc.main procesar ejemplos/pedido_ejemplo.txt --remitente helen.ray@contoso.com
python -m ordena_poc.main web
```

`ejemplos/guion_audio.md` holds the scripts of the test voice notes, with what each one should produce: record them yourself; they are not in the repository.

### Against a real Business Central

1. Start the **free trial** of Dynamics 365 Business Central in a Microsoft 365 tenant. It creates a `Production` environment with the CRONUS company.
2. **Register an application** in Entra ID: accounts in this directory, *Allow public client flows*, delegated Dynamics 365 Business Central permissions `Financials.ReadWrite.All` and `user_impersonation`, with admin consent.
3. Copy `.env.example` to `.env` and fill in `BC_TENANT_ID` and `BC_CLIENT_ID`.
4. `python -m ordena_poc.main probar-bc`: the first time it asks you to sign in with a device code.
5. `python -m ordena_poc.main maestros`: downloads CRONUS customers and items, and the vocabulary for Whisper.
6. `python -m ordena_poc.main procesar ejemplos/pedido_ejemplo.txt --remitente helen.ray@contoso.com --crear`, then open in Business Central the order number it prints.

For production, the same code uses application credentials (`BC_CLIENT_SECRET`) with a hand-written permission set in Business Central that cannot post.

## Measured

- **Local transcription:** 33 s of audio in about 11 s on an RTX 2060 (6 GB), 103 s on CPU.
- **End to end against Business Central:** a test message creates the unposted sales order in CRONUS, with the lines at the ERP's own list prices; processing the same message again does not create a second order.

Not measured: accuracy on a real company's messages. That is the first thing to measure with its documents.

---

## Design decisions

Seven decisions, each with its context, the alternatives it rejects and what would change it, in [docs/decisiones/](docs/decisiones/) (in Spanish):

1. Business Central online as the destination, Navision as the source
2. What Business Central does natively, before building anything
3. Docling for messy documents
4. Where the model runs
5. The standard API before an AL extension
6. Nothing enters Business Central without a human OK
7. Build, and locally, before buying

Plus the [Business Central touch points](docs/arquitectura/business-central.md), [master data](docs/arquitectura/datos-maestros.md) and a [glossary](docs/glosario.md).

## Limitations

- A proof of concept on demo data. No real message; accuracy on a company's email and voice notes is unmeasured.
- Business Central online only. The adapter for on-premise Navision (SOAP on page 42) is designed, not written.
- Text and voice only. PDF, Excel and scanned paper would go through Docling ([ADR-0003](docs/decisiones/0003-docling-para-documentos-sucios.md)), which is not wired in.
- The tray does not merge or split tickets, send acknowledgements or draft questions back to the customer, has no roles or search, and does not look at the customer's history ("the usual" stays doubtful).
- Few automated tests: `tests/test_tickets.py` covers the verbatim check and some resolver logic, offline. Contact and observations are not checked for verbatim copy. No custody ledger (who ran what, what left the machine). That comes next.

---

## Security & regulation

The same four headings as in the other repositories. Rows marked **today** are what the code does; rows marked **next** are what is missing.

| | | |
|---|---|---|
| **Confidentiality** | Transcription and model run locally by default: the message does not leave the machine. The cloud is used only when asked for (`--llm gemini`, `--stt groq`) and is meant for comparing on demo data, never on a company's data. One exception: `comparar` runs every engine side by side, so by default it also sends the message to Gemini and Groq; pass `--llm` and `--stt` with local engines only to keep it on the machine. `.env`, tokens, audio and the tray are outside git. | **today** |
| **Traceability** | Every run leaves in `salida/` the message, the transcript, the model's raw output and the tickets. In the tray, every ticket keeps its original, its state history and the number of the order it created; in Business Central, the order carries the ticket id as external document and the original attached. | **today** |
| | A custody ledger per model call (actor, step, whether data left the machine, input hash), as in the other repositories. | **next** |
| **Leak prevention** | Authentication with Microsoft Entra ID: device code for testing, application credentials for production. No username and password and no web-service keys in the code. The application's permissions are bounded in Business Central, with a hand-written permission set that cannot post. | **today** |
| **Human in the loop** | The pipeline only writes **unposted** orders. In the tray, only those a person has validated; the command line (`procesar --crear`) writes without it, to test the integration, and stays in the proof of concept. Doubtful fields are flagged in amber with their reason; nothing is silently corrected. Posting the order, the irreversible step, is always done by a person in Business Central. | **today** |

Written with reference to the EU AI Act (2024/1689), GDPR and ISO/IEC 27001. No certification or conformity is claimed: the table says which part the code covers and which part belongs to the company.

---

## Structure

```
ordena_poc/   esquema · transcribir · interpretar · maestros · resolver · tickets · bc · bandeja · mostrar · main
ordena_poc/web/   the tray (FastAPI and a page styled after Navision 2013)
data/         maestros_demo.json: an approximation of CRONUS to work offline
ejemplos/     test orders, a ready-made interpretation and the voice-note script
tests/        test_tickets.py: offline, no model (python tests/test_tickets.py)
docs/         decisiones/ (seven ADRs) · arquitectura/ · glossary
```

The code and the design documents are in Spanish.

Daniel Martín · [epifaneia.dev](https://epifaneia.dev) · Apache-2.0
