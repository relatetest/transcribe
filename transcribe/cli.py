"""transcribe: the one command. Exit codes: 0 transcript written, 1 the run failed, 2 wrong arguments or config."""
import argparse
import datetime
import os
import sys
import traceback

from . import __version__, config
from .compare import flag, parse_terms, unflag

DEFAULT_OUT = "transcribe-out"

EXAMPLES = """\
примеры:
  transcribe call.mov --lang en --terms "Figma, After Effects, Relate"
  transcribe interview.mp4 --lang ru --out ./interview-text
  transcribe --reflag --out ./interview-text

Результат: <out>/transcript.md для чтения и <out>/transcript.json со всеми фрагментами.
Фрагменты, где модели разошлись, отмечены ⚑: их нужно прослушать, прежде чем цитировать."""


class UsageError(Exception):
    pass


class RuHelp(argparse.RawDescriptionHelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):
        return super().add_usage(usage, actions, groups, "использование: " if prefix is None else prefix)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, "%s: ошибка в аргументах: %s\nПодробно: %s --help\n" % (self.prog, message, self.prog))


def build_parser():
    ap = Parser(prog="transcribe", formatter_class=RuHelp, add_help=False, epilog=EXAMPLES,
                description="Расшифровка созвонов и видео на своём компьютере.\n"
                            "Запись режется на фрагменты до 22 с по паузам, каждый фрагмент распознают две модели,\n"
                            "спикеры подписываются S1, S2…; фрагменты, где модели разошлись или пропали термины,\n"
                            "отмечаются для прослушивания.")
    ap._positionals.title = "аргументы"
    ap._optionals.title = "параметры"
    ap.add_argument("-h", "--help", action="help", help="показать эту справку и выйти")
    ap.add_argument("--version", action="version", version="transcribe " + __version__, help="показать версию и выйти")
    ap.add_argument("media", nargs="?", metavar="ЗАПИСЬ", help="запись: видео или аудио в любом формате, который читает ffmpeg; с --reflag не нужна")
    ap.add_argument("--out", metavar="ПАПКА", help="папка для transcript.md и transcript.json (по умолчанию ./%s/<имя записи>)" % DEFAULT_OUT)
    ap.add_argument("--lang", default="auto", metavar="ЯЗЫК", help="язык речи: en, ru, код другого языка из README (de, fr, kk…) или auto, "
                                                                "чтобы определить по первым фрагментам (по умолчанию auto)")
    ap.add_argument("--terms", default="", metavar="ТЕРМИНЫ", help="имена и термины из записи через запятую, например «Figma, After Effects»: "
                                                "модели пишут их правильно, а пропуски отмечаются")
    ap.add_argument("--no-check", action="store_true", help="только основная модель: быстрее, но это черновик, ничего не отмечается")
    ap.add_argument("--reflag", action="store_true", help="пересчитать отметки в готовой папке --out без моделей и переписать оба файла")
    ap.add_argument("--config", metavar="ФАЙЛ", help="свой файл моделей вместо встроенного transcribe/models.json")
    return ap


def out_dir(a):
    if a.out:
        return a.out
    if a.media:
        return os.path.join(DEFAULT_OUT, os.path.splitext(os.path.basename(a.media))[0] or "transcript")
    raise UsageError("укажите папку прошлого запуска: transcribe --reflag --out <папка>")


def reflag(out):
    from . import report
    if not os.path.isfile(os.path.join(out, "transcript.json")):
        raise UsageError("в папке %s нет transcript.json: укажите в --out папку, куда transcribe уже писал" % out)
    try:
        meta, rows = report.read(out)
    except (ValueError, KeyError) as e:
        raise UsageError("%s/transcript.json не похож на результат transcribe: %s" % (out, e))
    unflag(rows)
    meta["flagged"] = flag(rows, meta.get("terms") or [], meta.get("crosscheck") is not None)
    meta["reflagged"] = datetime.datetime.now().isoformat(timespec="seconds")
    path = report.write(out, meta, rows)
    print("отметки пересчитаны: %s · отмечено %d из %d" % (path, meta["flagged"], len(rows)), flush=True)


def transcribe(a, out):
    from . import pipeline, report
    cfg = config.load(a.config)
    if a.lang != "auto" and a.lang not in cfg["languages"]:
        raise UsageError("язык «%s» не настроен; есть: %s или auto" % (a.lang, ", ".join(cfg["languages"])))
    if not os.path.isfile(a.media):
        raise UsageError("файл не найден: %s" % a.media)
    meta, rows = pipeline.transcribe(a.media, cfg, a.lang, parse_terms(a.terms), crosscheck=not a.no_check)
    path = report.write(out, meta, rows)
    print("готово: %s · отмечено %d из %d" % (path, meta["flagged"], len(rows)), flush=True)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    a = build_parser().parse_args(argv)
    try:
        if a.reflag:
            reflag(out_dir(a))
        elif not a.media:
            raise UsageError("укажите запись: transcribe <файл> [--out папка]. Справка: transcribe --help")
        else:
            transcribe(a, out_dir(a))
        return 0
    except (UsageError, config.ConfigError) as e:
        print("transcribe: %s" % e, file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("transcribe: прервано", file=sys.stderr)
        return 130
    except Exception as e:
        from .pipeline import ToolError
        if isinstance(e, ToolError):
            print("transcribe: %s" % e, file=sys.stderr)
        else:
            traceback.print_exc()
            print("transcribe: неожиданная ошибка (%s). Текст выше пригодится владельцу инструмента." % type(e).__name__,
                  file=sys.stderr)
        return 1
