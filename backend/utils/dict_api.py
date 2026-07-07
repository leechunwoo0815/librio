# backend/utils/dict_api.py
"""外部词典API兜底"""

import logging

import httpx

logger = logging.getLogger(__name__)

FREE_DICT_API = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
REQUEST_TIMEOUT = 5


async def lookup_free_dict(word: str) -> dict | None:
    """
    Free Dictionary API 兜底查词（英文释义，无中文翻译）
    仅在 ECDICT 本地查不到时使用
    """
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.get(FREE_DICT_API.format(word=word))
            if resp.status_code != 200:
                return None
            data = resp.json()
            if not data or not isinstance(data, list):
                return None

            entry = data[0]
            phonetic = ""
            for p in entry.get("phonetics", []):
                if p.get("text"):
                    phonetic = p["text"]
                    break

            audio_url = ""
            for p in entry.get("phonetics", []):
                if p.get("audio"):
                    audio_url = p["audio"]
                    break

            meanings = entry.get("meanings", [])
            part_of_speech = meanings[0]["partOfSpeech"] if meanings else ""
            definitions = []
            for m in meanings:
                for d in m.get("definitions", [])[:2]:
                    definitions.append(d.get("definition", ""))
            english_meaning = "; ".join(definitions[:3])

            example = ""
            for m in meanings:
                for d in m.get("definitions", []):
                    if d.get("example"):
                        example = d["example"]
                        break
                if example:
                    break

            return {
                "word": word.lower(),
                "phonetic": phonetic,
                "audio_url": audio_url,
                "part_of_speech": part_of_speech,
                "english_meaning": english_meaning,
                "example_sentence": example,
                "source": "free_dict",
            }
    except Exception as e:
        logger.warning(f"Free dict API failed for '{word}': {e}")
        return None
