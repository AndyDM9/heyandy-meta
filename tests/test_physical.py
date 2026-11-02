"""The physical scorecard's own questions: a person judges each point, and a slip of the keyboard is asked again."""
import builtins

from evals.physical import ask


def test_enter_alone_is_asked_again_not_taken_for_an_answer(monkeypatch, capsys):
    answers = iter(["", "  ", "x", "Y"])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(answers))
    assert ask("At the thing?", "yno") == "y"
    assert capsys.readouterr().out.count("Type one letter") == 3
