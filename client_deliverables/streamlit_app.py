from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="Breast Cancer AI Demo",
    page_icon="🧬",
    layout="wide",
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"

FEATURES = [
    "menopaus",
    "agegrp",
    "density",
    "race",
    "hispanic",
    "bmi",
    "agefirst",
    "nrelbc",
    "brstproc",
    "lastmamm",
    "surgmeno",
    "hrt",
]

LABEL_MAPS = {
    "menopaus": {"0": "Premenopausal", "1": "Postmenopausal or age >=55", "9": "Unknown"},
    "agegrp": {"1": "35-39", "2": "40-44", "3": "45-49", "4": "50-54", "5": "55-59", "6": "60-64", "7": "65-69", "8": "70-74", "9": "75-79", "10": "80-84"},
    "density": {"1": "Almost entirely fat", "2": "Scattered fibroglandular densities", "3": "Heterogeneously dense", "4": "Extremely dense", "9": "Unknown/different system"},
    "race": {"1": "White", "2": "Asian/Pacific Islander", "3": "Black", "4": "Native American", "5": "Other/mixed", "9": "Unknown"},
    "hispanic": {"0": "No", "1": "Yes", "9": "Unknown"},
    "bmi": {"1": "10-24.99", "2": "25-29.99", "3": "30-34.99", "4": "35+", "9": "Unknown"},
    "agefirst": {"0": "Age <30 at first birth", "1": "Age >=30 at first birth", "2": "Nulliparous", "9": "Unknown"},
    "nrelbc": {"0": "0 first-degree relatives", "1": "1 first-degree relative", "2": "2+ first-degree relatives", "9": "Unknown"},
    "brstproc": {"0": "No previous breast procedure", "1": "Previous breast procedure", "9": "Unknown"},
    "lastmamm": {"0": "Previous mammogram negative", "1": "Previous mammogram false positive", "9": "Unknown"},
    "surgmeno": {"0": "Natural menopause", "1": "Surgical menopause", "9": "Unknown/not menopausal"},
    "hrt": {"0": "No current hormone therapy", "1": "Current hormone therapy", "9": "Unknown/not menopausal"},
}

CURATED_GENE_SUPPORT = {
    "ERBB2": "HER2/ERBB2 signal: consider HER2 pathway review and targeted therapy eligibility if clinically confirmed.",
    "ESR1": "ESR1 signal: hormone receptor / endocrine pathway involvement may be clinically relevant.",
    "PGR": "PGR signal: progesterone receptor pathway involvement may support hormone-pathway review.",
    "TP53": "TP53 abnormal signal: often associated with aggressive biology and DNA-damage pathway disruption.",
    "BRCA1": "BRCA1 signal: DNA repair pathway; genetic/HRD review may be relevant if clinically confirmed.",
    "BRCA2": "BRCA2 signal: DNA repair pathway; genetic/HRD review may be relevant if clinically confirmed.",
    "MKI67": "MKI67 high signal: proliferation marker that may suggest aggressive growth behavior.",
    "EGFR": "EGFR high signal: growth-factor pathway signal, often relevant in basal-like biology.",
    "KRT5": "KRT5 high signal: basal-like cytokeratin pattern.",
    "KRT14": "KRT14 high signal: basal-like cytokeratin pattern.",
    "KRT17": "KRT17 high signal: basal-like cytokeratin pattern.",
    "CDH1": "CDH1 abnormal signal: cell-adhesion pathway; may be relevant in lobular-like biology.",
}


@st.cache_data(show_spinner=False)
def load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def load_csv(path: str, nrows: int | None = None) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p, nrows=nrows)


@st.cache_resource(show_spinner=False)
def load_model(path: str):
    return joblib.load(path)


def metric_value(data: dict, *keys, default="NA"):
    cur = data
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    if isinstance(cur, float):
        return f"{cur:.3f}"
    return cur


def risk_band(percent: float) -> str:
    if percent < 0.25:
        return "Very low"
    if percent < 0.5:
        return "Low"
    if percent < 1.0:
        return "Moderate"
    return "Higher"


def show_image(path: Path, caption: str | None = None):
    if path.exists():
        st.image(str(path), caption=caption, use_container_width=True)
    else:
        st.warning(f"Missing image: {path}")


def select_code(feature: str, default: str):
    mapping = LABEL_MAPS[feature]
    options = list(mapping.keys())
    index = options.index(default) if default in options else 0
    return st.selectbox(
        feature,
        options=options,
        index=index,
        format_func=lambda code: f"{code} - {mapping[code]}",
    )


def prepare_gene_expression_table(raw: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Accept wide or long gene-expression CSVs and return samples x genes."""
    df = raw.copy()
    df.columns = [str(c).strip() for c in df.columns]
    lower_cols = {c.lower().replace(" ", "_"): c for c in df.columns}

    gene_col = None
    for key in ["hugo_symbol", "gene", "gene_symbol", "symbol", "genes"]:
        if key in lower_cols:
            gene_col = lower_cols[key]
            break

    if gene_col is not None:
        candidate_value_cols = [c for c in df.columns if c != gene_col]
        numeric_values = df[candidate_value_cols].apply(pd.to_numeric, errors="coerce")
        numeric_values = numeric_values.dropna(axis=1, how="all")
        if numeric_values.empty:
            raise ValueError("Long-format file detected, but no numeric expression value columns were found.")
        genes = df[gene_col].astype(str).str.strip()
        long_expr = numeric_values.copy()
        long_expr.insert(0, "gene", genes)
        long_expr = long_expr.groupby("gene", sort=False).mean(numeric_only=True)
        expr = long_expr.T
        expr.index = [str(idx) for idx in expr.index]
        return expr, "long format: one gene column and one or more sample/value columns"

    id_col = None
    for candidate in ["sample_id", "patient_id", "case_submitter_id", "id"]:
        if candidate in lower_cols:
            id_col = lower_cols[candidate]
            break

    metadata_cols = {
        "label",
        "sample_type",
        "vital_status",
        "ajcc_pathologic_stage",
        "cancer_prediction",
        "risk_prediction",
        "subtype",
    }
    drop_cols = []
    for col in df.columns:
        normalized = col.lower().replace(" ", "_")
        if col == id_col or normalized in metadata_cols:
            drop_cols.append(col)

    expr = df.drop(columns=drop_cols, errors="ignore")
    expr = expr.apply(pd.to_numeric, errors="coerce")
    expr = expr.dropna(axis=1, how="all")
    if expr.empty:
        raise ValueError("Wide-format file detected, but no numeric gene-expression columns were found.")
    if id_col is not None:
        expr.index = df[id_col].astype(str)
    else:
        expr.index = [f"uploaded_sample_{i+1}" for i in range(len(expr))]
    return expr, "wide format: one row per sample and one column per gene"


def align_expression_to_model(expr: pd.DataFrame, model, min_coverage: float = 0.70):
    required = list(getattr(model, "feature_names_in_", []))
    if not required:
        raise ValueError("This model does not expose feature_names_in_, so upload alignment is not available.")

    exact_map = {str(col): col for col in expr.columns}
    upper_map = {str(col).strip().upper(): col for col in expr.columns}

    aligned = pd.DataFrame(index=expr.index)
    found = []
    missing = []
    for gene in required:
        source = exact_map.get(gene)
        if source is None:
            source = upper_map.get(str(gene).strip().upper())
        if source is None:
            aligned[gene] = pd.NA
            missing.append(gene)
        else:
            aligned[gene] = pd.to_numeric(expr[source], errors="coerce")
            found.append(gene)

    coverage = len(found) / len(required) if required else 0
    if coverage < min_coverage:
        return None, found, missing, coverage
    return aligned, found, missing, coverage


def binary_probability(model, aligned: pd.DataFrame) -> list[float]:
    if hasattr(model, "predict_proba"):
        return (model.predict_proba(aligned)[:, 1] * 100).tolist()
    scores = model.decision_function(aligned)
    scores = 1 / (1 + pd.Series(-scores).map(lambda x: __import__("math").exp(x)))
    return (scores * 100).tolist()


def uploaded_gene_support(expr: pd.DataFrame, sample_id: str) -> str:
    if sample_id not in expr.index:
        return "No support flags available."
    row = expr.loc[sample_id]
    flags = []
    upper_map = {str(col).strip().upper(): col for col in expr.columns}
    for gene, insight in CURATED_GENE_SUPPORT.items():
        col = upper_map.get(gene)
        if col is None:
            continue
        value = pd.to_numeric(pd.Series([row[col]]), errors="coerce").iloc[0]
        if pd.isna(value):
            continue
        if value >= 2:
            flags.append(f"{gene} high ({value:.2f}): {insight}")
        elif value <= -2:
            flags.append(f"{gene} low ({value:.2f}): clinically relevant abnormal expression pattern; {insight}")
    return "; ".join(flags) if flags else "No curated extreme-expression support flags found. For best results, upload z-score normalized expression."


st.title("Breast Cancer AI Project Demo")
st.caption("Cancer signature, future incidence risk, subtype prediction, prognosis, and gene correlation analysis")

page = st.sidebar.radio(
    "Sections",
    [
        "Overview",
        "Upload Gene Expression",
        "Future Risk Percent",
        "Cancer Signature",
        "Tumor Subtype",
        "Prognosis",
        "Gene Correlation",
        "Figures",
        "Report Files",
    ],
)

tcga_metrics = load_json(str(OUT / "tcga_brca_cells" / "cancer_prediction" / "cancer_holdout_metrics.json"))
bcsc_metrics = load_json(str(OUT / "bcsc_future_risk_prediction" / "bcsc_future_risk_metrics.json"))
subtype_metrics = load_json(str(OUT / "tumor_subtype_prediction" / "tumor_subtype_metrics.json"))
survival_metrics = load_json(str(OUT / "metabric_optimized_prognosis" / "survival_best_metrics.json"))
recurrence_metrics = load_json(str(OUT / "metabric_optimized_prognosis" / "recurrence_best_metrics.json"))
corr_summary = load_json(str(OUT / "gene_correlation_pattern_analysis" / "gene_correlation_pattern_summary.json"))
upload_gene_metrics = load_json(str(OUT / "streamlit_upload_gene_models" / "upload_gene_models_metrics.json"))

if page == "Overview":
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("TCGA Cancer AUC", metric_value(tcga_metrics, "roc_auc"))
    c2.metric("BCSC Future Risk AUC", metric_value(bcsc_metrics, "validation", "roc_auc"))
    c3.metric("Subtype Balanced Acc", metric_value(subtype_metrics, "holdout_balanced_accuracy_from_previous_training"))
    c4.metric("Strong Gene Pairs", corr_summary.get("strong_pairs_abs_ge_0_45", "NA"))

    st.subheader("What this demo covers")
    st.write(
        """
        The project separates four clinical questions: cancer-like molecular signature,
        future incidence risk percentage, tumor subtype, and prognosis.
        This separation is important scientifically because every task needs different labels.
        """
    )

    rows = [
        ["Cancer signature", "TCGA-BRCA", "Cancer vs Normal", metric_value(tcga_metrics, "roc_auc")],
        ["Future incidence risk", "BCSC", "1-year future diagnosis risk", metric_value(bcsc_metrics, "validation", "roc_auc")],
        ["Tumor subtype", "METABRIC", "Real CLAUDIN subtype", metric_value(subtype_metrics, "holdout_balanced_accuracy_from_previous_training")],
        ["Survival prognosis", "METABRIC", "Overall survival event", metric_value(survival_metrics, "holdout_roc_auc")],
        ["Recurrence prognosis", "METABRIC", "Recurrence event", metric_value(recurrence_metrics, "holdout_roc_auc")],
    ]
    st.dataframe(pd.DataFrame(rows, columns=["Part", "Dataset", "Target", "Main metric"]), use_container_width=True)

elif page == "Upload Gene Expression":
    st.subheader("Upload Gene Expression CSV")
    st.write(
        """
        Upload a gene-expression CSV to run available gene-based modules on new samples.
        Supported formats:

        1. Wide format: one row per sample and one column per gene.
        2. Long format: one gene column such as `Hugo_Symbol` or `gene`, plus one or more numeric sample/value columns.
        """
    )
    st.info(
        "Cancer Detection and Subtype Prediction need broad gene-expression coverage. "
        "Survival and Recurrence here use gene-expression-only upload models, separate from the optimized clinical+gene prognosis models."
    )

    uploaded = st.file_uploader("Upload gene-expression CSV", type=["csv"], key="gene_expression_upload")

    cancer_model_path = OUT / "tcga_brca_cells" / "cancer_prediction" / "cancer_prediction_model.joblib"
    subtype_model_path = OUT / "metabric_real_label_prognosis" / "subtype_model.joblib"
    survival_upload_model_path = OUT / "streamlit_upload_gene_models" / "survival_gene_expression_upload_model.joblib"
    recurrence_upload_model_path = OUT / "streamlit_upload_gene_models" / "recurrence_gene_expression_upload_model.joblib"

    with st.expander("Download an empty template header"):
        if cancer_model_path.exists():
            model = load_model(str(cancer_model_path))
            template_cols = ["sample_id"] + list(getattr(model, "feature_names_in_", []))
            template = pd.DataFrame([["sample_1"] + [None] * (len(template_cols) - 1)], columns=template_cols)
            st.download_button(
                "Download TCGA cancer model gene template",
                template.to_csv(index=False).encode("utf-8"),
                "tcga_gene_expression_template.csv",
                "text/csv",
            )
        if subtype_model_path.exists():
            model = load_model(str(subtype_model_path))
            template_cols = ["sample_id"] + list(getattr(model, "feature_names_in_", []))
            template = pd.DataFrame([["sample_1"] + [None] * (len(template_cols) - 1)], columns=template_cols)
            st.download_button(
                "Download METABRIC subtype/prognosis gene template",
                template.to_csv(index=False).encode("utf-8"),
                "metabric_gene_expression_template.csv",
                "text/csv",
            )

    if uploaded is not None:
        raw = pd.read_csv(uploaded)
        try:
            expr, detected_format = prepare_gene_expression_table(raw)
        except Exception as exc:
            st.error(f"Could not parse uploaded file: {exc}")
            st.stop()

        st.success(f"Parsed {expr.shape[0]} sample(s) and {expr.shape[1]} numeric gene column(s) from {detected_format}.")
        st.dataframe(expr.head(), use_container_width=True)

        results = pd.DataFrame(index=expr.index)
        results.index.name = "sample_id"

        model_tasks = [
            ("Cancer Detection", cancer_model_path, "cancer_signature_probability_percent", 0.70),
            ("Gene-only Survival", survival_upload_model_path, "survival_event_probability_percent", 0.70),
            ("Gene-only Recurrence", recurrence_upload_model_path, "recurrence_event_probability_percent", 0.70),
        ]

        for task_name, model_path, output_col, min_coverage in model_tasks:
            if not model_path.exists():
                st.warning(f"{task_name} model file is missing: {model_path.name}")
                continue
            model = load_model(str(model_path))
            aligned, found, missing, coverage = align_expression_to_model(expr, model, min_coverage=min_coverage)
            st.write(f"{task_name} gene coverage: **{coverage*100:.1f}%** ({len(found)} / {len(found) + len(missing)})")
            if aligned is None:
                st.warning(f"{task_name} skipped because coverage is below {min_coverage*100:.0f}%. First missing genes: {missing[:20]}")
                continue
            probs = binary_probability(model, aligned)
            results[output_col] = probs
            if task_name == "Cancer Detection":
                results["cancer_detection_prediction"] = ["Cancer-like" if p >= 50 else "Normal-like" for p in probs]
            elif task_name == "Gene-only Survival":
                threshold = upload_gene_metrics.get("survival", {}).get("threshold", 0.5) * 100
                results["survival_risk_group"] = ["High risk" if p >= threshold else "Lower risk" for p in probs]
            elif task_name == "Gene-only Recurrence":
                threshold = upload_gene_metrics.get("recurrence", {}).get("threshold", 0.5) * 100
                results["recurrence_risk_group"] = ["High risk" if p >= threshold else "Lower risk" for p in probs]

        if subtype_model_path.exists():
            subtype_model = load_model(str(subtype_model_path))
            aligned, found, missing, coverage = align_expression_to_model(expr, subtype_model, min_coverage=0.70)
            st.write(f"Subtype Prediction gene coverage: **{coverage*100:.1f}%** ({len(found)} / {len(found) + len(missing)})")
            if aligned is not None:
                subtype_probs = subtype_model.predict_proba(aligned)
                classes = list(subtype_model.classes_)
                best_idx = subtype_probs.argmax(axis=1)
                results["predicted_subtype"] = [classes[i] for i in best_idx]
                results["subtype_confidence_percent"] = [float(subtype_probs[row_i, best_idx[row_i]] * 100) for row_i in range(len(best_idx))]
                for class_idx, class_name in enumerate(classes):
                    results[f"subtype_probability_{class_name}_percent"] = subtype_probs[:, class_idx] * 100
            else:
                st.warning(f"Subtype Prediction skipped because coverage is below 70%. First missing genes: {missing[:20]}")
        else:
            st.warning("Subtype model file is missing.")

        results["therapeutic_support_flags"] = [uploaded_gene_support(expr, sample_id) for sample_id in results.index]

        st.subheader("Uploaded Sample Predictions")
        st.dataframe(results.reset_index(), use_container_width=True)
        st.download_button(
            "Download uploaded-sample predictions",
            results.reset_index().to_csv(index=False).encode("utf-8"),
            "uploaded_gene_expression_predictions.csv",
            "text/csv",
        )

        if "cancer_signature_probability_percent" in results.columns:
            st.bar_chart(results["cancer_signature_probability_percent"])
        if "predicted_subtype" in results.columns:
            st.write("Subtype distribution")
            st.bar_chart(results["predicted_subtype"].value_counts())

elif page == "Future Risk Percent":
    st.subheader("Future Breast Cancer Risk Percentage")
    st.info(
        "This model predicts one-year breast cancer diagnosis risk after screening mammography. "
        "It is not a gene-expression model and not a lifetime risk model."
    )
    model_path = OUT / "bcsc_future_risk_prediction" / "bcsc_future_risk_model.joblib"
    if not model_path.exists():
        st.error("BCSC model file was not found.")
    else:
        defaults = {
            "menopaus": "1",
            "agegrp": "8",
            "density": "4",
            "race": "1",
            "hispanic": "0",
            "bmi": "4",
            "agefirst": "1",
            "nrelbc": "2",
            "brstproc": "1",
            "lastmamm": "1",
            "surgmeno": "0",
            "hrt": "1",
        }
        cols = st.columns(3)
        profile = {}
        for i, feature in enumerate(FEATURES):
            with cols[i % 3]:
                profile[feature] = select_code(feature, defaults.get(feature, list(LABEL_MAPS[feature])[0]))

        if st.button("Predict future risk percentage", type="primary"):
            model = load_model(str(model_path))
            row = pd.DataFrame([profile], columns=FEATURES).astype(str)
            percent = float(model.predict_proba(row)[0, 1] * 100)
            st.metric("Predicted 1-year risk", f"{percent:.3f}%")
            st.write(f"Risk band: **{risk_band(percent)}**")
            st.dataframe(row, use_container_width=True)

        show_image(OUT / "bcsc_future_risk_prediction" / "figures" / "02_bcsc_roc_curve.png", "BCSC validation ROC")
        show_image(OUT / "bcsc_future_risk_prediction" / "figures" / "04_bcsc_calibration.png", "BCSC calibration")

elif page == "Cancer Signature":
    st.subheader("TCGA Cancer Molecular Signature")
    st.warning(
        "This predicts whether the expression pattern is cancer-like versus normal-like. "
        "It should not be described as future incidence risk."
    )
    df = load_csv(str(OUT / "patient_probability_percentages" / "tcga_patient_cancer_and_risk_percentages.csv"))
    if df.empty:
        st.error("TCGA patient-level predictions file was not found.")
    else:
        label_col = "case_submitter_id"
        selected = st.selectbox("Select TCGA case", df[label_col].astype(str).head(1000).tolist())
        row = df[df[label_col].astype(str) == selected].iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("Cancer signature probability", f"{row.get('cancer_signature_probability_percent', 0):.2f}%")
        c2.metric("Cancer prediction", str(row.get("cancer_prediction", "NA")))
        c3.metric("Prognostic risk", f"{row.get('prognostic_risk_probability_percent', 0):.2f}%")
        st.write("Gene reasons")
        st.write(row.get("cancer_gene_reasons", "NA"))
        st.write("Doctor support flags")
        st.write(row.get("doctor_support_flags", "NA"))
        st.dataframe(pd.DataFrame([row]), use_container_width=True)

    with st.expander("Optional: upload a full TCGA gene-expression CSV for cancer signature prediction"):
        st.write("The uploaded file must contain all genes expected by the saved TCGA model.")
        uploaded = st.file_uploader("Upload CSV", type=["csv"], key="tcga_upload")
        if uploaded is not None:
            model_path = OUT / "tcga_brca_cells" / "cancer_prediction" / "cancer_prediction_model.joblib"
            model = load_model(str(model_path))
            input_df = pd.read_csv(uploaded)
            required = list(getattr(model, "feature_names_in_", []))
            missing = [col for col in required if col not in input_df.columns]
            if missing:
                st.error(f"Missing {len(missing)} required genes. First missing genes: {missing[:20]}")
            else:
                probs = model.predict_proba(input_df[required])[:, 1] * 100
                out = input_df.copy()
                out["cancer_signature_probability_percent"] = probs
                out["prediction"] = ["Cancer Signature" if p >= 50 else "Normal-like" for p in probs]
                st.dataframe(out[["cancer_signature_probability_percent", "prediction"]], use_container_width=True)

    show_image(OUT / "tcga_brca_cells" / "cancer_prediction" / "figures" / "cancer_top_genes.png", "Top cancer signature genes")

elif page == "Tumor Subtype":
    st.subheader("METABRIC Tumor Subtype Prediction")
    df = load_csv(str(OUT / "tumor_subtype_prediction" / "metabric_tumor_subtype_predictions_with_percentages.csv"))
    if df.empty:
        st.error("Subtype prediction file was not found.")
    else:
        selected = st.selectbox("Select METABRIC patient", df["PATIENT_ID"].astype(str).head(1500).tolist())
        row = df[df["PATIENT_ID"].astype(str) == selected].iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("Predicted subtype", str(row.get("predicted_molecular_subtype", "NA")))
        c2.metric("Confidence", f"{row.get('subtype_confidence_percent', 0):.2f}%")
        c3.metric("True subtype", str(row.get("true_molecular_subtype", "NA")))
        prob_cols = [c for c in df.columns if c.startswith("probability_")]
        st.bar_chart(pd.DataFrame(row[prob_cols]).rename(columns={row.name: "percent"}))
        st.write(row.get("subtype_support_note", ""))
        st.dataframe(pd.DataFrame([row]), use_container_width=True)

    show_image(OUT / "tumor_subtype_prediction" / "figures" / "03_subtype_confusion_matrix_all_labeled.png", "Subtype confusion matrix")
    show_image(OUT / "tumor_subtype_prediction" / "figures" / "05_top_subtype_genes.png", "Top subtype genes")

elif page == "Prognosis":
    st.subheader("Survival and Recurrence Prognosis")
    df = load_csv(str(OUT / "patient_probability_percentages" / "metabric_patient_prognosis_percentages.csv"))
    if df.empty:
        st.error("METABRIC prognosis percentage file was not found.")
    else:
        selected = st.selectbox("Select METABRIC patient", df["PATIENT_ID"].astype(str).head(1500).tolist(), key="prog_patient")
        row = df[df["PATIENT_ID"].astype(str) == selected].iloc[0]
        c1, c2 = st.columns(2)
        c1.metric("Survival event probability", f"{row.get('survival_event_probability_percent', 0):.2f}%")
        c1.write(row.get("survival_risk_group", "NA"))
        c2.metric("Recurrence event probability", f"{row.get('recurrence_event_probability_percent', 0):.2f}%")
        c2.write(row.get("recurrence_risk_group", "NA"))
        st.write("Survival top features")
        st.write(row.get("survival_top_features", "NA"))
        st.write("Recurrence top features")
        st.write(row.get("recurrence_top_features", "NA"))
        st.dataframe(pd.DataFrame([row]), use_container_width=True)

    show_image(OUT / "metabric_optimized_prognosis" / "figures" / "04_holdout_roc_curves.png", "METABRIC holdout ROC curves")
    show_image(OUT / "metabric_optimized_prognosis" / "figures" / "06_kaplan_meier_risk_groups.png", "Kaplan Meier risk groups")

elif page == "Gene Correlation":
    st.subheader("Gene Correlation and Expression Patterns")
    corr = load_csv(str(OUT / "gene_correlation_pattern_analysis" / "gene_gene_spearman_correlation_matrix.csv"), nrows=None)
    pairs = load_csv(str(OUT / "gene_correlation_pattern_analysis" / "strong_gene_correlation_pairs_abs_ge_0_45.csv"))
    expr = load_csv(str(OUT / "gene_correlation_pattern_analysis" / "selected_gene_expression_zscores.csv"))

    if not pairs.empty:
        st.write("Strongest gene-gene relationships")
        st.dataframe(pairs.head(50), use_container_width=True)

    if not corr.empty:
        genes = corr.columns[1:].tolist() if corr.columns[0].lower().startswith("unnamed") or corr.columns[0] not in corr.columns[1:] else corr.columns.tolist()
        if corr.columns[0] not in genes:
            corr = corr.set_index(corr.columns[0])
        col1, col2 = st.columns(2)
        with col1:
            gene_a = st.selectbox("Gene A", corr.index.astype(str).tolist(), index=0)
        with col2:
            gene_b = st.selectbox("Gene B", corr.columns.astype(str).tolist(), index=min(1, len(corr.columns) - 1))
        try:
            value = float(corr.loc[gene_a, gene_b])
            st.metric("Spearman correlation", f"{value:.3f}")
        except Exception:
            st.warning("Could not calculate this pair from the matrix.")

    if not expr.empty:
        id_cols = [c for c in ["PATIENT_ID", "SAMPLE_ID", "true_molecular_subtype"] if c in expr.columns]
        gene_cols = [c for c in expr.columns if c not in id_cols]
        patient = st.selectbox("Expression pattern patient", expr[id_cols[0]].astype(str).head(500).tolist(), key="expr_patient")
        selected_genes = st.multiselect("Genes to plot", gene_cols, default=gene_cols[:8])
        row = expr[expr[id_cols[0]].astype(str) == patient].iloc[0]
        if selected_genes:
            st.bar_chart(pd.DataFrame({"zscore": row[selected_genes].astype(float)}))

    show_image(OUT / "gene_correlation_pattern_analysis" / "figures" / "01_gene_gene_correlation_heatmap.png", "Gene-gene correlation heatmap")
    show_image(OUT / "gene_correlation_pattern_analysis" / "figures" / "04_strong_gene_correlation_network.png", "Strong gene correlation network")

elif page == "Figures":
    st.subheader("Main Output Figures")
    figure_paths = [
        OUT / "tcga_brca_cells" / "cancer_prediction" / "figures" / "cancer_roc_curve.png",
        OUT / "bcsc_future_risk_prediction" / "figures" / "02_bcsc_roc_curve.png",
        OUT / "tumor_subtype_prediction" / "figures" / "03_subtype_confusion_matrix_all_labeled.png",
        OUT / "metabric_optimized_prognosis" / "figures" / "04_holdout_roc_curves.png",
        OUT / "geo_external_validation" / "figures" / "05_external_roc_curves.png",
        OUT / "gene_correlation_pattern_analysis" / "figures" / "01_gene_gene_correlation_heatmap.png",
        OUT / "gene_correlation_pattern_analysis" / "figures" / "05_gene_pair_scatter_patterns.png",
    ]
    for path in figure_paths:
        show_image(path, path.name)

elif page == "Report Files":
    st.subheader("Generated Deliverables")
    deliverables = ROOT / "client_deliverables"
    files = [
        deliverables / "breast_cancer_ai_unified_client_notebook.ipynb",
        deliverables / "final_client_report.md",
        deliverables / "README_CLIENT_DELIVERABLES.md",
    ]
    for file in files:
        if file.exists():
            st.write(f"✅ `{file}`")
        else:
            st.write(f"❌ `{file}`")

    report_path = deliverables / "final_client_report.md"
    if report_path.exists():
        with st.expander("Preview final report"):
            st.markdown(report_path.read_text(encoding="utf-8"))
