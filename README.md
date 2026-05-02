# Tumor Likelihood Tool

A Bayesian tumor-type likelihood ranking tool that predicts the most likely cancer type from somatic mutations and copy number alterations found in targeted panel sequencing.

Built on enrichment statistics from **226,813 samples** across **23 tumor types** in the [AACR GENIE](https://www.aacr.org/professionals/research/aacr-project-genie/) v18 dataset.

## How It Works

Enter mutations (e.g., `BRAF p.V600E`) and/or copy number alterations (e.g., `CDKN2A DeepDeletion`). The tool:

1. Looks up pre-computed enrichment statistics for each alteration
2. Combines evidence using a naive Bayes framework with empirical priors
3. Returns ranked tumor types with posterior probabilities and supporting evidence

Results are shown at two levels:
- **Tumor Type** (23 broad categories, e.g., "SKIN_AND_MELANOMA")
- **Cancer Type Detailed** (200+ specific diagnoses, e.g., "Cutaneous Melanoma")

## Caveats

1. **For research use and clinical decision support only.** Not a standalone diagnostic device. Outputs may be incomplete or incorrect and must be reviewed by qualified experts in the full clinical, laboratory, and histopathological context. The authors assume no responsibility for clinical decisions or other consequences of use.
2. Tumor likelihoods depend on the submitted alterations, the panel content, and the representativeness of the AACR GENIE cohort; results should be interpreted together with morphology, immunophenotype, clinical history, and local assay validation.

## Quick Start

```bash
# Install dependencies
pip install -e .

# Run the server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then open http://localhost:8000.

## API

### `POST /api/v1/predict`

```json
{
  "alterations": [
    {"kind": "mutation", "gene": "BRAF", "protein": "p.V600E"},
    {"kind": "cna", "gene": "CDKN2A", "cna_state": "DeepDeletion"}
  ],
  "options": {"return_top_k": 10, "include_evidence": true}
}
```

### `GET /api/v1/meta`

Returns model metadata, supported CNA states, and class priors.

### `GET /health`

Health check with model readiness status.

## Data Artifacts

Pre-built data files in `data/` contain the enrichment evidence:

| File | Description |
|------|-------------|
| `evidence_tumor.parquet` | Enrichment events at tumor-type level (incl. gene pairs) |
| `evidence_detailed.parquet` | Enrichment events at detailed cancer type level |
| `priors_tumor.json` | Empirical class priors (23 tumor types) |
| `priors_detailed.json` | Empirical class priors (200+ detailed types) |
| `event_catalog.json` | Supported genes, CNA states, example queries |
| `tumor_mapping.json` | Tumor type to detailed subtype mapping |

These are generated from the enrichment analysis pipeline using `scripts/build_indices.py`.

## Testing

```bash
pip install -e ".[test]"
pytest
```

## Deployment

### Docker (local)

```bash
docker build -t tumor-likelihood-tool .
docker run -p 8000:8000 tumor-likelihood-tool
```

### Google Cloud Run

```bash
# Set your project
export PROJECT_ID=your-gcp-project-id
export REGION=europe-west1

# Build and push to Artifact Registry
gcloud artifacts repositories create tumor-tool --repository-format=docker --location=${REGION} 2>/dev/null
gcloud builds submit --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/tumor-tool/tumor-likelihood-tool

# Deploy to Cloud Run
gcloud run deploy tumor-likelihood-tool \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/tumor-tool/tumor-likelihood-tool \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 3
```

The app reads `$PORT` from the environment (set automatically by Cloud Run). 512 Mi memory is sufficient — the model artifacts are ~34 MB and load on first request.

## Citation

If you use this tool, please cite:

> [Publication details TBD]

## License

MIT
