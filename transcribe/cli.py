"""transcribe: the one command. Exit codes: 0 transcript written, 1 the run failed, 2 wrong arguments."""
import argparse
import os
import sys
import traceback

from . import __version__

DEFAULT_OUT = "transcribe-out"

EXAMPLES = """\
примеры:
  transcribe call.mp4
  transcribe interview.mov --out ./interview-text

Результат: <out>/transcript.md для чтения и <out>/transcript.json со всеми фрагментами.
Язык указывать не нужно: модель понимает русский и английский, в том числе вперемешку."""


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
                description="Расшифровка созвонов и видео на русском и английском на своём компьютере.\n"
                            "Видеокарта не нужна. Спикеры подписываются S1, S2…")
    ap._positionals.title = "аргументы"
    ap._optionals.title = "параметры"
    ap.add_argument("-h", "--help", action="help", help="показать эту справку и выйти")
    ap.add_argument("--version", action="version", version="transcribe " + __version__, help="показать версию и выйти")
    ap.add_argument("media", nargs="?", metavar="ЗАПИСЬ", help="запись: видео или аудио в любом формате, который читает ffmpeg")
    ap.add_argument("--out", metavar="ПАПКА", help="папка для transcript.md и transcript.json (по умолчанию ./%s/<имя записи>)" % DEFAULT_OUT)
    return ap


def out_dir(a):
    return a.out or os.path.join(DEFAULT_OUT, os.path.splitext(os.path.basename(a.media))[0] or "transcript")


def run(a):
    from . import pipeline, report
    if not os.path.isfile(a.media):
        raise UsageError("файл не найден: %s" % a.media)
    meta, rows = pipeline.transcribe(a.media)
    path = report.write(out_dir(a), meta, rows)
    print("готово: %s" % path, flush=True)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    a = build_parser().parse_args(argv)
    try:
        if not a.media:
            raise UsageError("укажите запись: transcribe <файл> [--out папка]. Справка: transcribe --help")
        run(a)
        return 0
    except UsageError as e:
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
