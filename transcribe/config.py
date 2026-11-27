"""The model config: which models run for which language, pinned to which revision."""
import json
import os

DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models.json")
ENGINES = {"qwen3-asr", "granite-speech", "gigaam", "nemotron-diarization"}
ASR_ENGINES = ENGINES - {"nemotron-diarization"}
HF_ENGINES = {"qwen3-asr", "granite-speech", "nemotron-diarization"}


class ConfigError(Exception):
    pass


def load(path=None):
    """Read and check the config; raise ConfigError with a sentence a person can act on."""
    path = path or DEFAULT
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        raise ConfigError("файл моделей не найден: %s. Проверьте путь в --config." % path)
    except (OSError, ValueError) as e:
        raise ConfigError("файл моделей %s не читается как JSON: %s" % (path, e))
    check(cfg, path)
    cfg["_path"] = os.path.abspath(path)
    return cfg


def check(cfg, path="models.json"):
    def bad(msg):
        raise ConfigError("файл моделей %s: %s" % (path, msg))

    if not isinstance(cfg, dict):
        bad("ожидается объект JSON")
    models, langs = cfg.get("models"), cfg.get("languages")
    if not isinstance(models, dict) or not models:
        bad("нет раздела «models»")
    if not isinstance(langs, dict) or not langs:
        bad("нет раздела «languages»")
    for key, spec in models.items():
        engine = spec.get("engine") if isinstance(spec, dict) else None
        if engine not in ENGINES:
            bad("у модели «%s» engine «%s»; этот инструмент умеет: %s" % (key, engine, ", ".join(sorted(ENGINES))))
        if engine in HF_ENGINES and not spec.get("repo"):
            bad("у модели «%s» нет «repo» (имя на Hugging Face)" % key)
        if engine == "gigaam" and not spec.get("version"):
            bad("у модели «%s» нет «version» (например multilingual_v2_rnnt)" % key)

    def model(key, role, engines):
        if key not in models:
            bad("%s ссылается на «%s», а такой модели нет в «models»" % (role, key))
        if models[key]["engine"] not in engines:
            bad("%s: модель «%s» не подходит для этой роли" % (role, key))

    for code, spec in langs.items():
        if not isinstance(spec, dict) or not spec.get("primary"):
            bad("у языка «%s» нет «primary»" % code)
        model(spec["primary"], "languages.%s.primary" % code, ASR_ENGINES)
        if spec.get("crosscheck"):
            model(spec["crosscheck"], "languages.%s.crosscheck" % code, ASR_ENGINES)
        tag = spec.get("gigaam_language")
        if tag is not None and (not isinstance(tag, str) or not models[spec["primary"]].get("multilingual")):
            bad("у языка «%s» задан «gigaam_language», а его основная модель не многоязычная GigaAM "
                "(«multilingual»: true)" % code)
    if cfg.get("default_language") not in langs:
        bad("«default_language» должен быть одним из языков: %s" % ", ".join(langs))
    model(cfg.get("diarization"), "diarization", {"nemotron-diarization"})
    model(cfg.get("language_detection"), "language_detection", {"qwen3-asr"})


def label(spec):
    """How a model is named in the transcript: its Hugging Face repo, or «GigaAM multilingual_v2_rnnt»."""
    if spec["engine"] == "gigaam":
        return "salute-developers/GigaAM " + spec["version"]
    return spec["repo"]
