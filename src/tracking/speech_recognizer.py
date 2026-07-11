"""Offline streaming speech recognition for page-turn commands."""

import json
import queue
import re
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable, Iterable, Optional


@dataclass(frozen=True)
class VoiceCommand:
    action: str
    transcript: str


class CommandParser:
    def __init__(
        self,
        previous_phrases: Iterable[str],
        next_phrases: Iterable[str],
        pause_phrases: Iterable[str],
        resume_phrases: Iterable[str],
        wake_words: Iterable[str],
        require_wake_word: bool,
    ) -> None:
        self._commands = self._build_commands(
            previous_phrases, next_phrases, pause_phrases, resume_phrases
        )
        self._wake_words = tuple(filter(None, map(self.normalize, wake_words)))
        self.require_wake_word = require_wake_word

    @staticmethod
    def normalize(text: str) -> str:
        return re.sub(r"[^\w\u4e00-\u9fff]", "", text.lower(), flags=re.UNICODE)

    def _build_commands(self, *groups: Iterable[str]) -> dict[str, str]:
        actions = ("PREVIOUS", "NEXT", "PAUSE", "RESUME")
        commands: dict[str, str] = {}
        for action, phrases in zip(actions, groups):
            for phrase in phrases:
                normalized = self.normalize(phrase)
                if normalized:
                    commands[normalized] = action
        return commands

    @property
    def grammar(self) -> list[str]:
        phrases = list(self._commands)
        if self._wake_words:
            phrases.extend(self._wake_words)
            phrases.extend(
                wake + command for wake in self._wake_words for command in self._commands
            )
        return list(dict.fromkeys(phrases))

    def parse(self, transcript: str) -> Optional[VoiceCommand]:
        normalized = self.normalize(transcript)
        if not normalized:
            return None
        wake = next((word for word in self._wake_words if normalized.startswith(word)), None)
        if self.require_wake_word and wake is None:
            return None
        if wake:
            normalized = normalized[len(wake) :]
        action = self._commands.get(normalized)
        return VoiceCommand(action, transcript) if action else None


class SpeechRecognizer:
    def __init__(
        self,
        model_path: str,
        parser: CommandParser,
        device: Optional[int] = None,
        sample_rate: int = 16000,
    ) -> None:
        path = Path(model_path)
        if not path.is_dir():
            raise FileNotFoundError(f"语音模型不存在: {path}")
        try:
            import sounddevice as sd
            from vosk import KaldiRecognizer, Model
        except ImportError as exc:
            raise RuntimeError("缺少语音依赖，请重新安装 requirements.txt") from exc
        self._sd = sd
        self._recognizer = KaldiRecognizer(
            Model(str(path)), sample_rate, json.dumps(parser.grammar, ensure_ascii=False)
        )
        self._parser = parser
        self._device = device
        self._sample_rate = sample_rate
        self._audio: queue.Queue[bytes | Exception] = queue.Queue(maxsize=20)

    def run(self, stop_event: Event, callback: Callable[[VoiceCommand], None]) -> None:
        def on_audio(indata, frames, time_info, status) -> None:
            del frames, time_info
            payload = (
                RuntimeError(f"麦克风输入异常: {status}") if status else bytes(indata)
            )
            try:
                self._audio.put_nowait(payload)
            except queue.Full:
                try:
                    self._audio.get_nowait()
                except queue.Empty:
                    pass
                self._audio.put_nowait(payload)

        with self._sd.RawInputStream(
            samplerate=self._sample_rate,
            blocksize=4000,
            device=self._device,
            dtype="int16",
            channels=1,
            callback=on_audio,
        ):
            while not stop_event.is_set():
                try:
                    data = self._audio.get(timeout=0.1)
                except queue.Empty:
                    continue
                if isinstance(data, Exception):
                    raise data
                if self._recognizer.AcceptWaveform(data):
                    transcript = json.loads(self._recognizer.Result()).get("text", "")
                    command = self._parser.parse(transcript)
                    if command:
                        callback(command)
