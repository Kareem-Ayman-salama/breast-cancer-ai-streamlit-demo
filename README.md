# Breast Cancer AI Streamlit Demo

Interactive demo for the Breast Cancer AI project.

## Main App

Use this file as the Streamlit entry point:

```text
client_deliverables/streamlit_app.py
```

## Run Locally

```powershell
pip install -r requirements.txt
python -m streamlit run client_deliverables/streamlit_app.py
```

## Streamlit Community Cloud

1. Push this folder to a GitHub repository.
2. Open [Streamlit Community Cloud](https://share.streamlit.io/).
3. Click **New app**.
4. Choose the GitHub repo and branch.
5. Set the main file path to:

```text
client_deliverables/streamlit_app.py
```

6. Deploy and copy the public app link.

## Included Components

- Future breast cancer risk percentage using BCSC.
- TCGA cancer molecular signature review.
- METABRIC tumor subtype prediction review.
- METABRIC survival and recurrence prognosis review.
- Upload Gene Expression page for testing new CSV gene-expression files.
- Gene-gene correlation and expression pattern review.
- Client reports in Markdown, HTML, and Word.

## Gene Expression Upload Test File

The repository includes a small public METABRIC-style sample file:

```text
sample_gene_expression_upload_metabric.csv
```

Upload it in the Streamlit **Upload Gene Expression** page to test subtype and gene-only prognosis predictions immediately.

## Scientific Note

TCGA cancer signature prediction is not future incidence prediction. Future risk percentage is handled separately using BCSC because it has real follow-up diagnosis labels.
