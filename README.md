# 🐉 DRAGONS Data ETL

### Data Engineering Component of the DRAGONS Project

- **Project:** DRAGONS – *Diffusing biodiversity Response-able Action and awareness raising through citizen empowerment, inclusive engagement and innovative Governance of Nature and Society*
- **Work Package:** WP1 – Understanding societal perceptions, awareness, and engagement responses to biodiversity loss
- **Institution:** Pontificia Universidad Javeriana
- **Related Repository:** `dragons-data-analytics`

---

## Objective

Develop the data engineering component responsible for collecting, transforming, validating, and storing information obtained from public or authorised online sources, including social media, news outlets, and other permitted data acquisition mechanisms.

The main objective is to build a reproducible data workflow capable of consolidating textual content and metadata into a MongoDB document database, ensuring traceability, data quality, and availability for subsequent use by the `dragons-data-analytics` repository.

---

## Project Team

### Project Leadership

Responsible for jointly guiding the technical, analytical, scientific, and domain strategy of the component, ensuring alignment between data engineering, analytics, and the biodiversity research objectives.

**Members:**

- **PhD Luis Gabriel Moreno Sandoval**  
  **Technical & Data Analytics Lead**  
  Section Head and Faculty Member, Department of Systems Engineering  
  Pontificia Universidad Javeriana  

  Responsible for the technical and methodological direction of the data component, architecture definition, analytics and artificial intelligence strategy, technical oversight, and validation of engineering and analytical deliverables.  
  📧 [morenoluis@javeriana.edu.co](mailto:morenoluis@javeriana.edu.co)

- **PhD Juan David Amaya Espinel**  
  **Biodiversity Research & Domain Lead**  
  Associate Professor, Department of Ecology and Territory  
  Pontificia Universidad Javeriana  

  Responsible for the scientific and thematic leadership of the biodiversity component. He guides the definition of research questions, conceptual criteria for source selection and evaluation, and the interpretation of results from the biodiversity domain perspective.  
  📧 [jamayae@javeriana.edu.co](mailto:jamayae@javeriana.edu.co)

---

### Project Coordination

Responsible for coordinating the execution of the ETL component across technical and domain workstreams, connecting data acquisition and processing requirements with the scientific criteria of the biodiversity research component.

**Members:**

- **Juan Pablo Arias Buitrago**  
  **Data Scientist & Technical Project Coordinator**  

  Responsible for the operational and technical coordination of the project, activity and deliverable tracking, integration between `dragons-data-etl` and `dragons-data-analytics`, definition of data requirements, monitoring of acquisition, transformation, and quality processes, and validation that ETL outputs can support the analytical dataset and downstream analysis.  
  📧 [ariasj.u@javeriana.edu.co](mailto:ariasj.u@javeriana.edu.co)

- **Pabla Lozano Ramírez**  
  **Biodiversity Domain Lead & Research Project Coordinator**  

  Responsible for the scientific and thematic coordination of the ETL component, supporting the definition and validation of data sources, search terms and queries, content-selection criteria, and thematic relevance of the collected corpus. She also contributes to the thematic quality review of the data and validates that acquired sources and records remain aligned with the biodiversity research objectives.  
  📧 [pabla-lozano@javeriana.edu.co](mailto:pabla-lozano@javeriana.edu.co)

---

### Data Science and Analytical Validation

Responsible for supporting the definition of analytical data requirements and ensuring that the information produced by the ETL component is suitable for downstream analytics.

**Member:**

- **Sergio Pardo Hurtado**  
  **NLP Data Scientist & Lead Data Analyst**  

  Participates in the ETL component from the analytical perspective, supporting the definition of fields, variables, and data-quality criteria required for downstream analysis. He also contributes to validating that the collected and transformed data are suitable for the analytical dataset, statistical analysis, NLP, and artificial intelligence processes.  
  📧 [sergio_pardo@javeriana.edu.co](mailto:sergio_pardo@javeriana.edu.co)

---

### Data Engineering and Platform Team

Responsible for developing the acquisition, transformation, validation, storage, and infrastructure components supporting the ETL workflow.

**Members:**

- **Viviana Gómez León**  
  **Data Engineer & Platform Developer**  

  Responsible for developing source connectors, integrating external data sources, implementing extraction and transformation processes, persisting data in MongoDB, supporting communication between components, and contributing to the data platform implementation.  
  📧 [gomezlv@javeriana.edu.co](mailto:gomezlv@javeriana.edu.co)

- **Marlon Jhoan Garcia Restrepo**  
  **Data Engineer & DevOps Engineer**  

  Responsible for developing and maintaining ETL pipelines, data-quality and storage components, automation, environment configuration, containerisation, continuous integration, deployment, and technical infrastructure support.  
  📧 [mjgarcia@javeriana.edu.co](mailto:mjgarcia@javeriana.edu.co)

---

## General Workflow

```text
Public and authorised sources
             │
             ▼
       Data acquisition
             │
             ▼
          Validation
             │
             ▼
   Cleaning and normalisation
             │
             ▼
       Data quality
             │
             ▼
           MongoDB
             │
             ▼
    dragons-data-analytics
```

---

## Core Technologies

* **Programming language:** Python
* **Database:** MongoDB
* **Integration:** REST APIs, RSS feeds, and external data services
* **Containers:** Docker
* **Version control:** Git / GitHub

---

## Project Structure

The current repository structure is organised as follows:

```text
dragons_data_etl/
│
├── config/                       # General project and source configuration
│
├── docs/                         # Technical and data model documentation
│
├── experiments/
│   └── source_discovery/         # Exploratory source assessment and discovery artifacts
│
├── gdelt/                        # GDELT-specific implementation and supporting resources
│
├── logs/                         # Execution and processing logs
│
├── queries/
│   └── gdelt/                    # Versioned queries used for GDELT acquisition
│
├── scripts/                      # Operational and execution scripts
│
├── src/                          # Core ETL implementation
│
├── tests/                        # Unit and integration tests
│
├── LICENSE
└── README.md
```
### `config/`

Contains general configuration required by the ETL processes, including source-specific settings and execution parameters.

### `docs/`

Contains technical documentation related to the architecture, MongoDB document model, data structures, and processing decisions.

### `experiments/source_discovery/`

Contains exploratory and experimental artifacts used during the identification, assessment, and comparison of potential data sources.

Content stored in this directory is not considered production configuration and should not be consumed directly by the operational ETL pipeline until the corresponding source has been reviewed and approved.

### `gdelt/`

Contains implementation components and supporting resources specifically related to data acquisition through GDELT.

### `logs/`

Stores execution logs generated during acquisition, transformation, validation, and testing processes.

### `queries/gdelt/`

Contains the versioned search queries used for GDELT data acquisition, enabling traceability and reproducibility of the retrieved datasets.

### `scripts/`

Contains executable scripts used to run acquisition, processing, validation, maintenance, or other operational workflows.

### `src/`

Contains the main application code for the ETL component, including source collectors, processing logic, validation, persistence, and reusable services.

### `tests/`

Contains unit and integration tests used to validate source connectors, processing logic, persistence, and other ETL components.

---

## Event pipeline (GDELT + scraper)

Collections in MongoDB (`MONGODB_DATABASE`, default `dragons`):

- `eventos` — seeded from [`data/events/DRAGONS_T1.csv`](data/events/DRAGONS_T1.csv) (68 events; skip the title row).
- `queries` — one BigQuery statement per event (`id`, `id_evento`, `consulta`).
- `whitelist` — up to **100** GKG rows per query (`id`, `hash`, `url`, full GKG payload, `id_query`, `id_scrapper`, `id_metric`).
- `metrics` — one document per query (same counters as the previous execution metrics, plus `id` and `id_query`).
- `scrapper` — article content from the news extractor (`id`, `hash_whitelist`, `contenido`).

Configure Atlas locally in `.env` (see `.env.example`). Do not commit `.env`.

```text
python scripts/seed_events.py
python scripts/run_gdelt.py --max-events 1 --skip-scrape
python scripts/run_gdelt.py --event-id UK-01 --event-id CO-01 --row-limit 100
```

`--max-events` / `--event-id` keep the Atlas free-tier sample small. Full 68 events × 100 rows plus HTML can exceed M0 storage.

The HTML extractor lives in `src/gdelt/collectors/web/news_extractor.py` (from `test/news-scraper-pipeline`).

---

## Shared MongoDB Flow For NLP

This ETL now writes to the MongoDB service defined in
`C:\project\javeriana\repos\dragons_project_nlp\docker\mongo`.

For local development, start the NLP services from WSL:

```powershell
wsl -e bash -lc "cd /mnt/c/project/javeriana/repos/dragons_project_nlp/docker/network && docker compose up -d"
wsl -e bash -lc "cd /mnt/c/project/javeriana/repos/dragons_project_nlp/docker/mongo && docker compose up -d"
```

The default local URI is:

```text
mongodb://root:dragons_dev_password@localhost:50030/?authSource=admin
```

When the ETL runs inside the shared Docker network, use the Mongo alias:

```text
mongodb://root:dragons_dev_password@dragons-mongo:27017/?authSource=admin
```

Shared collections:

- `eventos`: event catalogue loaded from `data/events/DRAGONS_T1.csv`.
- `queries`: GDELT SQL and parameters generated for each event.
- `whitelist`: URL-level GDELT results and metadata.
- `media_cloud_sources`: raw Media Cloud listing rows loaded from CSV/XLSX files.
- `bluesky_posts`: public Bluesky social posts collected from `app.bsky.feed.searchPosts`.
- `threads_posts`: public Threads posts collected from keyword search.
- `threads_replies`: optional Threads conversation replies for posts with replies.
- `url_queue`: common URL queue across `source=gdelt` and `source=media_cloud`.
- `url_crawls`: HTML/text extraction attempts and metadata from the common crawler.
- `pipeline_runs`: compact audit summaries for operational runs.

Recommended 10-document local exercise:

```powershell
py -m pip install -r requirements.txt
py scripts\load_mediacloud.py --limit 10
py scripts\seed_sample_url_queue.py --source gdelt --strategy event_query_sample --limit 10
py scripts\run_url_crawler.py --source media_cloud --limit 10
py scripts\run_url_crawler.py --source gdelt --strategy event_query_sample --limit 10
py scripts\smoke_local_mongo.py
```

Bluesky social crawling writes directly to `bluesky_posts` because the source
already provides post text through the API. Each document keeps `source=bluesky`,
`source_type=social_post`, `texto_raw` with the original post text, and `text`
with the cleaned text for NLP.

Configure credentials in `.env` when the public endpoint rejects unauthenticated
search:

```text
BLUESKY_IDENTIFIER=your-handle.bsky.social
BLUESKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
```

Run a 10-post proof of concept:

```powershell
py scripts\run_bluesky.py --limit 10 --countries colombia united_kingdom hungary --since 2024-01-01 --until 2026-09-11 --max-pages-per-query 1
py scripts\export_mongo_sample.py --limit 10 --format both --output-dir data\mongo_exports\bluesky_poc_10
```

Threads social crawling writes directly to `threads_posts`; optional replies go
to `threads_replies`. Each document keeps `source=threads`, `source_type`
(`social_post` or `social_reply`), `texto_raw` with the original Threads text,
and `text` with the cleaned text for NLP.

Configure the Threads Graph API token in `.env`:

```text
THREADS_ACCESS_TOKEN=your-threads-access-token
```

Run a 10-post proof of concept:

```powershell
py scripts\run_threads.py --limit 10 --countries colombia united_kingdom hungary --since 2025-01-01 --until 2026-09-11 --max-pages-per-query 1
py scripts\export_mongo_sample.py --limit 10 --format both --output-dir data\mongo_exports\threads_poc_10
```

For local validation without the external API token:

```powershell
py scripts\run_threads.py --offline-sample --limit 10 --countries colombia --download-replies --max-conversation-posts 2
```

The same proof of concept can be run as one command. It loads 10 Media Cloud
rows, seeds 10 GDELT-like queue rows, crawls pending URLs from both sources, and
exports 10 documents per configured MongoDB collection:

```powershell
py scripts\run_url_poc_10.py
```

To keep the HTML/text extractor running as a process, use the queue crawler in
watch mode. It repeatedly reads `url_queue` for `pending`, `queued`, or `retry`
URLs, writes extracted HTML/text metadata into `url_crawls`, and marks each queue
record as `crawled` or `crawl_failed`.

```powershell
py scripts\run_url_crawler.py --watch --poll-seconds 60 --limit 10
```

For a bounded validation of the process loop:

```powershell
py scripts\run_url_crawler.py --watch --poll-seconds 5 --max-idle-cycles 3 --limit 10
```

The queue is idempotent by URL/source/strategy. Re-loading the same GDELT or
Media Cloud URL updates `last_seen_at` / `last_seen_run_id`, but does not put an
already crawled URL back into `pending`; only new URLs are picked up as new work.

For a real GDELT run, configure `GOOGLE_APPLICATION_CREDENTIALS`, then run
GDELT with scraping disabled so the common queue crawler owns URL extraction:

```powershell
py scripts\seed_events.py
py scripts\run_gdelt.py --max-events 1 --row-limit 10 --skip-scrape
py scripts\run_url_crawler.py --source gdelt --strategy event_query --limit 10
```

To inspect data across all configured MongoDB collections, including empty
collections:

```powershell
py scripts\export_mongo_sample.py --limit 10 --format both --output-dir data\mongo_exports\poc_10
```

---

## Relationship with DRAGONS Data Analytics

The overall architecture between both components is:

```text
Online sources
      │
      ▼
dragons-data-etl
      │
      ▼
    MongoDB
      │
      ▼
dragons-data-analytics
```

`dragons-data-etl` is responsible for data acquisition, transformation, validation, quality control, and storage.

`dragons-data-analytics` consumes the resulting data to build the analytical dataset and mining view, and to perform subsequent statistical, NLP, AI, and data-analysis processes.

---

## License

This project is distributed under the **Apache License 2.0**.

The licence applies to the source code contained in this repository. Data collected from external sources remain subject to the access, licensing, and usage conditions established by each source or data provider.

---

## Contact

**Technical & Data Analytics Lead**

**PhD Luis Gabriel Moreno Sandoval**

Pontificia Universidad Javeriana

📧 [morenoluis@javeriana.edu.co](mailto:morenoluis@javeriana.edu.co)
