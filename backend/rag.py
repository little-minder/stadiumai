"""
AI Fan Assistant - lightweight retrieval-augmented answering.

This demo runs fully offline: it retrieves the most relevant chunks from
STADIUM_DOCS (keyword/overlap scoring) and composes an answer template.
That retrieval step is genuine RAG; only the "generation" half is a
template instead of a call to an LLM, so this runs anywhere with no API
key or network. Swap in a real generator by replacing `_compose()` with
a call to your LLM of choice, e.g.:

    import requests
    def _compose(question, chunks, lang):
        context = "\n\n".join(c["text"] for c in chunks)
        prompt = f"Context:\n{context}\n\nAnswer in {lang}: {question}"
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={"model": "gpt-4o-mini",
                  "messages": [{"role": "user", "content": prompt}]},
        )
        return resp.json()["choices"][0]["message"]["content"]

Everything else (retrieval, translation stub, quick-actions) stays the same.
"""
import re
from data import STADIUM_DOCS

STOPWORDS = {"the", "a", "an", "is", "are", "to", "of", "in", "and", "for",
             "what", "where", "how", "do", "i", "my", "can", "you", "me"}

LANG_LABELS = {
    "en": "English", "es": "Spanish", "fr": "French",
    "pt": "Portuguese", "ar": "Arabic",
}

# tiny phrasebook so the multi-language demo is visibly functional
GREETINGS = {
    "en": "Here's what I found:",
    "es": "Esto es lo que encontré:",
    "fr": "Voici ce que j'ai trouvé :",
    "pt": "Aqui está o que encontrei:",
    "ar": "إليك ما وجدته:",
}
NO_MATCH = {
    "en": "I couldn't find that in the stadium guide - try asking about seating, parking, food, facilities, schedule or emergencies.",
    "es": "No encontré eso en la guía del estadio - pregunta sobre asientos, estacionamiento, comida, instalaciones, horario o emergencias.",
    "fr": "Je n'ai pas trouvé cela dans le guide du stade - essayez de poser une question sur les sièges, le parking, la nourriture, les installations, l'horaire ou les urgences.",
    "pt": "Não encontrei isso no guia do estádio - tente perguntar sobre assentos, estacionamento, comida, instalações, horário ou emergências.",
    "ar": "لم أجد ذلك في دليل الملعب - جرّب السؤال عن المقاعد أو الوقوف أو الطعام أو المرافق أو الجدول أو الطوارئ.",
}


def _stem(w):
    return w[:-1] if len(w) > 4 and w.endswith("s") else w


def _tokenize(text):
    return [_stem(w) for w in re.findall(r"[a-zA-Z]+", text.lower()) if w not in STOPWORDS]


# Minimal cross-language keyword bridge so Spanish/French/Portuguese/Arabic
# (transliterated) questions still retrieve the right English doc chunks.
# A production build would translate the question with a real MT model
# (e.g. Azure Translator) before retrieval instead.
TRANSLATE_HINTS = {
    "estacionamiento": "parking", "parking": "parking", "parqueo": "parking",
    "asiento": "seating", "asientos": "seating", "siege": "seating", "sieges": "seating",
    "comida": "food", "nourriture": "food", "comer": "food",
    "bano": "restroom", "banos": "restroom", "toilette": "restroom", "toilettes": "restroom",
    "banheiro": "restroom", "medico": "medical", "medical": "medical", "emergencia": "emergency",
    "urgence": "emergency", "emergencia": "emergency", "horario": "schedule", "horaire": "schedule",
    "salida": "exit", "sortie": "exit", "saida": "exit", "idioma": "language", "langue": "language",
}


def _bridge(text):
    words = re.findall(r"[a-zA-ZÀ-ÿ]+", text.lower())
    extra = [TRANSLATE_HINTS[w] for w in words if w in TRANSLATE_HINTS]
    return text + " " + " ".join(extra)


def retrieve(question, k=2):
    q_tokens = set(_tokenize(_bridge(question)))
    scored = []
    for doc in STADIUM_DOCS:
        d_tokens = set(_tokenize(doc["title"] + " " + doc["text"]))
        overlap = len(q_tokens & d_tokens)
        if overlap:
            scored.append((overlap, doc))
    scored.sort(key=lambda x: -x[0])
    return [d for _, d in scored[:k]]


def _compose(question, chunks, lang):
    intro = GREETINGS.get(lang, GREETINGS["en"])
    body = " ".join(c["text"] for c in chunks)
    return f"{intro} {body}"


def answer(question, lang="en"):
    chunks = retrieve(question)
    if not chunks:
        return {
            "answer": NO_MATCH.get(lang, NO_MATCH["en"]),
            "sources": [],
            "lang": lang,
        }
    return {
        "answer": _compose(question, chunks, lang),
        "sources": [c["title"] for c in chunks],
        "lang": lang,
    }
