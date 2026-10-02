from __future__ import annotations

import io
import json
import tempfile
import zipfile
from pathlib import Path

import streamlit as st

from tmx_processor.analyzer import DataAnalyzer
from tmx_processor.cleaner import CleanConfig, DataCleaner
from tmx_processor.converter import ConvertOptions, DataConverter, OutputFormat
from tmx_processor.deduper import DataDeduper
from tmx_processor.parser import TMXParser
from tmx_processor.validator import DataValidator

st.set_page_config(
    page_title="TMX Processor · Streamlit UI",
    page_icon="🗂️",
    layout="wide",
)

st.title("🗂️ TMX Processor")
st.caption("Платформа за почистване и подготовка на TMX езикови данни за AI обучение")
st.info(
    "За TMX файлове 500–1000 MiB използвайте FastAPI браузърния интерфейс: "
    "там е наличен disk-backed streaming режим до 1 GiB. Този Streamlit "
    "интерфейс държи обработваните единици в паметта."
)
st.link_button("Отвори FastAPI UI (localhost:8000)", "http://localhost:8000")

if "units" not in st.session_state:
    st.session_state.units = None
if "header" not in st.session_state:
    st.session_state.header = None

tab_upload, tab_clean, tab_dedupe, tab_validate, tab_export = st.tabs([
    "📥 Качване & Преглед",
    "🧼 Почистване",
    "🔁 Дедупликация",
    "✅ Валидация & Статистика",
    "💾 Експорт",
])

# ---------------- UPLOAD ----------------
with tab_upload:
    st.subheader("Качете .tmx файл")
    f = st.file_uploader("Изберете TMX файл", type=["tmx"])
    if f is not None:
        with tempfile.NamedTemporaryFile(suffix=".tmx", delete=False) as tmp:
            tmp.write(f.read())
            tmp_path = Path(tmp.name)
        parser = TMXParser(tmp_path)
        header = parser.parse_header()
        units = parser.parse_all()
        st.session_state.units = units
        st.session_state.header = header
        tmp_path.unlink(missing_ok=True)

    if st.session_state.units is not None:
        units = st.session_state.units
        h = st.session_state.header
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Общо TU", len(units))
        c2.metric("Изходен език", h.source_lang or "N/A")
        c3.metric("Инструмент", (h.creation_tool or "N/A")[:20])
        c4.metric("Тип сегменти", h.seg_type or "N/A")

        avail_langs = sorted(list({u.source_lang for u in units if u.source_lang} | {u.target_lang for u in units if u.target_lang}))
        avail_pairs = sorted(list({f"{u.source_lang}-{u.target_lang}" for u in units if u.source_lang and u.target_lang}))
        st.write(f"**Открити езици ({len(avail_langs)}):** {', '.join(avail_langs)}")
        st.write(f"**Налични езикови двойки ({len(avail_pairs)}):** {', '.join(avail_pairs)}")

        with st.expander("💡 Първите 10 единици"):
            rows = []
            for i, u in enumerate(units[:10]):
                rows.append({
                    "#": i+1,
                    "ID": u.tu_id,
                    "Език 1": u.source_lang,
                    "Текст 1": u.source_text[:150],
                    "Език 2": u.target_lang,
                    "Текст 2": u.target_text[:150],
                })
            st.dataframe(rows, use_container_width=True)

# ---------------- CLEAN ----------------
with tab_clean:
    st.subheader("Почистване и нормализация")
    u = st.session_state.units
    if u is None:
        st.info("Първо качете TMX файл в секцията 'Качване'.")
    else:
        with st.form("clean_form"):
            c1, c2 = st.columns(2)
            min_len = c1.number_input("Мин. дължина (знака)", 0, 100000, 1)
            max_len = c2.number_input("Макс. дължина (знака)", 1, 1000000, 10000)
            mw1, mw2 = st.columns(2)
            min_w = mw1.number_input("Мин. думи", 0, 10000, 0)
            max_w = mw2.number_input("Макс. думи", 0, 100000, 0)
            ratio = st.slider("Макс. съотношение по дължина", 1.1, 10.0, 3.0, 0.1)
            avail_pairs = sorted(list({f"{unit.source_lang}-{unit.target_lang}" for unit in u if unit.source_lang and unit.target_lang}))
            selected_pairs = st.multiselect("Филтрирай по конкретни езикови двойки (остави празно за всички)", options=avail_pairs, default=[])

            st.write("Опции:")
            cc1, cc2, cc3, cc4 = st.columns(4)
            rem_html = cc1.checkbox("Премахни HTML", True)
            rem_urls = cc2.checkbox("Премахни URL-ли", False)
            rem_emails = cc3.checkbox("Премахни имейли", False)
            lang_detect = cc4.checkbox("Езикова детекция", False)
            preserve_ph = st.checkbox("Запази placeholders", False)
            submitted = st.form_submit_button("🚀 Почисти данните")
        if submitted:
            cfg = CleanConfig(
                min_length=min_len, max_length=max_len,
                min_words=min_w, max_words=max_w,
                max_length_ratio=ratio,
                remove_html_tags=rem_html,
                remove_urls=rem_urls,
                remove_emails=rem_emails,
                lang_detect=lang_detect,
                preserve_placeholders=preserve_ph,
                language_pairs=selected_pairs if selected_pairs else None,
            )
            cleaner = DataCleaner(cfg)
            before = len(u)
            new_units = cleaner.clean_units(u)
            st.session_state.units = new_units
            s1, s2, s3 = st.columns(3)
            s1.metric("Преди", before)
            s2.metric("След", len(new_units))
            s3.metric("Премахнати", before - len(new_units),
                     delta=f"-{round(100*(before-len(new_units))/max(before,1),1)}%")

# ---------------- DEDUPE ----------------
with tab_dedupe:
    st.subheader("Точна и Fuzzy дедупликация")
    u = st.session_state.units
    if u is None:
        st.info("Няма данни за обработка.")
    else:
        fuzzy = st.checkbox("Включи fuzzy (MinHash LSH)", False)
        threshold = 0.9
        if fuzzy:
            threshold = st.slider("Fuzzy threshold", 0.5, 1.0, 0.9, 0.05)
        if st.button("🔁 Дедуплицирай"):
            dd = DataDeduper(exact=True, fuzzy=fuzzy, fuzzy_threshold=threshold)
            before = len(u)
            new_u = dd.dedupe(list(u))
            st.session_state.units = new_u
            d1, d2, d3 = st.columns(3)
            d1.metric("Преди", before)
            d2.metric("След", len(new_u))
            d3.metric("Премахнати", before - len(new_u))

# ---------------- VALIDATE + STATS ----------------
with tab_validate:
    st.subheader("Валидация и статистика")
    u = st.session_state.units
    if u is None:
        st.info("Няма данни.")
    else:
        val_col, stats_col = st.columns(2)
        with val_col:
            validator = DataValidator()
            rep = validator.report(u)
            st.markdown("#### Валидационен отчет")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Общо", rep["total"])
            m2.metric("Валидни", rep["valid"])
            m3.metric("Невалидни", rep["invalid"])
            m4.metric("%", f"{rep['valid_pct']:.1f}%")
            if rep["error_counts"]:
                st.write("Най-чести грешки:")
                st.dataframe(
                    [{"Грешка": k, "Брой": v} for k, v in rep["error_counts"].items()],
                    use_container_width=True, hide_index=True
                )
            if rep["warning_counts"]:
                st.write("Предупреждения:")
                st.dataframe(
                    [{"Предупреждение": k, "Брой": v} for k, v in rep["warning_counts"].items()],
                    use_container_width=True, hide_index=True
                )
        with stats_col:
            analyzer = DataAnalyzer()
            s = analyzer.analyze(u)
            st.markdown("#### Статистика")
            m = st.container()
            mm1, mm2 = m.columns(2)
            mm1.metric("Средна дължина изход (знака)", f"{s.avg_source_length:.1f}")
            mm2.metric("Средна дължина превод (знака)", f"{s.avg_target_length:.1f}")
            mm1.metric("Средна дължина изход (думи)", f"{s.avg_source_words:.1f}")
            mm2.metric("Средна дължина превод (думи)", f"{s.avg_target_words:.1f}")
            mm1.metric("Общо знаци (изход)", f"{s.total_source_chars:,}")
            mm2.metric("Общо знаци (превод)", f"{s.total_target_chars:,}")

            if s.language_pairs:
                st.write("Езикови двойки:")
                st.dataframe(
                    [{"Двойка": f"{a} → {b}", "Брой": c}
                     for (a, b), c in s.language_pairs.most_common()],
                    use_container_width=True, hide_index=True
                )

# ---------------- EXPORT ----------------
with tab_export:
    st.subheader("Експорт за AI обучение")
    u = st.session_state.units
    if u is None:
        st.info("Няма данни за експорт.")
    else:
        fmt_label = st.selectbox("Формат", [
            "JSONL (стандарт)", "Parquet", "CSV", "TSV", "JSON",
            "Alpaca (instruction)", "ShareGPT (chat)",
            "ChatML (messages)", "OpenAI (messages)",
            "DPO/ORPO (preference)", "Prompt/Completion", "Reasoning",
            "HF Dataset — train/val/test splits + ZIP"
        ])
        fmt_map = {
            "JSONL (стандарт)": OutputFormat.JSONL,
            "Parquet": OutputFormat.PARQUET,
            "CSV": OutputFormat.CSV,
            "TSV": OutputFormat.TSV,
            "JSON": OutputFormat.JSON,
            "Alpaca (instruction)": OutputFormat.ALPACA,
            "ShareGPT (chat)": OutputFormat.SHAREGPT,
            "ChatML (messages)": OutputFormat.CHATML,
            "OpenAI (messages)": OutputFormat.OPENAI,
            "DPO/ORPO (preference)": OutputFormat.DPO,
            "Prompt/Completion": OutputFormat.PROMPT_COMPLETION,
            "Reasoning": OutputFormat.REASONING,
            "HF Dataset — train/val/test splits + ZIP": OutputFormat.HF_DATASET,
        }
        fmt = fmt_map[fmt_label]

        ec1, ec2 = st.columns(2)
        inc_meta = ec1.checkbox("Включи metadata", False)
        inc_id = ec2.checkbox("Включи TU ID", False)
        instr = ""
        if fmt in (OutputFormat.ALPACA, OutputFormat.SHAREGPT, OutputFormat.CHATML, OutputFormat.OPENAI, OutputFormat.DPO, OutputFormat.PROMPT_COMPLETION, OutputFormat.REASONING):
            instr = st.text_input("Персонализирана инструкция (по желание)",
                                  placeholder="Остави празно за автоматична")

        if st.button("💾 Генерирай и свали"):
            opts = ConvertOptions(
                include_metadata=inc_meta, include_id=inc_id,
                instruction_template=instr or None
            )
            converter = DataConverter(options=opts)
            with tempfile.TemporaryDirectory() as td:
                td_path = Path(td)
                if fmt == OutputFormat.HF_DATASET:
                    folder = td_path / "hf_splits"
                    converter.convert(u, folder, fmt)
                    buf = io.BytesIO()
                    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                        for p in folder.rglob("*"):
                            if p.is_file():
                                zf.write(p, arcname=p.relative_to(td_path))
                    buf.seek(0)
                    st.download_button(
                        "⬇️ Свали HF Dataset ZIP",
                        data=buf.getvalue(),
                        file_name="hf_dataset.zip",
                        mime="application/zip",
                    )
                else:
                    suffixes = {
                        OutputFormat.JSONL: ".jsonl", OutputFormat.PARQUET: ".parquet",
                        OutputFormat.CSV: ".csv", OutputFormat.TSV: ".tsv",
                        OutputFormat.JSON: ".json", OutputFormat.ALPACA: ".jsonl",
                        OutputFormat.SHAREGPT: ".jsonl", OutputFormat.CHATML: ".jsonl",
                        OutputFormat.OPENAI: ".jsonl", OutputFormat.DPO: ".jsonl",
                        OutputFormat.PROMPT_COMPLETION: ".jsonl", OutputFormat.REASONING: ".jsonl",
                    }
                    out = td_path / f"output{suffixes[fmt]}"
                    converter.convert(u, out, fmt)
                    with open(out, "rb") as f:
                        data = f.read()
                    st.download_button(
                        f"⬇️ Свали {out.name}",
                        data=data,
                        file_name=out.name,
                        mime="application/octet-stream",
                    )
